---
name: Frozen Metrics Spec (Grok 4.20)
description: Deterministic scoring functions for Be Still, Action Steps, Exposition. Passage-agnostic keyword/bigram/regex approach. Ready to implement.
type: project
---

Frozen metrics spec written by Grok 4.20 multi-agent session on 2026-03-19. Reviewed and annotated by Claude. Full spec in `docs/system/frozen-metrics-spec.md`.

**Core approach:** Extract passage signature (keywords, bigrams, trigrams) from that day's scripture text. Score generated content by intersection size, question context, template penalty detection, and same-day tangibility markers. No LLM at evaluation time.

**Scores for current output:** Be Still 12–28, Action Steps 15–22. Pass threshold: 80.

**5 issues to resolve before coding:**
1. Define STOP_WORDS as actual frozen list (exclude "God"/"Lord" from keyword matching)
2. Define "near" as within ±15 tokens (implement as helper function)
3. Bigram + question mark must be in the SAME prompt, not just same section
4. Short passage edge case: use `max(2, min(4, len(keywords)//3))` not fixed 4
5. Remove "used meaningfully" qualifier from exposition — not deterministic; 4x-repetition penalty already handles stuffing

**Implementation target:** `src/autoresearch/frozen_metrics.py` with `score_be_still()`, `score_action_steps()`, `score_exposition()`, all returning `{score, components, penalties_applied, bonuses_applied}`.

**How to apply:** When the post-migration session is ready to implement training, start with `frozen_metrics.py`. Do not modify the training loop until this file exists and produces correct scores on the 3 Psalm 23 sample days (expected: 12–28 range).
