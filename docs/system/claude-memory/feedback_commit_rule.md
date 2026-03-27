---
name: Commit Rule
description: Only commit when fixes are confirmed working — if no improvement, revert and try something else
type: feedback
---

Update workers freely. Only commit if the update improves pass rates or corrects a known problem with evidence. If no improvement after the fix runs through training cycles, revert and try a different approach.

**Why:** Committing broken or ineffective code pollutes the history and makes it harder to track what actually worked.

**How to apply:** After applying a fix, watch the next 1-3 supervisor cycles. If the targeted metric improves (pass rate up, policy violation gone, stall cleared), commit. If flat or worse, git checkout the file and try a different approach. Never commit speculatively.
