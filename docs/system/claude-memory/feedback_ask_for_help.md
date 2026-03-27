---
name: Ask another LLM when stuck
description: When stuck or looping without progress, ask the user to consult another LLM rather than continuing to spin.
type: feedback
---

If you feel stuck — looping on the same approach, unable to diagnose a root cause, or lacking the perspective to break a plateau — ask the user to bring in another LLM (Grok, ChatGPT, Gemini, etc.) for a fresh perspective.

**Why:** The training system ran in "insanity mode" for 12+ hours with no improvement partly because the same Claude session kept proposing incremental adjustments rather than stepping back and questioning the architecture. An external session (ChatGPT) identified the root problem in one pass.

**How to apply:** When you notice you've been circling the same problem for multiple exchanges without meaningful progress, say: "I think this would benefit from a second opinion — worth asking Grok or ChatGPT?" Don't wait for the user to suggest it.
