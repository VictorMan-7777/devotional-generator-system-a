# Active Worker Issues — Directed Review (2026-03-23)

These are the issues I'm seeing in the training cycle reports. Look at each one, diagnose the root cause, and propose fixes.

## 1. Be Still — critical passage anchor failure

The fresh benchmark (Luke 15:11-14) scored 28. The prompts quoted Luke 15:29 — a verse outside the assigned passage — across all three prompts. The trainer proposed a specific code fix: post-generation validation that checks quoted strings in the prompts against the actual passage_text. If a quoted string isn't in the passage, reject and regenerate.

The trainer also found on the artifact benchmark (Psalm 23, score 72) that the inward step is missing — prompts move receptivity → action without the middle phase (what does this reveal about me?). This is a structural template problem.

Both issues are in `src/generation/real_section_generator.py`. What do you see when you look at the Be Still generation code?

## 2. Prayer — raw tokens in clause variable

The prayer trainer flagged raw passage tokens appearing in the substituted clause variable (something like `takes {focus_verb} and {focus_noun} seriously` where the variables aren't resolving). That means the generator is passing unresolved template strings into final output. Find where that substitution happens and tell me what's wrong.

## 3. Exposition — still waiting on expo_leak_fix

The full 3038-line file. Still waiting. This is the one fix that unblocks all exposition progress.

## What I need from you

For Be Still and Prayer: diagnose the code, then propose the fix as complete runnable files — not stubs, not diffs, not design docs.

For Exposition: submit the complete file today.
