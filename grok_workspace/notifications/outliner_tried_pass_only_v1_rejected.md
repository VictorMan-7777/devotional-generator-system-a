REJECTED: outliner_tried_pass_only.py v1 — stub (file incomplete).

1. Ends with `# Rest of file unchanged...` — not a complete replacement. Cannot apply.

2. Also: `_INFEASIBLE_SKIP_THRESHOLD = 2` is unchanged in this version, which is now moot
   since `outliner_infeasible_threshold_v2.py` was approved and the threshold is now 10.

3. The infeasible threshold fix is now live. Wait one full outliner cycle to see if assignments
   generate before proposing further changes to `_tried_outline_benchmarks()`.

Do not submit the "pass only" variant until the threshold fix has had a chance to run.
