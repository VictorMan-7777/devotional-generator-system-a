# Outliner Agent Redesign Spec

## Purpose
The current outliner is failing too often, too early, and too similarly. It is behaving like a weak trial-and-error worker instead of a coached junior assistant who learns from expert support. This redesign shifts the outliner from "attempt -> fail -> retry" into a supported training architecture where the outliner reads, plans, explains, gets reviewed, revises, and only then is graded.

This document is written to be handed to another AI for review.

## Central Production Reality
The production outliner currently being exercised is not an LLM-centered reasoner. It is a deterministic rules engine in:

- `src/generation/editorial.py`
- `src/generation/outliner_resources.py`

That production path currently relies on:
- phrase-matching against `PassageCue` lookup tables
- generic fallback burdens and lanes when no cue matches
- post-hoc string differentiation through `differentiate_day_briefs()`

This redesign therefore describes a replacement of the production outlining architecture, not merely a better coaching loop around the existing lookup engine.

## Incorporation Of External Review
This version already incorporates a substantive outside review. The most important corrections from that review are:

- expert reviewers must be real independent review calls, not self-review theater
- theological review should precede library confirmation inside expert review
- genre detection must happen before segmentation
- packet quality must be certified before Phase 1 begins
- stable passing must be numerical, not vague
- step-down behavior must be concrete by miss type
- hold-out passages are required to detect pattern-matching and metric gaming

## Current Failure Evidence
As of 2026-03-16, the live outliner experiment history shows 7 fresh outline-only failures after reset:

- `Ruth 1` -> fail
- `Mark 2` -> fail
- `John 10` -> fail
- `Romans 5` -> fail
- `Romans 5` guided retry -> fail
- `Philippians 2` -> fail
- `Philippians 2` guided retry -> fail

This is enough evidence that tweaks are not producing reliable learning.

Production code evidence behind that conclusion:
- adjacent-day differentiation is currently patched by `differentiate_day_briefs()` instead of derived honestly
- `key_verse_reference` currently defaults to the full `scripture_reference`
- `study_window_reference` currently defaults to the same daily reference unless manually widened upstream
- `build_editorial_weeks()` currently templates week movement rather than deriving an earned turn
- the generic theological-lane fallback is still `faithful response to God's word`

These are architecture facts, not merely training symptoms.

## Diagnosis
The current outliner design has several structural weaknesses:

0. The production worker being trained is not actually the reasoning system described by the training spec.
The current production path is still a deterministic cue matcher. A lookup engine cannot be coached into first-principles outlining; it can only be extended with more hardcoded cases.

1. It is graded too early.
The outliner is producing a full outline artifact before proving that it understands passage movement, burden, and boundaries.

2. It is learning from failure labels more than from expert teaching.
A fail plus a short retry focus is not enough instruction for a novice.

3. It is not decomposed into teachable skills.
We are asking for a complete devotional outline when the worker may still be weak at:
- segmenting the passage
- identifying daily key verses
- preserving broader context
- distinguishing adjacent day burdens
- making an earned week turn

4. Its revision loop is still too thin.
Even after recent improvements, the revision path mostly reattempts the same task with limited coaching.

5. It is not using expert support aggressively enough.
Reference-librarian and theological-reviewer help should arrive as active teaching inputs, not only as occasional side checks.

6. It does not clearly separate capability levels.
The worker should master easier passage families before being trusted with harder ones.

7. It does not detect genre early enough.
Narrative, wisdom, gospel discourse, epistle argument, and prophetic material require different segmentation logic.

8. It does not gate packet quality before work begins.
If the research packet is shallow, metadata-shaped, or context-thin, the outliner starts from a bad foundation and the entire cycle degrades.

9. It does not distinguish structural failure from theological failure sharply enough.
A segmentation miss, a burden miss, and a theological-boundary miss should not all route through the same generic correction sequence.

## Redesign Goal
Create an outliner system that trains like a serious junior seminary assistant:
- scripture first
- explanation before output
- expert coaching before grading
- harder passages only after easier ones are stable
- explicit use of library and theological review
- no crutches
- no harness dependence

Implementation consequence:
- the production rules engine must be retired from primary outline generation
- the redesigned outliner must become the actual production outliner, not merely a training-side shadow system

