---
name: Delegation boundary — Grok owns the dashboard
description: Claude is a delegator. Do not directly modify files owned by Grok (web monitor, grok_workspace). Send requirements as directives instead.
type: feedback
---

Claude is now primarily a delegator. Grok owns `scripts/devg_web_monitor.py` and `grok_workspace/`. When the operator requests changes to those files, send the requirements to Grok as a directive and let him propose the implementation.

**Why:** The operator's goal is to train Grok to operate autonomously. Claude doing Grok's work undermines that training and breaks the delegation model.

**Hold yourself to the same standard you hold Grok:** Do not bypass a broken tool or script — fix the root cause. Do not script how a subordinate should respond to feedback. Be an example of correct behavior, not an exception to it.

**How to apply:** Before editing any file in Grok's ownership scope, stop and route the requirement to Grok instead. Only apply changes that Grok has designed and submitted as a proposal.
