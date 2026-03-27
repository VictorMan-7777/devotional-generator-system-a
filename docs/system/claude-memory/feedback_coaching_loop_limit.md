---
name: Coaching loop limit and rephrase rule
description: When Grok repeatedly fails on the same problem, rephrase early and show the solution after 3-5 attempts — do not run an infinite rejection loop
type: feedback
---

Do not repeat the same rejection note hoping for a different result. When Grok submits a failing proposal more than twice with the same mistake, change the communication approach before sending it back again.

**Rephrase rule (attempts 3-4):** If the same error recurs, rephrase the feedback using a different framing — show a before/after comparison, quote the exact source line alongside the broken pattern, ask Grok to read the source file and confirm what he sees. Saying the same thing louder is not coaching.

**Show and discuss rule (attempt 5 at the latest):** After ~3-5 failed attempts, stop sending rejections. Show Grok the correct solution, then open a direct conversation in chat.md about what he misunderstood in the original requests. The discussion is where the learning actually happens — it corrects the mental model, not just the output. This is not a failure state; it is the right teaching move.

**Never run more than 5 cycles on the same proposal error** without either rephrasing or showing the solution. Ten rejections with the same note is the same mistake on Claude's side as Grok's.

**Why:** The operator explicitly corrected this after l15_enforce took 10 rejections to resolve. Same feedback, same bug, no rephrase, no show-and-discuss. That is management failure, not just Grok failure.

**How to apply:** When writing a rejection note, ask: have I already said this? If yes, rephrase or show the working version. Track rejection count per proposal. At 3 rejections, change approach. At 5, show the answer and discuss.
