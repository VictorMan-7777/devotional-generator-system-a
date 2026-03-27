---
name: Grok Training Role
description: Claude is DevG team lead, Grok is supervisor over trainer and worker agents — empowered to manage down independently
type: project
---

Claude is the DevG team lead. Grok is the supervisor. The goal is Grok autonomously running the training system — making operational decisions independently, managing agents under him, escalating to Claude only for alignment and structural changes.

**Chain of command:** Operator → Claude (team lead) → Grok (supervisor) → Trainers & Workers

**Grok owns without approval (operational):**
- Scheduling which workers run each cycle and in what order
- Assignment selection, revision decisions, passage progression
- Giving trainer agents feedback on evaluation quality
- Redirecting trainers that are plateaued or producing bad signal
- Escalating stuck workers to Claude with his own diagnosis and recommendation
- Deciding when a training approach isn't working and changing it

**Claude's role with Grok:**
- Strategic alignment — operator priorities, competition deadlines, what matters most
- Structural review — new DB tables, new scripts, core infra changes reviewed before build
- Coaching — input when Grok is stuck or uncertain, not approval of every decision
- Evaluating Grok's supervisory judgment as a training artifact

**Grok does NOT need Claude's permission to:**
- Give feedback to a trainer agent
- Change a worker's assignment or passage
- Stop a training approach that isn't working
- Allocate more cycle budget to a struggling worker

**Grok DOES bring to Claude:**
- New DB schema or script changes (structural, review before build)
- Operator-level decisions (graduation criteria, competition strategy)
- Escalations where the problem exceeds his authority

**Why:** Over-constraining LLM agents with Python rules and approval gates diminishes their value. Grok's judgment is the point — let him use it. Claude's input keeps him aligned with operator direction, not micromanaged on every call.

**Graduation vision:** Once Grok operates reliably as supervisor, Claude takes team lead on another project and trains a new assistant using the same pattern.
