# Restart Handoff — 2026-03-27

**Written by:** Claude (outgoing instance) before clean shutdown
**For:** Next Claude instance on restart
**Project path:** `/Volumes/claude-projects/projects/devotional-generator-system-a/`

---

## Read This First

Your memory is in the repo at `docs/system/claude-memory/`. Start by reading `docs/system/claude-memory/MEMORY.md` to load context on the operator, project, Grok's role, and all working rules. Also read `CLAUDE.md` in the project root.

---

## Why We Stopped

Clean shutdown before Mac Studio + MacBook restart (pending OS updates). The operator also wants a **full code review** to identify accumulated bandaids before resuming training. Do not restart the supervisor until the operator confirms they want to.

---

## System State at Shutdown (2026-03-27 ~18:10 UTC)

### Processes — all stopped cleanly before reboot
- **Supervisor** (`run_grok_supervisor.py`) — was running PID 82415, stopped
- **Dashboard** (`dashboard_v4_server.py`) — was running, stopped
- **DB** — `registry.db` in project root, assigned=0 (all stalled rows archived before shutdown)

### Worker Pass Rates (last-50 at shutdown)
| Worker | Passes/50 | Rate |
|---|---|---|
| outliner | 35 | 70% |
| prayer_writer | 23 | 46% |
| action_writer | 13 | 26% |
| exposition_writer | 11 | 22% |
| be_still_writer | 10 | 20% |
| passage_researcher | 50 | 100% |
| pdf_art_director | 50 | 100% |

**Note:** Fast worker rates (action/be_still/prayer) collapsed today due to 3 supervisor freeze/stall cycles that flooded the DB with archived rows. Pre-stall rates were action 38%, be_still 18%, prayer 42%. Real quality signal is obscured.

---

## Known Issues / Bandaids (Code Review Starting Point)

### Critical — fix before resuming training

1. **SQLite over SMB** (`registry.db` on MacBook, accessed by Mac Studio via SMB)
   - Root cause of: dashboard DB I/O errors, WAL lock contention, supervisor freezes
   - Bandaid in place: dashboard now copies DB to `/tmp/devg_dashboard_cache.db` before reading
   - Real fix: move `registry.db` to local storage on Mac Studio (NAS migration path)

2. **Recurring supervisor freezes**
   - Supervisor froze 3× today (70+ min each), 0% CPU, no worker subprocesses
   - `execute_actions()` has per-action TimeoutExpired catch but supervisor still hangs
   - Likely: a subprocess call blocks at OS level before Python timeout kicks in
   - No root cause confirmed — needs investigation

3. **Worker stall pattern**
   - Workers assigned rows that never complete; we archive them manually/periodically
   - `archive_stalled_assignments.py` treats symptom but not cause
   - Why workers time out mid-cycle is unknown

4. **be_still_writer underperforming**
   - Last-50 rate 18-20% vs action 38%, prayer 42%
   - Root cause undiagnosed — Grok was asked in `grok_workspace/chat.md` (~16:15 UTC) but never answered
   - Check `grok_workspace/chat.md` tail for response after restart

### Known debt (not urgent)

5. **Dashboard `DB_PATH`** uses relative `'registry.db'` and `'grok_workspace/TODO.md'` — only works if server launched from project root

6. **Hardcoded paths** — audit all scripts for hardcoded `/Volumes/...` paths before NAS migration

7. **`data/devg_registry.sqlite3`** — stale fork of runtime DB, not used at runtime, merge pending

8. **Frozen metrics** — spec exists at `docs/system/frozen-metrics-spec.md`, never implemented. Per CLAUDE.md, training is officially stopped until this is done.

9. **Competency-based graduation** — operator-approved design, never implemented

10. **`research_librarian` 0% pass rate** (0/50) — not investigated

---

## Pending Items (Grok)

- `grok_workspace/chat.md` has an unanswered `[Q]` about be_still_writer root cause diagnosis (~16:15 UTC 2026-03-27). Check on restart.
- `grok_workspace/proposals/fast_worker_fail_analysis.md` — planning stub, no .py yet
- `grok_workspace/proposals/reset_stalled_assignments.py` — moot, can be deleted

---

## Restart Sequence (when operator confirms ready)

```bash
# 1. Archive any stalled rows (will be stale after reboot)
python3 scripts/autoresearch/archive_stalled_assignments.py

# 2. Start dashboard (read-only, safe to start first)
nohup python3 scripts/dashboard_v4_server.py >> logs/dashboard.log 2>&1 &

# 3. Start supervisor (only after operator confirms code review done)
nohup python3 scripts/autoresearch/run_grok_supervisor.py >> logs/supervisor.log 2>&1 &
```

---

## Memory Location

Operator preference: keep Claude memory in the repo, not on Mac Studio local filesystem.
Memory files: `docs/system/claude-memory/` (all 52 files copied here 2026-03-27)
Index: `docs/system/claude-memory/MEMORY.md`

On NAS migration: memory travels with the repo automatically.
On new Claude instance: read `docs/system/claude-memory/MEMORY.md` first, then this file.
