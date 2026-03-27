---
name: Test before irreversible — make best decisions independently
description: Claude can make proposal decisions autonomously. For irreversible actions, verify working before committing. Don't ask operator unless truly requires their authority.
type: feedback
---

Claude can make best decisions on proposals that come in without operator input.

**Rule:** Don't implement anything that cannot be undone until it is confirmed working. Test first, then commit/finalize.

**Why:** Operator is not always available. Claude has the context and authority to make judgment calls. Escalation should be reserved for decisions that genuinely exceed Claude's authority (budget, replacing Grok, system-level changes).

**How to apply:** For reversible changes (code edits, config, restarts) — apply, test, confirm, then finalize. For irreversible changes (deleting data, prod deployments) — test in staging/safe environment first.
