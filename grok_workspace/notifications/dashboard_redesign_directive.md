# Dashboard Redesign — Directive from Operator

**Priority: High. The web monitor is currently stopped.**

## What broke and why

`scripts/devg_web_monitor.py` hangs uninterruptibly (UN state) on every startup. Root cause: the `nw_c()` helper globs `docs/system/outputs/` and sorts results by `os.path.getmtime()`, which calls `stat()` on every matching file over SMB. That directory now has ~5,000 files. At scale, the stat calls over SMB take longer than the refresh interval and eventually hang the entire process in uninterruptible I/O wait.

This is not a patch problem. The operator's diagnosis: **this is a design issue that wasn't considered — the monitor worked at launch but the design doesn't hold as the pipeline accumulates output files.**

## What the redesign must solve

The monitor cannot depend on globbing a growing flat directory over SMB for any performance-critical read. As the pipeline runs indefinitely, the outputs directory will only grow larger.

## Required changes

**1. Store supervisor cycle summary in the DB**

Each supervisor cycle currently writes a large JSON blob to `docs/system/outputs/`. Add a lightweight DB write at the end of each supervisor cycle that persists the key summary fields to a `supervisor_cycles` table:

```sql
CREATE TABLE IF NOT EXISTS supervisor_cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at_utc TEXT,
    completed_at_utc TEXT,
    bottleneck_worker TEXT,
    outliner_grade TEXT,
    exposition_grade TEXT,
    be_still_benchmark_score INTEGER,
    be_still_benchmark_status TEXT,
    action_writer_benchmark_score INTEGER,
    action_writer_benchmark_status TEXT,
    worker_alerts_json TEXT,  -- compact JSON of alert messages
    created_at TEXT DEFAULT (datetime('now'))
);
```

The full JSON file continues to be written for audit trail. The DB row is the fast-access path.

**2. Rewrite the monitor to query the DB**

Replace all `nw_c()` + file-read patterns in the monitor with `sqlite3` queries against the DB:
- Pass rates → already in `autoresearch_experiments`
- Latest supervisor summary → `supervisor_cycles` table (new)
- File modification times for "last updated" display → query `created_at` from DB, not `stat()` on SMB

The monitor should need zero `glob.glob()` calls against `docs/system/outputs/`. If it needs to display a filename, it reads the filename from the DB row, not from the filesystem.

**3. Outputs directory management**

The outputs directory has no retention policy. Either:
- Add a post-cycle cleanup that moves files older than 7 days to `docs/system/outputs/archive/`, OR
- Keep files forever but ensure nothing performance-critical reads them by filename scan

The monitor redesign (item 2) makes the directory size irrelevant to dashboard performance. The cleanup is optional hygiene.

## Deliverable

A proposal consisting of:
1. A migration script or schema change that adds `supervisor_cycles` to the DB
2. Modified `run_training_supervisor.py` (or wherever the cycle finishes) to write the summary row
3. Rewritten `scripts/devg_web_monitor.py` that queries the DB

The current monitor is stopped. Until your proposal is applied, the dashboard is dark. This is the blocker.

## What not to do

- Do not patch `nw_c()` to use `max()` instead of sort-by-mtime. That's still a glob over 5,000 files.
- Do not archive old output files as a fix. The history must remain accessible to training agents that glob for historical cycles.
- Do not add a timeout wrapper around the glob. That silently drops data.
