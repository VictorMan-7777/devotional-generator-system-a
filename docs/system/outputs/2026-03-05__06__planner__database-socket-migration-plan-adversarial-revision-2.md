### 1. Overview
This is revision 2 of the Phase-15 database socket migration plan, updated after adversarial re-review of revision 1.

This revision resolves remaining critical gaps:
- guaranteed lock/snapshot cleanup (`try/finally`),
- no snapshot leak in dry-run paths,
- exactly-once resume semantics made atomic,
- corrected cutover state ordering,
- explicit single-active provider invariant,
- required (not optional) cross-volume dedup enforcement,
- explicit TLS configuration requirements.

### 2. Design Invariants
1. Exactly one active runtime provider at a time.
2. `legacy_json` is source-only and cannot be active target.
3. Migration export must come from immutable snapshot boundary.
4. Import + checkpoint advance must be atomic per batch.
5. Every terminal migration state (success/failure/rollback-failure) is logged.
6. Cross-volume quote dedup policy is mandatory and deterministic.
7. Alembic is the only schema migration authority.

### 3. Corrected Technical Approach
1. Keep hexagonal `DatabaseSocket` port for business logic.
2. Runtime adapters: SQLite and Postgres.
3. Bridge adapter: `LegacyJsonAdapter` (read-only source for first migration).
4. Migration runner:
   1. enforce maintenance mode preflight,
   2. acquire global migration lock,
   3. start source snapshot,
   4. export immutable manifest,
   5. import batches with atomic idempotent commit markers,
   6. compare target with immutable manifest,
   7. stage cutover (`pending`),
   8. run health gate,
   9. atomically switch active provider (`active`) and demote previous provider.

### 4. File Changes
| File path | Action | Description |
|---|---|---|
| [src/persistence/socket.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/socket.py) | create | Port interfaces, including snapshot context and idempotent batch APIs. |
| [src/persistence/factory.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/factory.py) | create | Provider factory; enforce source-only rule for `legacy_json`. |
| [src/persistence/config.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/config.py) | create | Provider config + explicit TLS/secret validation. |
| [src/persistence/adapters/sqlite_adapter.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/adapters/sqlite_adapter.py) | create | SQLite adapter implementation. |
| [src/persistence/adapters/postgres_adapter.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/adapters/postgres_adapter.py) | create | Postgres adapter implementation. |
| [src/persistence/adapters/legacy_json_adapter.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/adapters/legacy_json_adapter.py) | create | Read-only migration source adapter. |
| [src/persistence/migration/runner.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/migration/runner.py) | create | Snapshot-safe, lock-safe, resumable migration state machine. |
| [src/persistence/migration/verify.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/migration/verify.py) | create | Immutable-manifest verification logic. |
| [scripts/db/swap_provider.py](/Volumes/claude-projects/projects/devotional-generator-system-a/scripts/db/swap_provider.py) | create | CLI with enforced preflight checks and report output. |
| [src/persistence/schema/models.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/schema/models.py) | create | Phase-15 schema only, with required uniqueness and provider-state invariants. |
| [alembic/](/Volumes/claude-projects/projects/devotional-generator-system-a/alembic) | create | Canonical schema migration history. |
| [tests/persistence/test_swap_migration.py](/Volumes/claude-projects/projects/devotional-generator-system-a/tests/persistence/test_swap_migration.py) | create | Resumability, exactly-once, rollback, lock/snapshot cleanup tests. |

### 5. Corrected Migration Pseudocode (Lock/Snapshot Safe + Exactly-Once)
```python
def swap_provider(from_cfg, to_cfg, run_id, dry_run=False):
    require_maintenance_mode()
    lock = acquire_migration_lock(run_id)
    log_run_state(run_id, state="started", from_provider=from_cfg.name, to_provider=to_cfg.name)
    snapshot = None

    try:
        src = factory(from_cfg)
        dst = factory(to_cfg)
        assert_runtime_provider_supported(to_cfg.name)

        snapshot = src.begin_export_snapshot()  # repeatable-read or frozen boundary
        manifest = src.export_manifest(snapshot=snapshot)

        if dry_run:
            log_run_state(run_id, state="dry_run_complete", manifest=manifest)
            return manifest

        checkpoint = load_or_init_checkpoint(run_id)
        for entity in TOPOLOGICAL_ORDER:
            for batch in src.export_batches(entity, snapshot=snapshot, after=checkpoint.cursor(entity)):
                batch_id = deterministic_batch_id(run_id, entity, batch)
                # Atomic exactly-once apply:
                # transaction contains both data write and commit marker/checkpoint.
                with dst.transaction():
                    if dst.batch_already_committed(run_id, batch_id):
                        continue
                    dst.import_batch(entity, batch, mode="insert_strict")
                    dst.record_batch_commit(run_id, batch_id)
                    checkpoint.advance(entity, batch)
                    checkpoint.persist_txn(dst)

        verify = compare_manifest_to_target(manifest, dst)
        if not verify.ok:
            log_run_state(run_id, state="verification_failed", error=verify.report)
            raise MigrationVerificationError(verify.report)

        # Stage pending before health gate.
        set_provider_state_pending(run_id, from_provider=from_cfg.name, to_provider=to_cfg.name)
        health = run_post_cutover_health_gate(to_cfg)
        if not health.ok:
            rollback_pending_state(run_id, reason=health.report)
            log_run_state(run_id, state="cutover_health_failed", error=health.report)
            raise ProviderCutoverError(health.report)

        # Atomic single-active transition:
        # exactly one row may hold active=true.
        activate_provider_atomically(run_id, new_active=to_cfg.name, old_active=from_cfg.name)
        log_run_state(run_id, state="completed", verify=verify.report)
        return verify.report

    except Exception as exc:
        safe_log_failure(run_id, exc)
        raise
    finally:
        if snapshot is not None:
            src.end_export_snapshot(snapshot)
        release_migration_lock(lock)
```

