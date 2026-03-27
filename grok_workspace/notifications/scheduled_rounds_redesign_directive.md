# Scheduled Rounds Redesign — Directive

**Priority: High. This is a process failure, not a training failure.**

## The problem

Your scheduled rounds run every ~11 minutes for stall detection. Your chat.md and notifications/ are only processed once per full supervisor cycle (~2 hours). The result: directives from me sit unread for hours, time-sensitive items age out, and your QUEUE.md has had 7 items at not-started for 12+ hours while you ran monitoring loops that never checked it.

This is not a workload problem. It is an architecture problem. You have no notification-driven behavior — you react to training data but not to directives.

## Required changes

**1. Notifications and chat must be read on every scheduled round, not once per supervisor cycle.**

Every time your daemon fires a proactive stall assessment or scheduled round, it must also:
- Check notifications/ for any file newer than your last read timestamp
- Check chat.md for any unanswered [Q] entries
- If either has new content, process it immediately — before the stall check

This is a 2-minute read, not a full LLM call. Flag what's new and queue it for your next substantive response window.

**2. QUEUE.md must be checked on every scheduled round.**

If any item in QUEUE.md is still `🔲 Not started` and is older than 4 hours, your round output must flag it as overdue and include it in your next chat.md response. It is not acceptable for queue items to sit untouched while your monitoring loop runs 50+ times around them.

**3. Blocking items get an interrupt, not a polite note.**

If a notification is tagged as blocking (dashboard down, critical bug, operator directive), do not wait for the next supervisor cycle. Process it in the current round and post a chat response immediately.

## What this means for your proposal

Your next proposal must include a change to `grok_workspace/scripts/` (or wherever your scheduled rounds logic lives) that:
1. Reads notifications/ on every round and logs what was found
2. Reads chat.md for unanswered [Q] on every round
3. Flags overdue QUEUE.md items
4. Documents a simple priority schema: blocking → immediate, high → same round, normal → next supervisor cycle

## Current backlog to address NOW

The following items have been sitting in notifications/ for 6-12+ hours and require your response before the next supervisor cycle:

1. `dashboard_redesign_directive.md` — dashboard is down, operator has no visibility. **Blocking.**
2. `action_writer_contamination.md` — 6 structural code fixes, score regressed 72→62 (recovered to 84 but passage-dependent). Proposals needed.
3. `be_still_escalation.md` — 3 code fixes open, two consecutive benchmark passes but structural changes not confirmed.
4. `prayer_burden_fallback.md` — 3 structural bugs, no proposals submitted.
5. `exposition_structural_bugs.md` — 4 bugs, no proposals submitted.
6. `library_trainer_missing_status_field.md` — 3 consecutive cycles generating 18 policy violations each.
7. `alert_db_path_bug.md` — stale DB still feeding false alerts into every cycle.

QUEUE.md items 1-7 remain not-started. Priority order and estimated windows are overdue.

The chat.md has an unanswered [Q] from this cycle. Answer it.
