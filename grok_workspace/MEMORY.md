# Persistent Memory — Updated 2026-03-27T12:00 UTC

## STANDING REQUIREMENT: Maintain TODO.md every cycle (grok_workspace/TODO.md)

## DB State (LIVE)
**Totals excl. archived/others:**
- exposition_writer: 2020 total (24 pass ~1.2%)
- passage_researcher: 975 (893 pass ~92% GRADUATED)
- outliner: 940 (137 pass ~15%)
- be_still_writer: 794 (57 ~7%)
- prayer_writer: 780 (71 ~9%)
- action_writer: 767 (78 ~10%)
- pdf_art_director: 146 (107 ~73%)
**Assigned Backlog**: 270 stalled (90 each fast worker: prayer/be_still/action on Luke 15 refs, ~22h old).
**Fast workers**: Low passes; stalls blocking new assigns. Archive script ready: scripts/autoresearch/archive_stalled_assignments.py
**Stalls**: No completes post-09:36 UTC pre-restart; post-restart pending.

## Pending Proposals
- Fast worker fail analysis (propose logs/files for score/benchmark_ref)

## Completed Fixes
- dashboard_v4_server.py deployed
- supervisor changes applied & RESTARTED (PID 52467, tmux devg-supervisor)
- exposition floor fix

## Current Priority (post-restart)
**Supervisor auto-prio via TODO.md**
1. Archive stalls → clear fast backlog.
2. Fast workers FIRST: debug low pass (analysis needed).
3. exposition/outliner LAST.

## Item 1 Findings (Updated)
Stalled 270 confirmed (all >1h). Archive to unblock. Post-archive: monitor new assigns/passes.