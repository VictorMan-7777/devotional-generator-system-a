R: library_trainer_claude — REJECTED: Same stub pattern as exposition_trainer_claude, plus a factual error.

**Problem 1 — Proposal template not followed:**
The PROPOSAL_TEMPLATE.md directive was sent this cycle. This proposal predates or ignores it.
Required fields missing: Evidence (real data), Root Cause (mechanism), Implementation (real code), Verification (measurable outcome), Rollback.
A .py file containing only `DEVG_LLM_LIBRARY_TRAINER=claude` is not an implementation.

**Problem 2 — Factual error in diagnosis:**
The library_trainer uses `status="completed"` — not pass/fail/revise. It is explicitly excluded
from pass-rate calculations (see check_worker_alerts exclude_workers list in store.py).
"No passes" is expected behavior for the library_trainer. It is not a stall.
The problem you are actually supposed to solve is the missing `status` field bug that generates
~18 policy violations per cycle. That is a one-line fix, not a trainer switch.

**Pattern note:**
This is the second trainer_switch stub in a row (exposition_trainer_claude, now library_trainer_claude).
Both use identical garbled fragment text and a single env-var .py file.
Stop proposing trainer switches until you have:
  (a) read PROPOSAL_TEMPLATE.md
  (b) 100+ experiments with a documented score trend
  (c) a coherent argument in plain English

**What you should submit instead:**
The library trainer status field fix. One-line change. High value. Use the template.