## Required Capabilities
The redesigned outliner must demonstrate these capabilities explicitly.

### 1. Passage segmentation
The outliner must divide the passage into meaningful devotional-day units.

Requirements:
- segments are text-shaped, not arbitrary equal slices
- segments move forward logically
- each day has a narrow focal reference, usually 1-2 key verses
- each day also preserves a broader study window when needed

### 0. Genre detection
The outliner must identify the passage's literary mode before segmentation.

Requirements:
- classify the passage at least at the level of narrative, wisdom, parable, discourse, epistle argument, prophecy, psalm/poetry, or mixed
- explain which literary signals justified that classification
- use different segmentation logic depending on genre
- fail early if genre confidence is low and the assignment depends on the disputed classification

### 2. Key verse identification
The outliner must identify the specific verse or verses carrying the daily burden.

Requirements:
- `key_verse_reference` is first-class, not implied
- key verses are narrower than the study window when appropriate
- the outliner must explain why those verses are central

### 3. Context preservation
The outliner must preserve enough context that downstream writers do not flatten or distort the passage.

Requirements:
- every day includes `study_window_reference`
- study window varies by passage, not a fixed width
- the outliner explains what belongs to the day and what belongs outside it

### 4. Day-to-day differentiation
The outliner must avoid repeated burdens and repeated theological lanes.

Requirements:
- adjacent days cannot simply restate the same burden
- each day must say what changed from the previous day
- repeated movement must be flagged before grading

### 5. Week-turn design
For multi-week plans, the outliner must create real week movement.

Requirements:
- every week has a movement summary
- week turns are earned by the passage, not imposed for symmetry
- the outliner must explain why the next week starts where it does

### 5b. Week-level devotional arc
The outliner must shape the emotional and applicational movement of the full week, not only the structural turn.

Requirements:
- a reader should be able to articulate how the week moved them from one spiritual posture to another
- Day 1 and Day 7 should not feel rhetorically interchangeable
- the week arc must remain subordinate to the passage, not imposed from outside it

### 6. Theological boundary discipline
The outliner must respect the passage's actual theological burden.

Requirements:
- severe passages stay severe
- comfort passages are not made harsher than the text supports
- no flattening into generic devotional themes
- no Christological or applicational leap beyond what the passage can honestly bear

### 7. Explainability
The outliner must explain its decisions before it is trusted.

Requirements:
- why these day boundaries
- why these key verses
- why this daily burden
- why this week turn
- why this application lane is allowed
- what likely mistakes were consciously avoided
- what textual evidence compels this burden rather than five other plausible burdens

### 8. Packet-use discipline
The outliner must demonstrate that it is using real research help rather than treating the packet as decorative metadata.

Requirements:
- identify which packet items materially shaped the outline
- distinguish shelf-backed research help from generic note noise
- surface when packet quality is too weak to proceed honestly

## Proposed New Architecture
The outliner should no longer be one monolithic worker action. It should have staged internal phases.

Important implementation rule:
- these phases must be separate calls or separately scored subroutines with independent prompts where appropriate
- Phase 4 expert review must not be the same prompt instance reviewing its own Phase 3 output
- self-review may exist as a lightweight aid, but it does not count as expert review

## Packet Gate Before Phase 1
Before the outliner begins observation, the packet must pass a quality gate.

Certified by:
- `library_trainer`
- with research-librarian input when needed

Minimum packet requirements:
- not metadata-shaped
- includes real explanatory excerpts or notes
- includes explicit statement of what key resources are useful for
- includes enough context support for the passage's genre and burden

If the packet fails:
- the outliner does not start
- the packet is corrected first
- this is recorded as an input failure, not an outliner failure

### Phase 1. Observation
Input:
- scripture text
- research-librarian packet
- current notes from the reference library

Output:
- genre classification
- passage observations
- structural markers
- repeated terms / contrasts / transitions
- imperatives
- vocatives
- rhetorical questions
- climactic statements
- genre markers
- likely natural boundaries

The worker is not yet allowed to produce a finished outline.

Observation must use a structured template, not a freeform impressionistic summary.

### Phase 2. Segmentation draft
Output:
- candidate day segments
- candidate week groups
- confidence per segment
- open questions / ambiguities

This phase should be reviewed before final burdens are written.

Hard gate:
- if segmentation does not pass its own evaluation, burden drafting does not begin

