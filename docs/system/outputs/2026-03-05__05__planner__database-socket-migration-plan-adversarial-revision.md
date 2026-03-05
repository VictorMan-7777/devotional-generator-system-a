### 1. Overview
This is a corrected revision of `2026-03-05__04__planner__database-socket-migration-plan.md` after a deep-dive adversarial review.

Goal remains unchanged:
- introduce a swappable database socket abstraction,
- support controlled provider migration,
- preserve deterministic behavior and auditability.

### 2. Review Outcome Summary
Adversarial review verdict on prior artifact: `NEEDS_REVISION (4/10)` with critical findings in:
- snapshot consistency and live-source compare invalidation,
- unsafe migration write mode (`upsert=True`),
- dual migration authorities (`alembic` + custom `schema_migrations`),
- missing DB-enforced dedup guarantees,
- missing resumable migration protocol.

This revision applies all required corrections.

### 3. Corrected Technical Approach
Use a hexagonal `DatabaseSocket` with strict migration governance:

1. `DatabaseSocket` protocol remains the only persistence port used by application logic.
2. Adapters:
   1. `SQLiteAdapter` (default runtime provider)
   2. `PostgresAdapter` (runtime provider)
   3. `LegacyJsonAdapter` (**source-only** migration bridge; never active provider)
3. Migration runner performs snapshot-based export and strict import:
   1. Acquire global migration lock and require maintenance mode preflight.
   2. Capture immutable source manifest from a repeatable-read snapshot (or explicit write freeze boundary).
   3. Import using **strict insert** mode (no silent upserts).
   4. Compare target against immutable snapshot manifest, not live source.
   5. Run cutover health gate.
   6. Commit two-phase provider switch (`pending` -> `active`) or rollback.
4. Migration authority is Alembic-only (single source of truth for schema versions).
5. Postgres security posture is mandatory:
   1. DSN from env/secret source only.
   2. TLS required (`sslmode=verify-full` equivalent).
   3. Certificate validation documented and tested.

### 4. File Changes (Revised)
| File path | Action | Description of changes |
|---|---|---|
| [src/persistence/socket.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/socket.py) | create | Contract for persistence + migration snapshot/export primitives. |
| [src/persistence/factory.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/factory.py) | create | Provider factory. Enforce `legacy_json` as source-only (cannot become active provider). |
| [src/persistence/config.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/config.py) | create | Typed config and security validation for provider credentials/TLS. |
| [src/persistence/adapters/sqlite_adapter.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/adapters/sqlite_adapter.py) | create | SQLite runtime adapter implementing socket contract. |
| [src/persistence/adapters/postgres_adapter.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/adapters/postgres_adapter.py) | create | Postgres runtime adapter with matching invariants and constraints. |
| [src/persistence/adapters/legacy_json_adapter.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/adapters/legacy_json_adapter.py) | create | Source-only adapter for initial migration read path. |
| [src/persistence/schema/models.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/schema/models.py) | create | Core Phase-15 schema only (exclude future-scope tables). |
| [alembic/](/Volumes/claude-projects/projects/devotional-generator-system-a/alembic) | create | Canonical migration authority. |
| [src/persistence/migration/runner.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/migration/runner.py) | create | Snapshot export, strict import, verification, checkpoint/resume state machine. |
| [src/persistence/migration/verify.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/migration/verify.py) | create | Immutable-manifest verification and drift checks. |
| [scripts/db/swap_provider.py](/Volumes/claude-projects/projects/devotional-generator-system-a/scripts/db/swap_provider.py) | create | CLI with mandatory preflight checks, staged cutover, rollback hooks, report output. |
| [src/registry/registry.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/registry/registry.py) | modify | Delegate persistence to socket while preserving behavior. |
| [src/grounding_store/store.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/grounding_store/store.py) | modify | Socket-backed persistence path. |
| [src/prayer_trace_store/store.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/prayer_trace_store/store.py) | modify | Socket-backed persistence path. |
| [pyproject.toml](/Volumes/claude-projects/projects/devotional-generator-system-a/pyproject.toml) | modify | Add Alembic + Postgres driver dependencies. |
| [tests/persistence/test_socket_contract.py](/Volumes/claude-projects/projects/devotional-generator-system-a/tests/persistence/test_socket_contract.py) | create | Adapter contract tests. |
| [tests/persistence/test_swap_migration.py](/Volumes/claude-projects/projects/devotional-generator-system-a/tests/persistence/test_swap_migration.py) | create | Snapshot, strict insert, staged cutover, rollback, resume tests. |

