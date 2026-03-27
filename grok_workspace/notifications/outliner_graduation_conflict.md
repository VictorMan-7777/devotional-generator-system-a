DIRECTIVE: Outliner graduation vs bottleneck contradiction — investigate and resolve

Latest cycle (2026-03-24T00:57Z) shows a logic conflict you need to diagnose:

graduation_monitoring says:
  worker_name: outliner
  consecutive_passes: 106
  graduation_threshold: 100
  status: graduated

But the same cycle also shows:
  current_bottleneck_worker: outliner
  reviews[outliner].status: active_bottleneck
  expert_outliner_trainer: "reviewed_assignments=3, failed_assignments=3"
  expert_outliner_trainer advice: "Keep the outliner on outline-only drills until the latest trainer cycle is clean."

Today's outliner drills returned 3/3 PASS at 100/100 (1 Peter 1-5, Amos 1-9, Luke 1-4).

Your own monitor (grok-outliner-monitor) separately notes:
  "Outliner has improved on broad non-harness passages (recent 97% pass rate) but remains stuck on Exodus 19-20 (validation_failed) and Luke 15/Acts 9 (partial)"

The contradiction: graduation_monitoring says graduated (threshold met), but the training manager still lists it as active_bottleneck, and the expert trainer reports 3 failed drills.

What you need to answer:
1. Are the 106 consecutive passes counting non-harness passages only? If so, is graduation on non-harness passes premature while harness drills still fail?
2. Is the expert_outliner_trainer evidence from this cycle or stale?
3. What is the correct graduation criterion: consecutive passes on any passage, or consecutive passes including all harness passages?
4. If graduation stands — what is the next bottleneck worker, and does the training order need to update?

Do not change the graduation logic or bottleneck flag yourself. Write a diagnosis to grok_workspace/notifications/outliner_graduation_resolution.md with your answers and a recommendation. I will decide.
