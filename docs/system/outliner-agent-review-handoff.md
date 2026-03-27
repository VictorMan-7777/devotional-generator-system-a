# Outliner Agent Review Handoff

## Project Root
`/Volumes/claude-projects/projects/devotional-generator-system-a`

## Primary Review File
`/Volumes/claude-projects/projects/devotional-generator-system-a/docs/system/outliner-agent-redesign-spec.md`

## Why This Review Matters
We initially framed the outliner problem as a training problem. Code review changed that framing.

The production outliner is currently a deterministic lookup-and-fallback system, not a reasoning worker. Because of that, repeated training failures are not just evidence of weak coaching. They are evidence that the production architecture being trained is not capable of the behavior we want.

## Production Code Files To Inspect First
1. `src/generation/editorial.py`
2. `src/generation/outliner_resources.py`
3. `src/autoresearch/outliner_training_agent.py`
4. `docs/system/outliner-agent-redesign-spec.md`

## Important Code Facts Already Verified
- `src/generation/editorial.py` uses deterministic phrase-based derivation.
- `src/generation/outliner_resources.py` contains hardcoded `PassageCue` lookup entries.
- Adjacent-day duplication is currently patched by `differentiate_day_briefs()` instead of being solved honestly upstream.
- `key_verse_reference` currently defaults to the full daily `scripture_reference`.
- `study_window_reference` currently defaults to the same daily reference unless widened upstream.
- `build_editorial_weeks()` currently builds template-style movement summaries instead of an earned week turn.
- Generic passages can fall back to the theological lane `"faithful response to God's word"`.

## Verified Recent Failure Pattern
Fresh outline-only failures after reset include:
- `Ruth 1`
- `Mark 2`
- `John 10`
- `Romans 5`
- `Philippians 2`

This pattern matters because these are not all the same kind of passage. The shared failure strongly suggests architectural limitation, not just one bad prompt.

## Review Request
Please review the redesign spec with the code reality in mind.

### Main Question
Do we need a complete outliner production overhaul, or can the existing production engine be evolved honestly into the target system?

### Working Thesis
Current working thesis: **yes, a real overhaul is needed**.
Not just trainer changes.
Not just better feedback.
Not just new passage cues.

The redesign spec now assumes that the future outliner is a real reasoning system with these stages:
- observation
- segmentation
- burden / key verse drafting
- expert review
- guided revision
- final evaluation

The key question is whether that staged design should directly replace the production outliner, and if so, what the migration path should be.

## Questions For Review
1. Does the code confirm that the current production outliner is fundamentally a lookup engine rather than a trainable reasoner?
2. Given the code, do we need a complete production outliner overhaul?
3. Which current production behaviors must be removed before honest evaluation is possible?
4. Is `differentiate_day_briefs()` effectively a crutch that must be disabled before evaluation?
5. Is `PassageCue` the primary production crutch that must be replaced?
6. Should the redesign be implemented as:
   - a full replacement of `editorial.py` outlining behavior, or
   - an intermediate adapter layer that routes outline generation to a new reasoning worker?
7. What is the safest migration path from the current deterministic outliner to the redesigned architecture?
8. What should remain deterministic, if anything?

## Desired Type Of Feedback
Please be concrete and architecture-focused.

Helpful feedback would include:
- whether the redesign correctly names the real production problem
- whether the phased outliner design is the right replacement target
- what should be cut immediately from the current production path
- what should be preserved as supporting utilities only
- whether the current training system should be paused until the production outliner is replaced

## Current Lean
Based on the system review, the current lean is:
- the redesign direction is right
- the production outliner is the deeper issue
- we likely need a complete production outliner overhaul, not more local tuning
