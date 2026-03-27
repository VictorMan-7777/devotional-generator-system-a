---
name: Dual database architecture and NAS SQLite issue
description: Two SQLite DBs have diverged; NAS WAL locking blocks concurrent writes; supervisor auto-restarts
type: project
---

## Two divergent databases

The system has two SQLite files, both containing `excerpt_catalog` and other production tables:

1. **`data/devg_registry.sqlite3`** — originally seeded with manually indexed resources (10,141 rows as of 2026-03-20); missing `resource_acquisition_requests`, `autoresearch_experiments`
2. **`registry.db`** (project root) — the supervisor's runtime DB; contains experiment store, `resource_acquisition_requests`, all tables; only 6,749+ excerpt_catalog rows

**Why:** `.env.local` sets `DEVG_DB_PATH=/Volumes/.../registry.db`. All supervisor-run indexing goes to `registry.db`. Manual indexing runs done before `.env.local` fix went to `data/devg_registry.sqlite3`.

**Why:** The `resource_catalog` table was migrated to BOTH DBs on 2026-03-20, with `registry.db` being the authoritative one (used by supervisor at runtime).

## Project location — MacBook, not NAS (as of 2026-03-21)

The project currently lives on the MacBook. The `/Volumes/claude-projects/...` path is a MacBook-local path shared via SMB — the NAS has not received the repo yet. NAS migration is planned (see `docs/system/nas-migration-plan.md`) but deferred while current development work is in progress.

## SQLite WAL concurrent write issue

SQLite WAL mode does not work reliably over SMB mounts. When the supervisor writes to `registry.db`, concurrent writes from any other process fail with `sqlite3.OperationalError: disk I/O error`.

**How to apply:** Never run manual `DEVG_DB_PATH=.../registry.db` scripts while the supervisor is running. The DB merge must be done after the supervisor is stopped.

## Supervisor auto-restarts

The training supervisor at `scripts/autoresearch/run_training_supervisor.py` keeps restarting after being killed (PID changes from 6806 to 53656 etc.). Root cause unknown — may be a launchd agent or another process monitoring it.

## How to apply

- Do NOT attempt concurrent SQLite writes to NAS-mounted DBs
- The `resource_catalog` table is in `registry.db` — this is what the supervisor uses
- The `data/devg_registry.sqlite3` is a stale fork; its unique sources need to be merged into `registry.db` after the supervisor stops
- When diagnosing missing excerpts, check `registry.db` not `data/devg_registry.sqlite3`
