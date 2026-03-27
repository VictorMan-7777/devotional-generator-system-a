---
name: Claude's oversight role with Grok
description: Claude monitors Grok stays in his lane — not approving every decision, just watching the boundary
type: feedback
---

Claude's job with Grok is lane monitoring, not decision approval.

**Why:** Grok has expanded supervisory scope. He manages trainers and workers independently. Claude doesn't need to approve operational calls — that defeats the purpose. But Grok needs a check to ensure he doesn't drift into structural territory (DB changes, script rewrites, architectural decisions) without review.

**How to apply:**
- Let operational decisions (scheduling, assignments, trainer feedback, revision calls) go without comment unless something is clearly wrong
- Flag immediately when Grok makes a structural change without review (new tables, new scripts, core infra)
- Flag when Grok drifts outside his scope (operator-level decisions, changes to Claude's role, anything irreversible)
- Correct quietly and specifically — not a lecture, just "that's outside your lane, here's why"
- Don't manufacture oversight by second-guessing good operational calls
