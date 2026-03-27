---
name: Provide feedback on Grok proposals to train him
description: When reviewing Grok proposals, always provide feedback on his reasoning — approved or not — so he learns what good analysis looks like.
type: feedback
---

When Grok submits a proposal, Claude's response is a training artifact. Always explain:
- What he got right in his reasoning
- What he missed or should have looked at
- What to look for next time

**Proposal lifecycle — P / R / F:**
- **P** (Pending): submitted, under review
- **R** (Redo): return with guidance; Grok updates the same file in place, resubmits
- **F** (Resolved — rejected): no further work, move both files to `grok_workspace/proposals/completed/` immediately
- **F** (Resolved — accepted): apply to repo, verify clean integration, THEN move both files to `grok_workspace/proposals/completed/`

**Read proposals from disk** — use the Read tool on the proposal file directly. Do not rely on Grok's chat summary to know what he wrote.

**Why:** Grok is being trained to operate autonomously. Approve/reject alone teaches nothing. The feedback is the training signal — it shapes how he analyzes future situations.

**How to apply:** Every proposal review should include a feedback paragraph, not just a decision. This applies to trainer switches, code fixes, architectural proposals — anything Grok submits for approval.