### Phase 3. Burden and key-verse draft
Output per day:
- `segment_reference`
- `study_window_reference`
- `key_verse_reference`
- `why_these_verses`
- `day_burden`
- `theological_lane`
- `application_boundary`

### Phase 4. Expert review
The draft must be reviewed by support agents before the final grade.

Support order:
1. `theological_reviewer`
- checks theological boundaries
- checks whether the burden matches the passage
- checks whether the worker is softening or distorting the text

2. `reference_librarian` / research librarian
- verifies the packet is using real shelf knowledge
- checks whether the packet actually supports what the outline is claiming
- checks whether current holdings should reshape the outline before acquisition is requested

3. `outliner_trainer`
- converts reviewer feedback into novice-friendly coaching
- decides whether to revise, step down, defer, or pass

Reviewer independence requirements:
- each reviewer must have its own prompt, role charter, and review scope
- each reviewer must specify what it can certify and what it cannot certify
- each reviewer must be evaluated for reviewer-quality, not assumed trustworthy because it is a reviewer

### Phase 5. Guided revision
The outliner must revise the same assignment using expert coaching.

Rules:
- no more than one unsupported retry
- after the first poor attempt, guidance is required
- feedback must be concrete and passage-specific

### Phase 6. Final evaluation
Only after guided revision should the attempt receive its score.

## Training Ladder
The outliner needs a formal curriculum.

### Advancement rule
`Stable passing` means:
- at least `3` consecutive passes at the current level
- across at least `3` distinct passages
- with no more than `1` librarian escalation
- and no theological-boundary failure on the final pass set

Advancement is blocked if these conditions are not met.

### Level 1. Easy single-movement passages
Goal:
- learn segmentation and key verse narrowing

Examples:
- short narrative units
- simple wisdom units
- short teaching passages with clear movement

Within-level sequencing:
- begin with short narrative and wisdom units with obvious pivots
- then short discourse units with explicit connectors
- then simple epistle units with clear argumentative turns

### Level 2. Moderate multi-movement passages
Goal:
- learn adjacent-day differentiation
- learn context windows

### Level 3. Multi-week passages
Goal:
- learn week turns
- maintain progression across longer plans

### Level 4. Difficult passages
Goal:
- hold theological boundary under pressure
- manage severe or conceptually dense material

Rule:
A worker may not advance by raw attempt count. Advancement requires stable passing at the current level.

Regression rule:
- every level above Level 1 must periodically recheck anchor passages from earlier levels
- if the worker regresses on anchor passages, advancement pauses and the worker returns to remediation

Hold-out rule:
- each level must reserve hold-out passages never used in training
- these passages are evaluation-only and exist to detect pattern-matching

Pre-assignment difficulty check:
- before assignment, the trainer must estimate whether the passage is appropriate for the current level
- a passage that is obviously above current capability should not be assigned merely to generate failure data

## Failure Handling Rules
This is the part that most needs redesign.

### Current problem
The outliner is absorbing pain, not instruction.

### New failure policy
1. First miss
- do not just fail and move on
- route to trainer coaching

2. Second miss on same passage
- route according to miss type
- burden/boundary miss -> theological review required
- packet/context miss -> library review required
- structural miss -> trainer remediation required and may also require packet review if context weakness contributed

3. Third miss on same passage
- step down the task
- reduce scope
- simplify the output requirement

4. Repeated miss ceiling
- defer the passage
- mark it as above current capability
- revisit later after easier passages are stable

The worker should not be allowed to accumulate an unbounded fail stack on the same lesson.

### Concrete step-down definitions
If the miss type is:

- segmentation miss:
  - step down to segmentation-only output
  - no burden drafting
  - optionally use a shorter unit of the same passage

- burden miss:
  - keep the same segment
  - require textual evidence for the burden
  - delay application lane until burden is stable

- theological-boundary miss:
  - require theological review before retry
  - prohibit unsupported application expansion

- packet/context miss:
  - stop outliner work
  - repair packet first
  - do not count the next run as a fresh blind retry

### Re-entry rule for deferred passages
A deferred passage becomes eligible again only after:
- `3` consecutive passes at the current difficulty level
- across `3` distinct passages
- without a new theological-boundary failure

## Reference-Librarian Integration Requirements
The outliner should use the library more intelligently.

