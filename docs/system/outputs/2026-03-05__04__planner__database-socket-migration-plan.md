### 1. Overview
This task introduces a unified persistence layer so the system can run on interchangeable databases (for example SQLite or Postgres) without changing business logic.  
It also adds a controlled provider-swap workflow that migrates data from the old database to the new one with verification and rollback safety.

Skills note: I did not invoke the listed skills because `skill-creator` and `skill-installer` are for Codex skill authoring/installation, not system database architecture.

### 2. Technical Approach
Use a hexagonal “database socket” (port/adapter) design:

1. Define a `DatabaseSocket` protocol (the stable contract used by pipeline, validators, registry, artifact stores).
2. Implement provider adapters behind it:
   1. `SQLiteAdapter` (default local)
   2. `PostgresAdapter` (swap target)
   3. `LegacyJsonAdapter` (read bridge for existing file artifacts)
3. Move persistence call sites (`SeriesRegistry`, `GroundingMapStore`, `PrayerTraceMapStore`) to the socket contract.
4. Add a migration runner that can export/import all entities between providers in deterministic order with integrity checks.
5. Add provider selection config and a safe `swap_provider` command.

Key decisions and tradeoffs:
- Keep current domain models unchanged (lower regression risk).
- Use SQLAlchemy for both SQLite/Postgres adapters (single ORM surface, minor dialect differences).
- Store complex artifact bodies as JSON columns for portability.
- Make migration explicit and operator-triggered (safer than automatic on boot).

### 3. File Changes
| File path | Action | Description of changes |
|---|---|---|
| [src/persistence/socket.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/socket.py) | create | `Protocol` definitions for persistence operations (series/volume, quote/scripture usage, grounding/prayer maps, snapshots/approval state). |
| [src/persistence/factory.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/factory.py) | create | Provider factory: builds socket instance from config (`sqlite`, `postgres`, `legacy_json`). |
| [src/persistence/config.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/config.py) | create | Typed config model and loader for active DB provider and connection settings. |
| [src/persistence/adapters/sqlite_adapter.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/adapters/sqlite_adapter.py) | create | SQLite implementation of `DatabaseSocket`; preserves current registry semantics. |
| [src/persistence/adapters/postgres_adapter.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/adapters/postgres_adapter.py) | create | Postgres implementation with matching behavior and constraints. |
| [src/persistence/adapters/legacy_json_adapter.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/adapters/legacy_json_adapter.py) | create | Read adapter for existing JSON artifact stores to support first migration. |
| [src/persistence/schema/models.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/schema/models.py) | create | SQLAlchemy ORM schema for all tables listed below. |
| [src/persistence/migration/runner.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/migration/runner.py) | create | End-to-end provider swap and migration transaction flow. |
| [src/persistence/migration/verify.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/persistence/migration/verify.py) | create | Row-count and checksum verification logic before provider cutover. |
| [scripts/db/swap_provider.py](/Volumes/claude-projects/projects/devotional-generator-system-a/scripts/db/swap_provider.py) | create | Operator CLI for `--from`, `--to`, dry-run, execute, report output. |
| [src/registry/registry.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/registry/registry.py) | modify | Refactor to delegate persistence to injected `DatabaseSocket` while preserving API. |
| [src/grounding_store/store.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/grounding_store/store.py) | modify | Keep class API but route `save/load/exists` via socket backend. |
| [src/prayer_trace_store/store.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/prayer_trace_store/store.py) | modify | Same refactor as grounding store. |
| [src/validation/orchestrator.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/validation/orchestrator.py) | modify | Resolve artifacts through socket-backed stores/configured backend. |
| [src/api/generation_pipeline.py](/Volumes/claude-projects/projects/devotional-generator-system-a/src/api/generation_pipeline.py) | modify | Build persistence from factory and inject consistently. |
| [pyproject.toml](/Volumes/claude-projects/projects/devotional-generator-system-a/pyproject.toml) | modify | Add migration and driver deps (`alembic`, `psycopg[binary]` optional). |
| [tests/persistence/test_socket_contract.py](/Volumes/claude-projects/projects/devotional-generator-system-a/tests/persistence/test_socket_contract.py) | create | Contract tests that every adapter must pass. |
| [tests/persistence/test_swap_migration.py](/Volumes/claude-projects/projects/devotional-generator-system-a/tests/persistence/test_swap_migration.py) | create | End-to-end swap tests: sqlite→postgres and sqlite→sqlite temp. |
| [tests/grounding_store/test_store.py](/Volumes/claude-projects/projects/devotional-generator-system-a/tests/grounding_store/test_store.py) | modify | Keep behavior assertions but run against socket-backed store. |
| [tests/prayer_trace_store/test_store.py](/Volumes/claude-projects/projects/devotional-generator-system-a/tests/prayer_trace_store/test_store.py) | modify | Same as above. |
| [tests/test_registry.py](/Volumes/claude-projects/projects/devotional-generator-system-a/tests/test_registry.py) | modify | Ensure dedup/override behavior still holds via socket backend. |

