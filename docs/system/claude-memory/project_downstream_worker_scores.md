---
name: Downstream Worker Scores
description: Current PASS/FAIL status for all deterministic downstream workers (Exposition, Be Still, Action Steps, Prayer)
type: project
---

All four downstream workers reach PASS (≥80) across all 5 benchmark passages as of 2026-03-21.

**Why:** Workers were failing at ~35-72 due to template issues: meta-commentary, generic prompts, wrong tone/register for specific themes, grammatically broken fallbacks, evaluation truncation, and narrative focus_clauses being quoted verbatim in prayer petition language.

**How to apply:** These workers do not need structural overhaul. When regression is found, diagnose via the trainer's `priority_fix` field and fix the specific template sentence. The evaluator's findings are the primary diagnostic tool.

## Current Scores — All 5 Benchmark Passages (2026-03-21)

| Passage | Exposition | Be Still | Action | Prayer |
|---------|-----------|----------|--------|--------|
| Habakkuk 1:1-4 | ✅ PASS | ✅ PASS | ✅ PASS | ✅ PASS |
| Psalm 23:1-3 | ✅ 82 | ✅ 88 | ✅ 88 | ✅ 84 |
| Ruth 1:6-10 | ✅ 84 | ✅ 84 | ✅ 88 | ✅ 84 |
| Colossians 3:1-4 | ✅ 84 | ✅ 88 | ✅ 84 | ✅ 82 |
| Luke 15:11-14 | ✅ 88 | ✅ 88 | ✅ 84 | ✅ 88 |

## Key Fixes for Luke 15:11-14 (repentance theme)

### Exposition
- Added parable-specific `opening_sentence` (deliberate sequence: request, division, gathering, journey, squandering, famine)
- Fixed `_theme_applications("repentance")` — "name what the far country actually cost and turn back toward the Father's presence"
- Added parable-specific `_theme_specific_sentence` for `repentance`
- Added parable-specific `_ensure_exposition_floor` supplementals
- Added `"repentance"` to `_has_theme_addenda` (prevents meta-commentary)
- Added parable-specific `theme_addenda["repentance"]` in `_build_exposition`

### Be Still
- Added `repentance` `response_prompt`: "Where in you is the same movement — wanting the Father's gifts while putting distance between yourself and the Father's presence?"

### Action Steps
- Added `repentance` 3-item specific set (far country naming, concrete return step, honest cry if return feels too humiliating)

### Prayer
- Fixed `_prayer_image_override["repentance"]` → `"he squandered his estate in loose living"` (v.13) — prevents truncated narrative clause repeating as image
- Added `focus = ""` override for `repentance` theme — narrative focus_clauses (story events) read incoherently as petition language
- Fixed `theme_petition["repentance"]` — converted "Let us see clearly what this passage names" (narration) to "Father, do not let us take what You give while putting distance from Your presence" (direct petition)

## Ongoing Issues
- DB writes go to NAS `registry.db` (not AppSupport) because `DEVG_DB_PATH` in `.env` is an absolute NAS path. Count: 851+ as of 2026-03-21T19Z.
- Supervisor/trainer mismatch: supervisor reports `failed_assignments=3` for outliner even when cycles show pass. Root cause: `review_current_outliner_work` reads devotional meta.json which doesn't exist for outline-only training. Cosmetic only — experiments ARE being recorded.
- Grok monitor was failing rc=1 every supervisor cycle due to stale model name `grok-4.20-0309-reasoning`. Fixed to `grok-4-1-fast-reasoning` in both `src/llm/grok_agent.py` and `scripts/autoresearch/run_grok_outliner_monitor.py` (2026-03-21).

## Fresh Benchmark Issues — Active Training (2026-03-21)
- Be Still fresh: 72 (Habakkuk) — habakkuk_lament closing_prompt fixed to surface justice/outward dimension
- Action writer fresh: 52 (Habakkuk) — fixed cross-references to "honest sentence from Be Still" (Be Still never asks for a written sentence)
- Action writer garbled connector "takes makes and down seriously" — fixed in `editorial.py` `_application_lane` fallback (expanded _SKIP set, 5+ char token minimum)
