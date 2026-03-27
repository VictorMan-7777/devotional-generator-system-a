---
name: LLM agent autonomy
description: Don't over-constrain LLM agents with deterministic Python rules — give them authority to own decisions
type: feedback
---

Don't box in LLM agents with hardcoded Python rules for decisions they should make themselves — but don't remove all guardrails either. The goal is right constraints in the right places.

**Why:** The deterministic supervisor (assignment selection, revision logic, cycle planning, worker scheduling) was doing the thinking that LLM agents should do. This produced rigid, slow, low-quality decisions — 119-minute outliner cycles, unconditional revision runs, fixed assignment budgets. But full autonomy with no review creates a different risk: irreversible structural mistakes with no human check.

**Agents own without approval (operational judgment):**
- Which workers run each cycle, in what order, with what budget
- Whether to revise, skip, defer, or escalate a failing assignment
- Which passages/benchmarks to assign and why
- Cycle pacing and parallelism decisions
- Any judgment call about training quality or progression

**Review before building (structural/irreversible):**
- New DB tables or schema changes
- New scripts or changes to core infrastructure
- Changes to how worker output is logged or measured
- Anything that can't be easily reversed if wrong

**How to apply:**
- If a decision is "which passage should the outliner work on next" — trainer LLM, no approval needed
- If a decision is "should we revise this output" — trainer LLM, no approval needed
- If a decision is "which workers run this cycle" — supervisor LLM, no approval needed
- If a decision is "add a new DB table" — submit for review before building
- Python infrastructure stays for: DB writes, subprocess execution, file I/O, logging