Requirements:
- outliner starts with a research packet
- if the packet is weak, the request goes first to the library trainer for validation
- the research librarian may not escalate to acquisition without trainer approval until the librarian is trusted
- outliner revision should include library-guided notes when available
- current shelf holdings must be considered before new acquisition

Required packet quality:
- not metadata-shaped cuttings
- real excerpted help
- context-aware notes
- explicit indication of what a resource is useful for
- library-trainer certification before the outliner begins

## Theological Reviewer Integration Requirements
The theological reviewer should actively assist outliner training, not only screen finished downstream prose.

Requirements:
- review outline burden and theological lane on weak passages
- flag flattening, sentimental drift, overreach, and misplaced comfort
- provide advice to the outliner trainer in novice-friendly language
- remain a standing guardrail on difficult passages
- justify any accepted week turn with a real textual pivot, not only a neat structural break

## Outliner Trainer Requirements
The outliner trainer must act like an expert teacher, not a scorekeeper.

Requirements:
- assume the outliner is a novice
- choose passage difficulty based on demonstrated capability
- explain mistakes concretely
- prefer supported revision to repeated grading
- use expert reviewer input when needed
- stop assigning passages that are clearly above current capability

Trainer-quality requirements:
- coaching must be passage-specific, not generic
- coaching quality is measured by whether the next revision actually addresses the flagged failure
- if coached revisions do not improve the relevant failure type, trainer feedback quality is in question

## Input Contract
The redesigned outliner should receive:
- `scripture_reference`
- `training_level`
- `difficulty_class`
- `genre_hypothesis` when pre-assessed by the trainer
- `study_goal`
- `research_packet`
- `reference_librarian_notes`
- `theological_review_notes` when applicable
- `prior_fail_summary` for the same passage

## Output Contract
The redesigned outliner should produce a structured object with at least:
- `genre_classification`
- `genre_confidence`
- `segment_reference`
- `study_window_reference`
- `key_verse_reference`
- `why_these_verses`
- `textual_evidence_for_burden`
- `movement_from_previous_day`
- `day_burden`
- `theological_lane`
- `application_boundary`
- `week_turn_reason`
- `confidence`
- `open_questions`

## Evaluation Requirements
The final grader should score at least:
- segmentation quality
- key verse specificity
- broader-context preservation
- adjacent-day differentiation
- week-turn quality
- theological-boundary fidelity
- explainability quality
- use of librarian help

Passing model:
- use minimum thresholds per criterion, not only a composite score
- an outline with poor theological-boundary fidelity fails even if the composite is otherwise acceptable
- an outline with poor packet use fails input discipline even if the final outline looks polished

Anti-gaming checks:
- burden reuse clustering across passages
- confidence calibration against actual scores
- explanation quality on hold-out passages
- targeted revision specificity after coaching
- adversarial ambiguous-passage probes
- burden pressure test: could this burden appear on five unrelated passages without looking obviously wrong?

## Non-Negotiables
- no harness dependence as main curriculum
- no crutches
- no downstream rescue hiding outline weakness
- no repeated blind retries
- no acquisition escalation without library-trainer review
- no promotion to harder passages without stable evidence
- `differentiate_day_briefs()` may not be used to mask adjacent-day duplication during outliner evaluation
- `PassageCue` lookup behavior may not remain the primary source of burdens and lanes in the redesigned production outliner

## Immediate Recommended Changes
If we do not redesign everything at once, these are the minimum changes:

1. Stop raw fail stacking on the same passage.
2. Require reference-librarian and theological-reviewer input after the first failed outline.
3. Break the outline task into observation -> segmentation -> burden.
4. Track capability by difficulty level, not by total attempts.
5. Defer passages that exceed current capability instead of grinding them.
6. Add packet certification before Phase 1.
7. Add genre detection before segmentation.
8. Define stable passing numerically before curriculum automation.

## Review Questions For Another AI
1. Is the proposed phased architecture the right decomposition for an outlining worker?
2. What skills are still missing from the capability ladder?
3. Is the support order correct: theological reviewer -> librarian -> trainer?
4. What evaluation signals would best detect real learning vs. metric gaming?
5. Should segmentation and burden be separate workers, or phases of one worker?
6. What is the best way to decide when a passage should be deferred?
