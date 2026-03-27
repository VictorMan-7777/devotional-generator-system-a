---
name: Autoresearch Direction
description: Owner's intent for autonomous prompt/code mutation — when to implement and why to wait
type: project
---

The owner is aware of the Karpathy autoresearch pattern (autonomous eval → mutate → keep winner loop) and wants it applied to this system eventually. The key concepts from a video transcript shared 2026-03-16:

- Three ingredients: objective metric, measurement tool, something to change
- Evals should be binary yes/no — Likert scales compound variability
- Don't make evals too narrow or the model optimizes for the test, not actual quality
- Experiment history is a durable asset — pass to future models to resume where predecessors left off

**Current decision: wait to implement autonomous mutation.**

**Why:** Workers are Python/TypeScript code, not prompt files — much higher revert risk. Trainers are still being calibrated. Data is too thin (exposition_writer had first real LLM score today, outliner at ~8.5% pass rate). Need to understand failure patterns before automating fixes.

**When to revisit:** After 100+ scored runs per worker, failure patterns are stable, and trainer evaluations are consistent and trustworthy.

**Right sequence when ready:**
1. Start with exposition_writer prompt (closest to a text-file mutation target)
2. Not the outliner — too complex, too much risk in autonomous code changes
3. Confirm trainers are reliable before closing the loop
