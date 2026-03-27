---
name: Log Grok proposal reviews to autoresearch_experiments DB
description: After every Grok proposal review, log the cycle to the DB using log_worker_experiment.py with worker_name=grok_supervisor
type: feedback
---

Every Grok proposal review is a training cycle and must be logged to `autoresearch_experiments` just like other workers. Use the existing script:

```bash
python3 scripts/autoresearch/log_worker_experiment.py \
  --experiment-id <uuid> \
  --worker-name grok_supervisor \
  --benchmark-name <category> \
  --benchmark-reference <proposal_stem> \
  --run-slug <proposal_stem>-<YYYYMMDD> \
  --status <pass|fail> \
  --attempted-change "<one-line summary of what Grok proposed>" \
  --learning-note "<Claude's feedback>" \
  --keep-decision <approved|rejected|approved_with_corrections> \
  --metric reasoning_quality=<0-10> \
  --metric approved=<true|false> \
  --metric hallucination_detected=<true|false>
```

**benchmark_name categories:**
- `trainer_switch` — Grok proposes switching a worker's trainer API
- `code_fix` — Grok proposes a code change to a worker or harness
- `diagnosis` — Grok produces a diagnosis/analysis without a code change
- `monitor_update` — Grok proposes a dashboard or monitoring change

**status:**
- `pass` — reasoning was sound, evidence-based, showed good analytical judgment
- `fail` — reasoning was weak, hallucinated data, missed obvious evidence, or wrong diagnosis

**Why:** Grok's training trajectory must be measurable the same way other workers are measured. Pass rates, trajectory, and learning notes feed back into evaluating whether Grok is improving as a supervisor.

## Trainer interaction logging (Grok's responsibility)

Grok also logs every significant Grok↔trainer interaction using `worker_name=trainer_<name>` (e.g., `trainer_outliner`, `trainer_exposition_writer`). This covers:
- Trainer flags raised and Grok's directive responses
- Feedback or directives Grok issues to a trainer
- Outcome verification after a directive

**Claude's role:** Review `trainer_<name>` experiment logs periodically to assess whether trainers need updates — prompt changes, difficulty adjustments, or API switches. Nothing should happen between Grok and trainers without a log entry Claude can inspect.

**Operator does NOT need trainer interaction details.** Operator monitors the system as a whole — are cycles happening, are there gaps, is it improving. The human dashboard (port 8765) should show only the timestamp of last Grok-trainer interaction per worker card. Claude monitors the details.

benchmark_name categories for trainer logs: `trainer_flag_response`, `trainer_directive`, `trainer_feedback_review`
keep_decision values: `effective` / `ineffective` / `pending`
