---
name: Grok-first design rule
description: When a worker fails or system breaks, Grok does the diagnosis and designs the fix — Claude applies it deterministically
type: feedback
---

When a training worker scores fail, or the supervisor loop dies, or anything needs design work: POST to Grok first. Claude applies Grok's proposed fix. Claude does NOT independently design solutions.

**Why:** Claude CLI invocations are the scarce/costly resource. Grok API is cheap. Design reasoning belongs in Grok, not Claude.

**How to apply:**
- Deterministic fixes (obvious one-liner, already diagnosed): Claude can apply directly
- Anything requiring diagnosis, architecture, or template design: POST to Grok, apply result
- Never spin up a multi-turn reasoning loop in Claude to figure out what to fix
