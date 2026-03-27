---
name: Competency-Based Graduation Design
description: Operator-approved architectural decision to replace binary streak-based graduation with per-competency tracking so new requirements on graduated workers don't get skipped
type: project
---

Operator approved replacing the binary graduation model (streak ≥ threshold → frozen) with competency-based graduation (per-assignment-ID pass tracking).

**Why:** As the system adds features (Day 7 template, named destinations, AC scoring, future PRD additions), any requirement added after a worker graduates is permanently skipped by the current `if not worker_graduated` gate. The PDF layout engineer was the first case — graduated before Day 7 layout and named destinations were added to the training queue.

**Design approved:**
- New DB table: `worker_competencies (worker_name, assignment_id, status, last_passed_at, last_verified_at)`
- Training agents query this table per assignment ID — generate if no pass row exists
- "Fully graduated" = all defined assignment IDs have `status='pass'`
- New assignment IDs automatically show as "pending" for all workers
- Migration: pre-seed existing graduated workers so they don't retrain from scratch

**Regression prevention (operator requirement):**
- Assignment budget (3 per cycle) fills with unmet competencies FIRST
- If budget remains after all unmet are queued → spot-check the passed competency with oldest `last_verified_at`
- Spot-check failure → `status='fail'`, competency re-enters Priority 1 next cycle
- Worker with 3/5 passed: all 3 budget slots go to the 2 unmet — no spot-checks until gap is closed
- Rule: focused on gap first, regression guard only when nothing left to close

**How to apply:**
- PDF training agent is the first implementation (Day 7 + named destinations are the immediate trigger)
- Validate the pattern on pdf_training_agent.py before expanding to other agents
- Other agents (outliner, exposition, etc.) use different graduation logic and get separate proposals
- Grok is designing the proposal; Claude applies it
