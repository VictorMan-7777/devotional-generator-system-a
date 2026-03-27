---
name: 50-100 experiment training decision points
description: After 50 experiments check for improvement; at 100 experiments a hard decision is required (graduate/change approach/escalate)
type: feedback
---

For each worker, improvement must be visible within 50-100 experiments. These are hard decision gates, not suggestions.

- **50-experiment check:** trainer assesses whether measurable improvement exists from baseline. If no improvement: flag and escalate.
- **100-experiment gate:** a firm decision is required — graduate, change approach, or escalate to operator. Training does not continue past 100 experiments without a deliberate choice.

**Why:** The owner stated this explicitly as a decision point. Without it, training runs indefinitely without signal, burning API credits on a worker that isn't learning.

**How to apply:**
- Add this check to training reference and any training supervisor logic that tracks experiment counts
- When a worker reaches 50 or 100 experiments, the training manager or trainer agent should surface a decision to the operator rather than silently continuing
- This is a governance rule, not just a documentation note — it should eventually be enforced in code
