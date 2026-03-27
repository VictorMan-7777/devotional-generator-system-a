FEEDBACK: dashboard_db_schema — APPROVED (Step 1 of 3)

Migration applied. Table created in registry.db. Your reasoning was correct: the monitor hangs because nw_c() stats 5,000 files over SMB; storing cycle summaries in DB eliminates that.

**What was right:**
- IF NOT EXISTS guard — safe to re-run
- Correct DB path via repo_root
- Fields cover what the monitor needs (bottleneck, pass rates, alerts)

**What is still required (do not close this in QUEUE.md until all three are done):**

Step 2 — At the end of each supervisor cycle, INSERT a row into supervisor_cycles.
Where: run_training_supervisor.py (or wherever the supervisor cycle concludes).
Fields to populate: started_at_utc, completed_at_utc, bottleneck_worker, outliner_consec_passes, outliner_status, expo_experiment_count, be_still_benchmark_score, action_benchmark_score, worker_alerts_json.
This must happen every cycle, even failed ones.

Step 3 — Rewrite devg_web_monitor.py to query supervisor_cycles ORDER BY id DESC LIMIT 1.
The nw_c() function must not call os.path.getmtime() or glob over docs/system/outputs/.
The monitor is currently stopped. Do not restart it until step 3 is complete.

Submit step 2 and step 3 as separate proposals. Each must be a runnable .py file.
