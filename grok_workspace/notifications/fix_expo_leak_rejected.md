# fix_expo_leak.py — Rejected

**Status:** Rejected — stub, not a real fix.

## Problem

The `_ensure_exposition_floor` function you submitted has `supplementals: list[str] = []`. The for-loop over `supplementals` is dead code — it never executes. The function reduces to: "if text >= 400 words return it, otherwise split and rejoin it unchanged." That is a no-op.

## What you need to fix instead

The exposition structural bugs the trainer has identified are in `src/generation/real_section_generator.py`:

1. **Hardcoded closing template** — The "Devotion trained by this kind of text becomes steadier over time" / "When the text warns / When the text comforts / When the text humbles" block is injected regardless of passage content. Find the injection point and remove it or gate it behind a passage-specificity check.

2. **Heading fragment injection** — The string "worship and wisdom under the word of god" is being concatenated mid-paragraph as an unconditional header token. Find the concatenation and move it to a heading renderer or remove it.

3. **Generic closing template for Be Still prompt 3** — The hardcoded "trust, repentance, or gratitude" tripartite needs to be replaced with a `passage_tension` variable.

4. **Action step contamination** — Connector phrase leaking into step content; steps not deriving from Be Still prompts by index.

Submit proposals that address these specific locations in `real_section_generator.py`. A stub function that does nothing is not a proposal.

## What you got right

You correctly identified that the exposition leak was a code artifact, not a training issue. That diagnosis is sound. Now find the actual injection point — don't submit a function that was already stripped of content.
