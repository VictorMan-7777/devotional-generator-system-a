---
name: Training State 2026-03-18 (Current)
description: Post-reboot. Exposition template fixed (100/100). Outliner at 615 exp / 17 passes, 100-gate governance breach. Ruth commentaries added.
type: project
---

Training loop was running as PID 13515 before reboot. Not restarted yet — operator decision on outliner ruth-1 18d wall required first.

**Why:** 100-gate governance rule (memory: feedback_training_50_100_experiments.md) requires operator decision before loop continues hammering an unsolvable wall.

**How to apply:** Do not restart training loop without confirming the ruth-1 18d outliner decision with the operator.

---

## Experiment counts (from DB before shutdown)
| Worker | Total | Passes |
|--------|-------|--------|
| exposition_writer | 1,266 | 0 (LLM scoring only; template fixed — pending re-run) |
| outliner | 615 | 17 |
| passage_researcher | 557 | 536 |
| pdf_art_director | 146 | 107 |
| pdf_layout_engineer | 22 | 19 |
| research_librarian | 184 | — |

## Graduated workers
- **PDF Layout Engineer** ✅ graduated
- **Passage Researcher** ✅ effectively passing (536/557)
- **PDF Art Director** ✅ passing (107/146)

## Exposition writer — FIXED
- `src/generation/real_section_generator.py` — `_build_exposition()` now uses `brief.focus_clause` as direct verse quote every paragraph
- Deterministic scorer: 45–55 → **100/100** across all benchmarks
- LLM trainer verification: pending (needs training loop to run an exposition cycle)

## Outliner — STALLED / 100-GATE BREACH
- 615 experiments, only 17 passes
- Root cause: ruth-1 18d = 1.22 verses/day — LLM cannot reliably produce 18 distinct outlines at this granularity
- Score ceiling: 74/85 (pass threshold is 85)
- **Operator decision pending:** defer 18d for ruth-1 / accept wall / wait for commentary re-run

## Infrastructure additions
- Two new Ruth commentaries indexed:
  - `keil-delitzsch-ruth`: 800 chunks, 236 Ruth 1 hits
  - `pulpit-commentary-ruth`: 972 chunks, 379 Ruth 1 hits
- APIs: both Claude and OpenAI have credits (confirmed 2026-03-17)

## Active bottlenecks
1. **Outliner** — 100-gate breach on ruth-1 18d, operator decision required
2. **Exposition LLM verification** — automatic on next exposition training cycle
