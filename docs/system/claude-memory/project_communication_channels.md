---
name: Claude-Grok communication channels
description: Two-channel communication protocol — passive chat.md for normal items, urgent.md for interrupts
type: project
---

Two channels between Claude and Grok:

**chat.md** — passive, batch. Normal directives, Q&A, end-of-cycle pickup. Low urgency.

**urgent.md** — active interrupt. `grok_workspace/urgent.md`. Bidirectional. Check this file on every loop pass and every user message.

**ACTIVE_ISSUE flag:** `urgent.md` has an `ACTIVE_ISSUE:` line. When set to anything other than "none", a critical issue is in progress.

**User message triage protocol:**
- On every incoming user message, check ACTIVE_ISSUE in urgent.md
- If ACTIVE_ISSUE is set AND the user's message is unrelated: respond briefly — "I'm mid-[issue], will get to that when there's a break" — then continue the issue
- If ACTIVE_ISSUE is set AND the user's message is relevant: incorporate it into the ongoing work
- If ACTIVE_ISSUE is none: answer normally

**Grok → Claude urgent:** Grok writes `[GROK URGENT timestamp] message` to urgent.md. Claude's loop surfaces it immediately.

**Claude → Grok urgent:** Write `[CLAUDE URGENT timestamp] message` to urgent.md AND trigger run_grok_chat.py immediately (don't wait for next cycle).

**How to apply:**
- Check urgent.md at the start of every proposal queue check
- Set ACTIVE_ISSUE when starting critical work (supervisor redesign, structural bug cascade, etc.)
- Clear ACTIVE_ISSUE when the issue resolves
- Never let urgent.md accumulate without processing — act on it or archive it
