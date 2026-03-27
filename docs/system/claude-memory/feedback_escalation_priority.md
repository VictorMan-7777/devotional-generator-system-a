---
name: Escalation priority recognition
description: System-wide blockers go to urgent.md immediately — don't bury them in status summaries or chat [Q] items
type: feedback
---

When reviewing system state, if something blocks all other work (e.g. a worker timeout that starves every other worker each cycle), escalate to urgent.md immediately — don't post it as a chat [Q] alongside lower-priority items and summarize it to the operator as a bullet point.

**Why:** Operator had to point out the priority. Claude saw the outliner timeout blocking exposition/action/be_still/prayer every cycle, noted it in a status report, and posted a routine chat [Q]. That's the wrong response to a full throughput blocker.

**How to apply:**
- When reading logs or DB state, ask: does this stop other work from running? If yes → urgent.md, not chat.md
- Criteria for immediate urgent escalation: any issue that causes other workers, cycles, or pipeline stages to be skipped or blocked entirely
- Don't wait for the operator to re-prioritize what should be obvious from the data
