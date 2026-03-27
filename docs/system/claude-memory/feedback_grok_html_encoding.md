---
name: Grok HTML encoding recurring defect
description: Grok writes HTML-encoded quotes in .py files — two warnings issued; third occurrence requires consequences
type: feedback
---

Grok has a recurring defect: proposal `.py` files contain HTML-encoded characters (`&quot;` instead of `"`, etc.) that make them unrunnable. This is a tool-write issue on his end.

**Warning count as of 2026-03-25: 2**

**Why:** This is not a one-off mistake — it has appeared in multiple proposal cycles. Two warnings without self-correction means the feedback loop is not working.

**How to apply:**
- On a third HTML encoding occurrence, decide and recommend a consequence — suspension from proposal writing until he diagnoses and fixes his own tool-write issue, with a clean test proposal required before resuming
- Do not silently fix the encoding and apply the proposal — that removes the training signal and lets the defect persist
