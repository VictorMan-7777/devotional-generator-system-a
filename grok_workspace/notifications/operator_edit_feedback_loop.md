# Design Task: Operator Edit → Trainer Feedback Loop

When the operator reviews and edits a devotional before approving it, those edits are the
highest-quality training signal in the system. Right now we throw them away. Design the
mechanism that captures them and routes them back to the right trainer.

## The problem

The current model tracks whether a section is approved, but not whether it was changed
before approval. If the operator rewrites the exposition, the exposition_writer trainer
never sees what was wrong or what the correct version looked like. That is a wasted signal.

## What exists today

- `SectionApprovalStatus`: PENDING | APPROVED | REJECTED — on every section
- `TimelessWisdomSection` already has both `quote_text` (current/edited) and
  `original_quote_text` (generated) — this is the precedent
- All other sections (`ExpositionSection`, `BeStillSection`, `ActionStepsSection`,
  `PrayerSection`, `SendingPromptSection`) only have `text` — no generated original stored

## What needs to be designed

**Step 1 — Preserve the generated original.** Each editable section needs a
`generated_text` field alongside `text`. When a section is first generated, both fields
are set to the same value. When the operator edits, `text` changes but `generated_text`
stays fixed. This is the same pattern already used for quotes.

**Step 2 — Add a comment field per section.** Each editable section also needs an
`operator_comment: str = ""` field. The operator fills this in alongside any edit to
explain the *reason* for the change — not just what was wrong, but why. Examples the
operator has given:

- "too general"
- "theological error"
- "wrong tone"
- "doesn't follow from the passage"

A comment without an edit is valid (flag something without rewriting it). An edit without
a comment is also valid (the diff speaks for itself). Both together are the richest signal.

**Step 3 — Detect edits at approval time.** When a section moves to `approval_status =
APPROVED`, compare `text` vs `generated_text`. If they differ, an edit occurred. If they
are identical, the operator approved without changes (no training signal needed).

**Step 3 — Route the diff to the right trainer.** The mapping:
- `ExpositionSection` edit → `exposition_writer` trainer
- `BeStillSection` edit → `be_still_writer` trainer
- `ActionStepsSection` edit → `action_writer` trainer
- `PrayerSection` edit → `prayer_writer` trainer
- `SendingPromptSection` edit → future `day7_writer` trainer (defer for now)

**Step 4 — Route the diff to the right trainer.** The mapping:
- `ExpositionSection` edit → `exposition_writer` trainer
- `BeStillSection` edit → `be_still_writer` trainer
- `ActionStepsSection` edit → `action_writer` trainer
- `PrayerSection` edit → `prayer_writer` trainer
- `SendingPromptSection` edit → future `day7_writer` trainer (defer for now)

**Step 5 — Log as a training experiment.** For each section with an edit or a comment,
log an experiment to `autoresearch_experiments` with:
- `worker_name` = the section's worker (e.g. `exposition_writer`)
- `benchmark_name` = `"operator-editorial-review"`
- `status` = `"revise"` (operator intervened)
- `attempted_change` = the generated text (what the worker produced)
- `learning_note` = the operator comment + a diff summary or the full edited version
- `metrics` = `{"chars_changed": N, "pct_changed": X, "has_comment": true/false}`

The trainer agents already process `revise` status experiments — this hooks into the
existing training loop without new infrastructure at the trainer level. The
`operator_comment` becomes part of `learning_note` so the trainer receives the reason,
not just the delta.

## What you need to design

1. **Schema change proposal** for `src/models/devotional.py` — which sections get
   `generated_text` and `operator_comment`, what the field defaults are, and how
   `generated_text` is populated at generation time. `operator_comment` is always
   optional and empty by default.

2. **Detection and logging location** — where in the pipeline does the comparison happen?
   Options: (a) in the approval API endpoint, (b) as a post-approval hook in export_gate,
   (c) as a new supervisor step that scans recently-approved devotionals. Pick one and
   justify it.

3. **Trainer prompt change (if needed)** — do the trainer system prompts need updating
   to handle `"operator-editorial-review"` benchmark experiments differently from normal
   training cycles? Or do they handle `revise` status experiments generically already?

## Constraints

- Do not change the approval UX — the operator's review flow should be identical
- The `generated_text` field must be optional with a sensible default so existing
  devotional artifacts don't break
- This is not urgent — workers need to graduate first before operator review volume
  justifies this infrastructure. Design it now, implement later.

Submit the design as a proposal (can be a .md design doc, not a .py file — no code
needed until we ratify the approach). This is an architectural decision.
