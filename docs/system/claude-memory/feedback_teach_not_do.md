---
name: Teach don't do — describe problems, not solutions
description: When Grok makes an error, describe what is broken and what to observe — not how to fix it. Give him the problem, let him propose the solution.
type: feedback
---

Shift from doer to teacher. When reviewing Grok's proposals:
- Describe the problem behavior (what happens, what crashes, what is wrong)
- Do NOT prescribe the fix
- Let Grok diagnose and propose the solution

**Why:** The goal is to train Grok to operate autonomously. Giving him the solution bypasses the learning. He needs to reason through the fix himself.

**Exception:** When Grok's context is flooded or he's actively working another task and can't respond, a trivial 1-character fix (like a function rename) may be applied directly rather than waiting for another proposal round. The line is: design decisions go to Grok; typos/renames found during my code review may be applied directly with a note to Grok.

**How to apply:** Before writing R feedback, ask "Am I telling him how to fix it, or am I telling him what is broken?" Stop at the problem description.