### 4. Implementation Details
1. Define database socket contract.
2. Implement schema and adapters.
3. Refactor existing stores/registry to socket.
4. Add provider config + factory.
5. Build swap migration command.

Pseudocode for swap orchestration:
```python
def swap_provider(from_cfg, to_cfg, dry_run=False):
    src = factory(from_cfg)
    dst = factory(to_cfg)

    manifest = src.export_manifest()  # counts + hashes per entity

    if dry_run:
        return manifest

    with dst.transaction():
        for entity in TOPOLOGICAL_ORDER:
            for batch in src.export_batches(entity, batch_size=500):
                dst.import_batch(entity, batch, upsert=True)

        verify = compare(src, dst)  # counts + checksums
        if not verify.ok:
            raise MigrationVerificationError(verify.report)

    write_active_provider(to_cfg)
    record_provider_switch(from_cfg.name, to_cfg.name, manifest, verify.report)
```

Pseudocode for dedup-safe quote insert:
```python
def record_quote_use(volume_id, series_id, quote_text, override_reason=None):
    if exists_same_volume(volume_id, quote_text) and not override_reason:
        raise DuplicateQuoteError

    if exists_other_volume_same_series(series_id, volume_id, quote_text) and not override_reason:
        raise CrossVolumeDuplicateError

    insert_quote_use(...)
```

Detailed database structure (initial unified schema):
- `series`
  - `id` PK, `title`, `created_at`
- `volumes`
  - `id` PK, `series_id` FK, `volume_number`, `title`, `parent_volume_id` FK nullable, `created_at`
  - unique: (`series_id`, `volume_number`)
- `quote_uses`
  - `id` PK, `volume_id` FK, `series_id` FK, `quote_text`, `quote_hash`, `author`, `source_title`, `publication_year`, `override_reason`, `added_at`
  - indexes: (`volume_id`, `quote_hash`), (`series_id`, `quote_hash`)
- `scripture_uses`
  - `id` PK, `volume_id` FK, `reference`, `translation`, `added_at`
  - index: (`volume_id`, `reference`, `translation`)
- `grounding_maps`
  - `id` PK, `exposition_id`, `retrieval_run_id`, `payload_json`, `created_at`, `updated_at`
- `prayer_trace_maps`
  - `id` PK, `prayer_id`, `payload_json`, `created_at`, `updated_at`
- `devotional_books` (for future FR-80/NFR-02 persistence hardening)
  - `id` PK, `series_id` FK nullable, `volume_number`, `topic`, `input_json`, `output_mode`, `created_at`, `updated_at`
- `devotional_days`
  - `id` PK, `book_id` FK, `day_number`, `day_focus`, `created_at`, `last_modified`
  - unique: (`book_id`, `day_number`)
- `section_states`
  - `id` PK, `day_id` FK, `section_name`, `approval_status`, `content_json`, `updated_at`
  - unique: (`day_id`, `section_name`)
- `section_snapshots`
  - `id` PK, `day_id` FK, `section_name`, `snapshot_slot` (1..3), `content_json`, `created_at`
  - unique: (`day_id`, `section_name`, `snapshot_slot`)
- `provider_switch_log`
  - `id` PK, `from_provider`, `to_provider`, `started_at`, `completed_at`, `status`, `summary_json`
- `schema_migrations`
  - `version` PK, `applied_at`, `checksum`

### 5. Testing Strategy
1. Contract tests:
   1. Run the same CRUD + dedup suite against each adapter.
2. Regression tests:
   1. Existing `tests/test_registry.py`, grounding/prayer store tests must pass unchanged semantically.
3. Migration tests:
   1. Seed source DB with realistic data.
   2. Migrate source→target.
   3. Verify row counts and per-entity checksums match.
   4. Verify provider config switches only after successful verification.
4. Failure-path tests:
   1. Missing source artifact.
   2. Unique constraint collision in target.
   3. Interrupted migration resumes safely.
5. Integration tests:
   1. `generate_devotional` with sqlite adapter.
   2. swap to postgres.
   3. rerun `generate_devotional`; ensure output and validation behavior unchanged.

Specific cases:
- Within-volume duplicate quote still raises.
- Cross-volume duplicate still raises unless override.
- Scripture duplicate remains warning-only.
- Grounding/prayer artifact missing ID still raises `KeyError`.
- Snapshot cap enforces max 3 per section/day.

### 6. Edge Cases & Risks
- Partial migration/cutover risk: mitigate with transaction + verify-before-switch.
- Dialect differences (SQLite vs Postgres JSON/timestamps): normalize UTC and JSON serialization.
- Large payload migration memory pressure: stream in batches.
- Concurrent writes during migration: add app-level migration lock; run in maintenance mode.
- Legacy JSON inconsistency/corruption: validate against Pydantic before import, log rejects.
- Deterministic ID collisions (`gm_`/`ptm_` short hash): keep current IDs for compatibility now; plan longer hash in a later backward-compatible migration.