### 6. Revised Database Structure (Phase-15 Core Only)
- `series`
  - `id` PK, `title`, `created_at`
- `volumes`
  - `id` PK, `series_id` FK, `volume_number`, `title`, `parent_volume_id` nullable FK, `created_at`
  - unique: (`series_id`, `volume_number`)
- `quote_uses`
  - `id` PK, `volume_id` FK, `series_id_materialized` (stored value maintained by app/trigger), `quote_text`, `quote_hash`, `author`, `source_title`, `publication_year`, `override_reason`, `added_at`
  - required unique: (`volume_id`, `quote_hash`)
  - required unique: (`series_id_materialized`, `quote_hash`) with override handled via explicit override record path
- `scripture_uses`
  - `id` PK, `volume_id` FK, `reference`, `translation`, `added_at`
  - index: (`volume_id`, `reference`, `translation`)
- `grounding_maps`
  - `id` PK, `exposition_id`, `retrieval_run_id`, `payload_json`, `created_at`, `updated_at`
- `prayer_trace_maps`
  - `id` PK, `prayer_id`, `payload_json`, `created_at`, `updated_at`
- `migration_runs`
  - `run_id` PK, `from_provider`, `to_provider`, `state`, `checkpoint_json`, `manifest_json`, `created_at`, `updated_at`
- `migration_batch_commits`
  - `run_id`, `batch_id`, `entity_name`, `committed_at`
  - PK: (`run_id`, `batch_id`)
- `provider_states`
  - `provider_name` PK, `state` (`inactive|pending|active`), `updated_at`, `run_id`
  - invariant: only one `active` provider (enforced via transaction + uniqueness strategy)
- `provider_switch_log`
  - `id` PK, `run_id`, `actor`, `lock_owner`, `from_provider`, `to_provider`, `status`, `started_at`, `completed_at`, `manifest_scope`, `summary_json`, `error_payload_json`

Not in this phase:
- future-scope book/day/section persistence tables.

### 7. TLS and Secret Requirements (Explicit)
Postgres runtime must require:
- `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` from env/secret source (not committed config),
- TLS mode equivalent to verify-full:
  - hostname verification enabled,
  - CA certificate path required,
  - client cert/key supported if policy requires mTLS.

Driver settings (to document and test in implementation):
- SQLAlchemy URL params for psycopg with SSL root cert and hostname verification.
- CLI/config validation must fail if TLS verification is not enabled for Postgres.

### 8. Acceptance Criteria (Corrected)
- Lock release guaranteed on every path.
- Export snapshot closed on every path, including dry-run.
- Per-batch apply + commit marker + checkpoint are atomic.
- Resume with same `run_id` is exactly-once.
- Verification compares target to immutable manifest.
- Pending cutover and rollback ordering are valid.
- Single-active provider invariant is enforced atomically.
- Cross-volume dedup is required (not optional) with explicit override flow.
- Failure states are persisted in provider switch logs.
- `legacy_json` cannot be configured as active runtime provider.

### 9. Test Plan Additions
1. Lock leak test: inject exception before verification; assert lock released.
2. Snapshot leak test: dry-run and error paths close snapshot.
3. Crash between import/checkpoint simulated; resume proves exactly-once.
4. Verification-fail path logs terminal failure and does not activate target.
5. Health-gate fail path rolls back pending state and retains old active provider.
6. Single-active invariant test under concurrent cutover attempts.
7. Cross-volume dedup deterministic behavior with and without override.
8. Postgres TLS enforcement test with insecure config rejected.
