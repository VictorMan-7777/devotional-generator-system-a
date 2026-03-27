# DevG NAS Migration Plan

## Purpose

This plan covers the post-competition migration of DevG persistence from the current local DB path to a local NAS-hosted canonical data location.

## Why this move makes sense

A NAS-hosted canonical store can improve:
- durability
- backup discipline
- centralized data location
- operational clarity for research memory, review state, and experiment history

Because DevG now keeps persistence behind the socket boundary, the migration should primarily affect configuration and adapter validation rather than core application behavior.

## Governing rule

The migration must not leak NAS/storage assumptions into generator, review, validation, or export code.

Only these layers should need awareness of the migration:
- persistence configuration
- persistence adapters
- operational runbooks
- storage validation tests

## Migration scope

Datastores expected to move:
- canonical DevG registry / persistence DBs
- review-state persistence
- autoresearch experiment ledger
- research-memory stores that are currently SQLite-backed or local-file-backed and intended to remain durable

## Risks to validate up front

### 1. SQLite locking behavior on NAS storage

Potential issue:
- network-backed filesystems can behave differently for SQLite locking and journaling than local disks

Validation required:
- concurrent write test from two DevG processes
- concurrent review edit + generator write test
- harness cleanup/reset write test
- review-save + proof-export test

Questions to answer:
- does the NAS/filesystem fully support SQLite file locking semantics?
- does WAL mode behave correctly on that mount?
- are transient lock or I/O errors materially worse than local disk?

### 2. WAL behavior

Potential issue:
- WAL can behave poorly or inconsistently on some network-mounted filesystems

Validation required:
- verify `journal_mode=WAL` persists and behaves correctly
- verify `-wal` and `-shm` sidecar behavior is acceptable on the NAS
- test fallback plan if WAL is not reliable there

### 3. Concurrent worker activity

Potential issue:
- DevG is moving toward more concurrent writes:
  - review persistence
  - autoresearch experiment logging
  - generation checkpoints

Validation required:
- verify socket write serialization still protects the system adequately
- verify retry behavior under realistic concurrent load
- verify idempotent writes remain correct when retries happen

### 4. Read/write latency

Potential issue:
- NAS latency may be higher than local disk latency

Validation required:
- compare generation checkpoint speed before and after migration
- compare review save responsiveness before and after migration
- compare harness cleanup/reset timing before and after migration

### 5. Power/network interruption behavior

Potential issue:
- NAS availability problems can create different failure modes than local disk

Validation required:
- simulate temporary NAS unavailability
- verify write failures surface clearly
- verify recovery after reconnect does not corrupt state
- verify checkpoints still protect completed work

## Preconditions before migration

1. Competition devotional and submission work are complete.
2. Current canonical DB path is backed up.
3. Socket reliability layer is already in place.
4. A staging/test NAS path is available before production cutover.
5. `data/devg_registry.sqlite3` added to `.gitignore` (stale 21 MB copy in repo; live DB is at
   `~/Library/Application Support/DevG/devg_registry.sqlite3` on the Mac Studio at ~562 MB as of
   2026-03-18). The live DB is the one to copy to the NAS — not the repo copy.
6. `DEVG_DB_PATH` confirmed as the canonical env override for DB location (verify `.env.local`
   on all machines that run the training loop before cutover).

## Migration phases

### Phase 1: Inventory and backup

1. Identify all persistence paths currently used by DevG.
2. Confirm which stores are canonical and which are temporary/test-only.
3. Create a full backup snapshot of current DBs before any path change.

Deliverable:
- inventory of persistence paths and their purpose

### Phase 2: Staging-path validation

1. Point DevG config to a staging NAS DB path.
2. Run focused persistence tests.
3. Run generation, review, and export smoke tests.
4. Run a harness case against the staging NAS path.

Pass criteria:
- no unexpected lock errors
- no unacceptable latency regressions
- review and export remain correct

### Phase 3: Concurrency and durability validation

1. Run concurrent write scenarios deliberately:
- review save + generation checkpoint
- autoresearch ledger write + review save
- harness cleanup + generation write
2. Validate WAL sidecar behavior.
3. Validate retry/serialization behavior under pressure.

Pass criteria:
- transient errors are rare and recoverable
- no data corruption
- no duplicated records from retries

### Phase 4: Controlled cutover

1. Freeze writes briefly if needed.
2. Copy canonical DBs to the NAS production path.
3. Repoint `DEVG_SQLITE_PATH` / persistence config.
4. Run post-cutover smoke tests.

Pass criteria:
- DevG reads and writes only through the NAS path
- review, generation, and harness flows still work

### Phase 5: Post-cutover observation

1. Monitor write failures and retry frequency.
2. Monitor review responsiveness.
3. Monitor harness and checkpoint performance.
4. Confirm backups for NAS-hosted DBs are working.

## Recommended validation scenarios

1. Fresh devotional generation to review stage
2. Review edit persistence through the socket
3. Reviewed-proof PDF generation from approved review state
4. Harness case with post-run reset
5. Autoresearch ledger writes during active generation/testing
6. Recovery after a forced interrupted write scenario

## Configuration notes

Expected configuration touchpoints:
- `DEVG_DB_PATH` (canonical override in `src/persistence/paths.py::default_registry_db_path()`)
- any future per-component provider/path overrides

The application code should not require broader changes if the socket boundary remains intact.

## Success definition

The NAS migration is successful when:
- DevG uses the NAS-hosted canonical DB path through the socket boundary
- concurrent writes remain reliable
- review/generation/export responsiveness stays acceptable
- WAL/locking behavior is proven safe or a documented fallback is in place
- no direct DB assumptions were added to feature code during migration
