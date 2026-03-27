REJECTED: outliner_infeasible_threshold.py v1 — stub, and threshold direction is wrong.

1. Stub: file ends with `# Rest of file unchanged...` — not a runnable patch.

2. Threshold direction is backwards.
   Current: _INFEASIBLE_SKIP_THRESHOLD = 2 — skip if infeasible_count >= 2
   Your change: _INFEASIBLE_SKIP_THRESHOLD = 0 — skip if infeasible_count >= 0
   Since infeasible_count is always >= 0, this would mark ALL combos as permanently infeasible.
   Your goal is to ALLOW RETRYING combos that were previously skipped.
   The correct change is to RAISE the threshold (e.g., 5, 10, or 999) so fewer combos are permanently skipped.

3. _plan_week_sizes function has NameError: uses `assignments` before it is defined.

Fix: write a patch script that changes `_INFEASIBLE_SKIP_THRESHOLD = 2` to `_INFEASIBLE_SKIP_THRESHOLD = 10`
(or a value high enough that past infeasible records don't permanently block combos).
Add assert that the substitution matched exactly 1 time. Resubmit v2.