### 5. Corrected Migration Orchestration
```python
def swap_provider(from_cfg, to_cfg, run_id, dry_run=False):
    require_maintenance_mode()
    lock = acquire_migration_lock(run_id=run_id)
    src = factory(from_cfg)
    dst = factory(to_cfg)

    # Snapshot boundary: repeatable-read tx or explicit freeze token.
    snapshot = src.begin_export_snapshot()
    manifest = src.export_manifest(snapshot=snapshot)  # immutable counts + checksums

    if dry_run:
        release_migration_lock(lock)
        return manifest

    checkpoint = load_or_init_checkpoint(run_id)
    for entity in TOPOLOGICAL_ORDER:
        for batch in src.export_batches(entity, snapshot=snapshot, after=checkpoint.cursor(entity)):
            # strict insert; conflicts are surfaced, never overwritten
            dst.import_batch(entity, batch, mode="insert_strict")
            checkpoint.advance(entity, batch)
            checkpoint.persist()

    verify = compare_manifest_to_target(manifest, dst)
    if not verify.ok:
        rollback_pending_cutover()
        raise MigrationVerificationError(verify.report)

    set_provider_state(to_cfg.name, state="pending", run_id=run_id)
    health = run_post_cutover_health_gate(to_cfg)
    if not health.ok:
        rollback_to_provider(from_cfg.name, run_id=run_id)
        raise ProviderCutoverError(health.report)

    set_provider_state(to_cfg.name, state="active", run_id=run_id)
    append_provider_switch_log(
        run_id=run_id,
        actor=current_actor(),
        lock_owner=lock.owner,
        from_provider=from_cfg.name,
        to_provider=to_cfg.name,
        manifest_scope=manifest.scope,
        status="success",
        error_payload=None,
    )
    release_migration_lock(lock)
```

### 6. Revised Database Structure (Phase-15 Scope)
Only core tables needed for current runtime and migration:

- `series`
  - `id` PK, `title`, `created_at`
- `volumes`
  - `id` PK, `series_id` FK, `volume_number`, `title`, `parent_volume_id` FK nullable, `created_at`
  - unique: (`series_id`, `volume_number`)
- `quote_uses`
  - `id` PK, `volume_id` FK, `quote_text`, `quote_hash`, `author`, `source_title`, `publication_year`, `override_reason`, `added_at`
  - unique: (`volume_id`, `quote_hash`)
  - optional policy unique: (`series_id_derived`, `quote_hash`) if business rule requires strict cross-volume lockout
  - note: do not store redundant mutable `series_id`; derive via join from `volumes`
- `scripture_uses`
  - `id` PK, `volume_id` FK, `reference`, `translation`, `added_at`
  - index: (`volume_id`, `reference`, `translation`)
- `grounding_maps`
  - `id` PK, `exposition_id`, `retrieval_run_id`, `payload_json`, `created_at`, `updated_at`
- `prayer_trace_maps`
  - `id` PK, `prayer_id`, `payload_json`, `created_at`, `updated_at`
- `provider_switch_log`
  - `id` PK, `run_id` unique, `actor`, `lock_owner`, `from_provider`, `to_provider`, `manifest_scope`, `started_at`, `completed_at`, `status`, `summary_json`, `error_payload_json`
- `migration_runs`
  - `run_id` PK, `from_provider`, `to_provider`, `status`, `checkpoint_json`, `created_at`, `updated_at`

Schema versioning:
- Alembic version table only (no custom `schema_migrations` table).

Deferred to later phase:
- `devotional_books`, `devotional_days`, `section_states`, `section_snapshots`.

### 7. Testing Strategy (Revised)
1. Contract tests:
   1. Every adapter passes identical CRUD + dedup + error semantics.
2. Migration correctness tests:
   1. Export under snapshot boundary only.
   2. Target verification uses immutable manifest, not live source.
   3. Strict insert conflict emits deterministic conflict report.
3. Resume/interrupt tests:
   1. Simulate kill during batch N.
   2. Resume with same `run_id` from checkpoint.
   3. Assert exactly-once row counts and checksum match.
4. Cutover safety tests:
   1. Pending state requires health gate pass.
   2. Failed health gate auto-rolls back active provider.
5. Security/config tests:
   1. Postgres connection rejected when TLS verification disabled.
   2. Secret-less DSN configuration rejected.
6. Governance tests:
   1. CLI fails when maintenance mode not enabled.
   2. CLI fails without migration lock acquisition.
   3. CLI rejects `--to legacy_json`.

### 8. Acceptance Criteria Additions (Mandatory)
- Migration command MUST enforce maintenance mode preflight.
- Migration command MUST acquire exclusive migration lock before export.
- Export MUST run from immutable snapshot boundary.
- Import MUST use strict insert mode (no implicit upsert overwrite).
- Verification MUST compare target to immutable snapshot manifest.
- Provider cutover MUST be staged (`pending` -> health-gated -> `active`) with automatic rollback.
- Migration MUST support resumable checkpoints with exactly-once semantics.
- DB-level uniqueness MUST enforce quote dedup invariants.
- Alembic MUST be the sole schema migration authority.

### 9. Risks and Controls
- Concurrent writes during export:
  - control: enforced maintenance mode + snapshot transaction boundary.
- Partial run interruption:
  - control: `migration_runs` checkpoint ledger and resumable `run_id`.
- Forensic gaps during incidents:
  - control: expanded `provider_switch_log` with run/actor/error/lock metadata.
- Legacy JSON misuse as runtime backend:
  - control: source-only adapter policy enforced in factory and CLI.
