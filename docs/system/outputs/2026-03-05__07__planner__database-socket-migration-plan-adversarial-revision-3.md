### 1. Overview
This is revision 3 of the database socket migration plan after role-reversed adversarial review.

This revision addresses all remaining critical gaps from `__06__`:
- `try/finally` safety bug around `src` initialization and snapshot cleanup,
- unstable exactly-once keying based on batch shape,
- dedup uniqueness conflict with override semantics,
- unspecified DDL for single-active provider invariants.

### 2. Non-Negotiable Invariants
1. Migration lock is always released, regardless of failure point.
2. Snapshot is always closed when opened, including dry-run.
3. Exactly-once semantics are cursor-range-based, not batch-shape-based.
4. Cross-volume quote dedup remains deterministic with explicit override path.
5. Exactly one active provider is enforced by concrete DB constraints.
6. All terminal outcomes are persisted to one authoritative migration event log.

### 3. Corrected Migration Pseudocode
```python
def swap_provider(from_cfg, to_cfg, run_id, dry_run=False):
    require_maintenance_mode()
    lock = acquire_migration_lock(run_id=run_id, ttl_seconds=300, renew=True)
    src = None
    snapshot = None

    append_migration_event(run_id, state="started", from_provider=from_cfg.name, to_provider=to_cfg.name)

    try:
        src = factory(from_cfg)
        dst = factory(to_cfg)
        assert_runtime_provider_supported(to_cfg.name)  # blocks legacy_json target

        snapshot = src.begin_export_snapshot()
        manifest = src.export_manifest(snapshot=snapshot)

        if dry_run:
            append_migration_event(run_id, state="dry_run_complete", manifest=manifest)
            return manifest

        checkpoint = load_or_init_checkpoint(run_id)
        for entity in TOPOLOGICAL_ORDER:
            while True:
                # Cursor is immutable PK range, not list position.
                range_start, range_end = checkpoint.next_pk_window(entity, window_size=500)
                rows = src.export_pk_window(entity, snapshot=snapshot, start=range_start, end=range_end)
                if not rows:
                    break
                idempotency_key = f"{run_id}:{entity}:{range_start}:{range_end}"
                with dst.transaction():
                    if dst.commit_exists(idempotency_key):
                        checkpoint.mark_window_done(entity, range_end)
                        checkpoint.persist_txn(dst)
                        continue
                    dst.import_rows_strict(entity, rows)
                    checkpoint.mark_window_done(entity, range_end)
                    checkpoint.persist_txn(dst)
                    dst.record_commit(idempotency_key)

        verify = compare_manifest_to_target(manifest, dst)
        if not verify.ok:
            append_migration_event(run_id, state="verification_failed", error=verify.report)
            raise MigrationVerificationError(verify.report)

        set_provider_pending(run_id, to_provider=to_cfg.name)
        health = run_post_cutover_health_gate(to_cfg)
        if not health.ok:
            rollback_pending(run_id, reason=health.report)
            append_migration_event(run_id, state="cutover_health_failed", error=health.report)
            raise ProviderCutoverError(health.report)

        activate_provider_atomically(run_id, new_provider=to_cfg.name, old_provider=from_cfg.name)
        append_migration_event(run_id, state="completed", verify=verify.report)
        return verify.report

    except Exception as exc:
        append_migration_event(run_id, state="failed", error=str(exc))
        raise
    finally:
        if src is not None and snapshot is not None:
            src.end_export_snapshot(snapshot)
        release_migration_lock(lock)
```

### 4. Required Schema and Constraint Details
#### 4.1 Provider state (single active provider)
`provider_states(provider_name PK, state, run_id, updated_at)`

Postgres:
- `CREATE UNIQUE INDEX uq_provider_single_active ON provider_states ((state)) WHERE state = 'active';`

SQLite:
- maintain singleton row table `active_provider_singleton(id INTEGER PRIMARY KEY CHECK(id=1), provider_name UNIQUE NOT NULL)`.
- transaction updates `provider_states` and singleton row together.

#### 4.2 Quote dedup + override semantics
Base table:
- `quote_uses(id PK, volume_id FK, series_id_materialized, quote_hash, ..., added_at)`
- required unique: `(volume_id, quote_hash)`
- required unique: `(series_id_materialized, quote_hash)` for non-overridden inserts.

Override table (explicit structural separation):
- `quote_use_overrides(id PK, quote_use_id FK UNIQUE, reason NOT NULL, approved_by, approved_at)`

Write semantics:
1. Non-override insert path must satisfy both uniqueness constraints.
2. Override path writes to `quote_use_overrides` and uses dedicated insert mode that records exception intent.
3. Read path always joins override metadata so behavior remains deterministic and auditable.

#### 4.3 Drift control for `series_id_materialized`
- DB trigger updates materialized series id when `volume_id` changes.
- migration-time reconciliation query asserts:
  - `quote_uses.series_id_materialized = volumes.series_id` for all rows.
- mismatch fails migration verification.

### 5. Locking and Fencing
- lock must include:
  - lease TTL,
  - owner token,
  - fencing token monotonic counter.
- all state-mutating operations validate fencing token to prevent stale-owner writes.

### 6. Authoritative Logging
Single sink: `migration_events`
- `id PK, run_id, ts, actor, phase, state, from_provider, to_provider, lock_owner, fencing_token, manifest_scope, payload_json, error_json`

Required:
- write event on every terminal state:
  - `completed`, `failed`, `verification_failed`, `cutover_health_failed`, `rollback_failed`.
- redact secrets in payload/error fields.

### 7. TLS and Secret Policy (Explicit)
For Postgres providers:
- credentials only from environment/secret manager,
- TLS verification required (hostname + CA validation),
- fail startup if insecure TLS mode is detected.

Acceptance test:
- ensure no DSN/password/secret value appears in CLI or logs on failure paths.

### 8. Acceptance Criteria Additions
- `src` initialization and snapshot cleanup path cannot raise `UnboundLocalError`.
- dry-run leaves no open snapshot transaction.
- idempotency key is derived from immutable PK cursor bounds.
- replayed committed window advances checkpoint deterministically.
- override behavior is structurally represented and auditable.
- single-active provider invariant enforced in both Postgres and SQLite.
- migration event log records all terminal outcomes with secret redaction.

### 9. Test Additions
1. Factory failure test: lock still released; no masking exception.
2. Dry-run snapshot close test.
3. Window-bound idempotency resume test with changed batch shape.
4. Override path test proving uniqueness + explicit override table semantics.
5. Provider singleton constraint test (SQLite + Postgres).
6. Fencing token stale-owner rejection test.
7. Log redaction test for DSN/password leak prevention.
