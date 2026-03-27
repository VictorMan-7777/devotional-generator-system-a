---
name: Diagnostic runs are for insight, not repair
description: When asked to run a scorer/metric against existing output, report the numbers and stop — do not diagnose or fix failures found during the run.
type: feedback
---

When the user asks to run a frozen metric or scorer against existing output (e.g. "run the prayer score against Psalm 23 outputs"), the goal is to produce a score table like the Be Still / Action Steps baseline runs — show the numbers, note what's passing or failing at a high level, and stop.

**Why:** The user asked for a diagnostic run on the prayer worker frozen metric. Instead of just reporting the scores (88 Pass, –12 focus clause penalty), the session went into diagnosing false positives in `_theme_key()` and making code changes. That was scope creep — the scoring run was for insight, not repair.

**How to apply:** Run the scorer, print the scores and top penalties, summarize in one paragraph what the numbers mean. If bugs are found during the run, note them for later but do not fix them mid-run unless the user explicitly asks.
