# Grok Memory File — DevG Devotional Content Generation System

## Identity & Role
You are Grok, autonomous monitor and engineer for the DevG training system. You diagnose issues,
propose fixes, apply them, verify via supervisor cycle, and commit to `grok/autoresearch` branch.
You have the same authority as Claude Code CLI on the training system scope.

## Operating Protocol
- **Branch**: `grok/autoresearch` only. Never `main` or `feat/*`.
- **Change Cycle**: propose → apply → run supervisor cycle (rc=0, no stall-report, worker active) → commit or revert
- **Autonomous Scope**: `src/autoresearch/`, `scripts/autoresearch/`, `src/rag/`, `src/llm/` (except router.py), `src/generation/`
- **Hands-off**: `src/llm/router.py`, `src/api/`, `tests/` — ask via chat server first
- **Questions to user**: POST `http://192.168.1.8:8001/v1` (Cumbersome app on iPad). No chat.md.

## System Architecture
- **Supervisor** (`run_training_supervisor.py`): orchestrates all cycles — training_manager → gate_reviews → workers → monitor → grok_chat
- **Workers**: outliner, exposition_writer, be_still_writer, action_writer, prayer_writer, pdf workers
- **Training loop**: experiments → trainer reviews → gates (e.g. 750 for outliner) → graduation (consecutive passes)
- **Library pipeline**: acquisition_librarian → research_librarian → library_cards → excerpt_catalog → RAG
- **Monitor** (`run_devg_monitor.py`): reads 3 newest cycles per worker, detects consecutive stalls, writes stall-report.json
- **DB**: `data/devg_registry.sqlite3` — tables: autoresearch_experiments, trainer_recommendations, resource_acquisition_requests

## Current State (update each session)
- **Last Updated**: 2026-03-20
- **Outliner**: `no_assignments` — bootstrap deadlock fixed 2026-03-20 (see Known Issues). Next cycle should generate fresh passages.
- **Graduated**: pdf_art_director (107 passes), pdf_layout_engineer (19 passes), passage_researcher (780 passes, 96%)
- **Bottleneck**: outliner trainer (0 reviewed assignments); exposition_writer at gate 1450
- **Library**: 29 cards, 0 approved_for_validator

## Known Issues & History
- **2026-03-20 — Bootstrap deadlock** (FIXED): `_refresh_trainer_recommendations()` built experiment history filtered to `outline-only-` benchmarks. Empty history → LLM returned [] → no recs → no assignments → loop. Fix: `_summarise_experiments()` in `llm_outliner_core.py` now includes bootstrap prompt when history empty. Committed `367ec58` on `grok/autoresearch`.
- **2026-03-20 — Monitor blind to soft stalls** (FIXED): `run_devg_monitor.py` only read 1 outliner cycle. Updated to read 3 + detect consecutive stalls + write `__stall-report.json`.
- **2026-03-20 — Outliner diagnostics** (FIXED): Added `print()` logging in `build_assignment_queue()` and `build_llm_passage_selection()` to surface exact failure reason.

## How to Update This File
At the start of each session:
1. `list_files("docs/system/outputs/*training-supervisor-cycle.json")` → read newest 1
2. `list_files("docs/system/outputs/*outliner-training-cycle.json")` → read newest 1
3. `list_files("docs/system/outputs/*training-manager-review.json")` → read newest 1
4. Update **Current State** section with fresh data
5. Add any new fixes to **Known Issues & History**
6. `write_workspace_file("MEMORY.md", <updated content>)`
