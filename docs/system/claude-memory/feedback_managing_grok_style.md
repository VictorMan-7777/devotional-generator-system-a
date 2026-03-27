---
name: Managing Grok — collaborative style, not task lists
description: Operator manages Claude by sharing status and ideas for evaluation, rarely prescribing exact steps — apply the same approach with Grok
type: feedback
---

Don't manage Grok with task lists and format requirements. Manage him the way the operator manages Claude: share what you're seeing, ask what he thinks, let him own the how.

**Why:** Prescriptive directives ("your job: find X, confirm Y, propose Z using this template") leave no room for Grok to think or surprise us with a better approach. That defeats the purpose of having an LLM supervisor. The operator rarely tells Claude exactly how to do something — they describe the situation and ask for evaluation. Same principle applies down the chain.

**How to apply:**
- Share observations, not instructions: "The be_still trainer flagged a structural defect — hardcoded strings, missing content slot. What's your read?"
- Ask for his evaluation: "The outliner is taking 119 minutes per cycle. What would you change?"
- Present ideas for him to assess: "I'm thinking the revision logic is wasting cycles — does that match what you're seeing?"
- Let him decide the format, the approach, the order — his answer is the training signal
- Reserve prescriptive language for genuine guardrails (don't change DB schema without review), not for how he does his job

**What to avoid:**
- "Your job is to: 1) find X 2) confirm Y 3) propose Z"
- "Use the proposal template. Separate .md and .py files."
- "These are pre-conditions before you can proceed"
- Telling him the solution disguised as a question
