---
name: Use second-eyes review proactively, not deferred
description: User corrected deferring Grok/external LLM review to "future" — use it in the current session now
type: feedback
---

Don't defer second-eyes LLM review to future sessions. If Grok, ChatGPT, or another LLM can provide a useful review today, send it today.

**Why:** "Don't put off til tomorrow something that can be helpful today." User confirmed this explicitly when Grok review was treated as a future concern rather than immediate action.

**How to apply:** After making significant code changes in a session, send a second-eyes request to the Grok chat server (port 8001 on this machine) before ending the session. Structure the message as: what changed, current scores, and ask for gaps/regressions/systemic issues. Also: select the right LLM for the role — if Grok is not the best fit, use an OpenAI agent instead.
