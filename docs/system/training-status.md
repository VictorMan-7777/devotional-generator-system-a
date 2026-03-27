# Training Status
_Auto-updated. Last: 2026-03-18 (session 2)_

## Training Loop
- **PID:** 6463 — running (`logs/training-loop-20260318.log`)
- **Branch:** `feat/phase-014-rag-infrastructure`
- **API limits:** Anthropic ~82% weekly (resets Sun). OpenAI: active.
  Workers use OpenAI (DEVG_LLM_PROVIDER=codex). Trainers use Claude (CROSS).

---

## Worker Status

| Worker | Exps | Pass | Status | Notes |
|--------|------|------|--------|-------|
| outliner | 616 | 17 | 🔴 BOTTLENECK | 100-gate breach. Trainer upgraded: infeasibility detection + stall strategy. New Ruth commentaries indexed. |
| exposition_writer | 1,266 | 0 | 🟡 PENDING VERIFY | Template fixed (100/100 det. score). Awaiting first LLM-verified pass. Running in parallel now. |
| passage_researcher | 557 | 536 | ✅ GRADUATED | 444 consecutive passes (threshold 200). `trained_enough_for_support`. |
| pdf_art_director | 146 | 107 | 🟢 PASSING | 73% pass rate. Monitoring. |
| pdf_layout_engineer | 22 | 19 | ✅ GRADUATED | No further training needed. |
| be_still_writer | 0 | 0 | 🔵 STARTING | Training agent exists. Now runs every cycle (not just when bottleneck). |
| action_writer | 0 | 0 | 🔵 STARTING | Training agent exists. Now runs every cycle. |
| prayer_writer | 0 | 0 | 🔵 READY | Training agent created. Activates next supervisor cycle automatically. |
| research_librarian | 184 | — | 🟢 RUNNING | Continues passively each cycle. |

---

## Changes This Session (2026-03-18, session 2)

### Outliner trainer upgrades (`src/autoresearch/llm_outliner_core.py`)
- Task feasibility verdict: `task_infeasible` status when assignment is structurally impossible (e.g. 18d/Ruth 1 = 1.2 verses/day)
- Stall detection: trainer sees full benchmark history, must recommend strategy change after flat scores
- 500-word downstream exposition constraint: trainer understands infeasible outlines corrupt the full pipeline
- `_recent_attempts_for_benchmark()` in training agent filters by passage + template, excludes task_infeasible records

### Supervisor (`scripts/autoresearch/run_training_supervisor.py`)
- be_still + action_writer now run **every cycle** (not gated on training_manager's active_training set)
- exposition_writer runs every cycle in parallel with outliner bottleneck
- prayer_writer added to plan when its script exists

### Cover designer (`src/api/cover_export.py`) — NEW
- `generate_cover_for_book(book, *, output_dir, title, subtitle, author, blurb)`
- Generates all 3 KDP concepts (Shepherd's Rest / Still Waters / Sanctuary)
- Returns `{design_id: {png: Path, pdf: Path}}`
- Usage: call after `generate_devotional()` with an output directory

### 50-experiment gate review system — NEW
- `src/autoresearch/llm_gate_review_core.py` — gate detection + LLM meta-evaluation
  - `pending_gate_reviews(workers)` — returns which workers have crossed a new gate
  - `run_gate_review(worker, gate)` — calls trainer LLM for full history meta-eval; detects insanity loops; outputs `gate_verdict` (on_track / stalled / insanity_loop), `root_cause`, `structural_changes`, `priority_intervention`
  - Logs result as experiment record (`benchmark_name="gate-review-{N}"`) so it won't re-run
- `scripts/autoresearch/run_gate_reviews.py` — run script; outputs gate-reviews.json
- Supervisor: `gate_reviews` step added to every plan (before worker cycles)
- Training manager: `experiment_gate_status` field added to review output
- **Both outliner (gate 600) and exposition_writer (gate 1250) have pending reviews — will fire next supervisor cycle**

### Passage researcher graduation fix (`src/autoresearch/training_manager.py`)
- `_review_passage_researcher()` now checks streak against threshold first; returns `trained_enough_for_support` at 444 consecutive passes (threshold 200)
- `list_experiments` import added (was missing from store import)

### Acquisition librarian wired (`scripts/autoresearch/run_acquisition_librarian_cycle.py`) — NEW
- Processes ALL pending requests (`status="requested"`) regardless of `requested_by` (previously only handled `research_librarian` requests, missed outliner requests)
- Added to supervisor `_step_plan()` — runs every cycle after `research_librarian`, before `passage_researcher`

### Prayer writer training — COMPLETE
- `src/autoresearch/llm_prayer_writer_core.py` — seminary professor/pastoral theologian persona, 8-criterion deterministic pre-check, LLM trainer
- `src/autoresearch/prayer_writer_training_agent.py` — agent (5 fresh benchmark passages)
- `scripts/autoresearch/run_prayer_writer_training_cycle.py` — run script
- Auto-activates in supervisor next cycle via script-existence check

---

## Governance Issues

| # | Issue | Status |
|---|-------|--------|
| 1 | Outliner 100-gate breach (615+ exp, ruth-1 18d infeasible) | ✅ Trainer now auto-flags as `task_infeasible` — no operator decision needed |
| 2 | Exposition LLM verification | ⏳ Automatic next exposition cycle |
| 3 | Trainer biblical scholar audit (several agents not updated) | 🔲 Pending |
| 4 | Acquisition librarian competence unverified | ⏳ Now wired into supervisor every cycle. Pending first observed acquisition output. |
| 5 | Pipeline/training docs update | 🔲 Operator deferred to Monday |

---

## Log Tails (check anytime)
```bash
tail -50 logs/training-loop-20260318.log
tail -50 logs/training-loop-20260318.log | grep -E "pass|fail|revise|infeasible|score"
```
