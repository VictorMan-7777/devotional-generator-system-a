**Worker:** outliner

**Why:** Flat 100+ experiments (939 total, 137 passes 14.6%, consecutive passes 3/100 threshold), trainer reports 3/3 failing drills repeat despite cycle pass (sup 2026-03-24__083811, cycle 074424 status=pass but sup flags 0/3), bottleneck blocking downstream (training_order librarians->outliner). Recent day 32 passes healthy throughput but consec low plateau. Code sound (agent assigns, store logs), trainer LLM codex plateau proposals claude pending Claude CLI.

**Evidence:** sup cycle "latest_outline_training_cycle_passes=0/3" DB query totals 939/137 consec3, interventions claude pending no halt.

**Resume:** post claude trainer switch verified (consec passes >10, trainer clean cycle) or proposals applied supervisor cycle returncode0 no stall-report.