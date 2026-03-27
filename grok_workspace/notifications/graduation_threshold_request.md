# Request: Propose Outliner Graduation Threshold

## Context

The outliner currently has no graduation threshold — the gate system (every 50 experiments) provides check-ins only. The monitor now shows streak and gate info, but the "graduation" target is missing. We need a specific consecutive-pass threshold to add to `_check_graduation_candidates()` in `training_manager.py` so the supervisor gets a graduation signal.

## Current Outliner State

- Total experiments: 857 (605 fail, 68 pass, 146 revise, 31 task_infeasible, 6 completed, 1 test)
- Current consecutive pass streak: 39
- Current gate: 850, next gate: 900
- Last cycle: PASS (score=100, Jeremiah 1-10)
- Trainer cycle status: consistently pass with score=100 x3/3 recent

## Comparable Worker Thresholds (for context)

| Worker | Threshold | Nature | At graduation |
|--------|-----------|--------|---------------|
| pdf_layout_engineer | 10 consecutive | Simple layout rules | 10/22 total, streak=7 |
| pdf_art_director | 25 consecutive | More complex design rules | 107/146 total, streak=0 (oscillating) |
| passage_researcher | 200 consecutive | Research quality | 915/936 total, streak=300+ |

## The Question

The outliner is the most critical worker — it gates all downstream training. It produces theological outlines from scripture passages.

**Task:** Propose a graduation threshold for the outliner. Specifically:
1. What consecutive-pass count should trigger a graduation signal?
2. What does "graduated" mean for the outliner — full release to downstream training, or something narrower?
3. Where to add it: `_check_graduation_candidates()` in `src/autoresearch/training_manager.py` and optionally a constant in `src/autoresearch/outliner_training_agent.py`

## What graduation should NOT mean

The outliner's "pass" experiments are currently on easier/mid passages. The harness passages (luke-15, acts-9, exodus-19-20) have had prior failures. Graduation should probably require evidence of broad passage coverage, not just streak on easy passages.

## Proposal Expected

Write your proposed threshold (and rationale) to:
`grok_workspace/proposals/outliner_graduation_threshold.md`

Include:
- The threshold number and why
- Whether a broader coverage check is needed (or if streak alone is sufficient)
- The exact code change needed (constant definition + `_check_graduation_candidates` entry)
