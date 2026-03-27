# Prayer Writer — pastoral_burden fallback producing generic prayers

The prayer writer trainer has flagged this in multiple cycles. The cause is now located in the code.

## The bug

In `src/generation/real_section_generator.py` around lines 2225–2228, the prayer template uses `brief.pastoral_burden` directly:

```python
f"In this passage You bring {brief.pastoral_burden} into the open; let that truth press into our obedience today."
```

When `brief.pastoral_burden` is empty or is the generic fallback string "faithful response to God's word", this produces a prayer petition that is semantically plausible for any passage but specific to none:

> "In this passage You bring faithful response to God's word into the open; let that truth press into our obedience today."

The trainer's conclusion:
> "A fallback filler string that is semantically plausible for any passage but specific to none will always produce prayers that fail passage-anchoring criteria. This is a structural default-value problem, not a training problem. The fallback string must be removed from the default template entirely."

## The fix needed

Two changes:
1. **Remove the fallback string.** The string "faithful response to God's word" must not exist anywhere as a default value for `pastoral_burden`. If the brief doesn't have a specific burden, do not substitute a generic one.
2. **Hard fail on empty burden.** If `brief.pastoral_burden` is empty or None at prayer generation time, halt generation and return an error rather than producing a generic prayer. A prayer that isn't grounded in the passage is worse than no prayer.

**Target:** `src/generation/real_section_generator.py`, around lines 2225–2228. Also check wherever `pastoral_burden` is set/defaulted in the brief construction — if the fallback is set upstream, fix it there too.

Submit a proposal with the specific change. Include what `pastoral_burden` defaults to and where it is set.

---

**Update — 16:54 cycle (additional structural findings):**

The prayer trainer identified two additional code-level fixes needed alongside the pastoral_burden fallback:

**Fix B — Passage-theme classification** (`src/generation/real_section_generator.py`): Add passage-theme classification (e.g., provision, lament, wisdom, obedience) so that obedience-frame petitions are only emitted when the passage theme is imperatival or exhortation — not for declarative trust psalms like Psalm 23. The triple repetition of "faithful response to God's word" in Psalm 23 prayer output is a structural signature of a hardcoded fallback petition firing regardless of passage classification.

**Fix C — Broken variable interpolation** (`src/generation/real_section_generator.py`): The string "takes makes and down seriously" is a malformed output from a failed template variable substitution — likely an attempt to interpolate "He makes me lie down" into a petition frame. Locate the f-string or string interpolation in the petition assembly function that references passage action verbs. Add a grammatical validation step that either renders correctly or suppresses the petition entirely (rather than emitting broken text) if the variable is malformed.

All three fixes (A pastoral_burden fallback removal, B theme classification, C variable interpolation) are in the same file and likely the same region. Submit as one combined proposal.
