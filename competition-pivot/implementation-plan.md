# Competition Pivot — Implementation Plan

**Status:** Active
**Created:** 2026-03-25
**Constraint:** All changes are additive. The multi-worker pipeline and training loop remain
intact. Nothing is removed or rewired for competition purposes.

---

## Strategic Context

DevG is continuing toward competition submission. The decision to concede or continue is
deferred until System B verifies at Hebrews 1-10 difficulty (the true competition-level test)
and a genuine timeline comparison can be made. This plan covers what DevG does in the
intervening period to maximize its readiness.

The competition submission gate is Hebrews 1-10: 30 days, 5 weeks, full pipeline, scored
against the Hebrews Passing Baseline (see `hebrews-passing-baseline.md`).

---

## Governance Model

| Stage | Model | Rationale |
|---|---|---|
| 0 — Unblock | **Option C** — Grok proposes, Claude applies | Operational, well-understood work |
| 1 — Argumentative Text Outlining | **Option B** — Team design before proposals | Classifier and template criteria are design inputs, not review items. Grok + Outliner Trainer + Theological Reviewer align before any proposal is written. |
| 2 — Arc Coherence Evaluation | **Option B** — Team design before proposals | Stage 2 checkpoints are downstream of Stage 1 structure. Must be designed together to avoid rubric divergence that surfaces at Stage 4. Outliner Trainer provides machine-readable rubric as design input before Grok touches implementation. |
| 3 — Downstream Worker Gates | **Option C** — Grok proposes, Claude applies | Training supervision; domain trainers score output, not design input |
| 4 — Full Hebrews Dispatch | **Option C** — Grok proposes, Claude applies | Execution and scoring stage |
| 5 — Submission Readiness | **Option C** — Grok proposes, Claude applies | Review and decision stage |

For Option B stages: Grok, Outliner Trainer, and Theological Reviewer complete a design
session. One shared design basis is produced. Grok then writes the proposal from that basis.
Claude applies. Domain trainers have approval authority over criteria in their domain —
their sign-off on Stage 1 and 2 designs is required before proposals are submitted.

---

## Architecture Constraint

> The focus on competition must not cause us to unwire the long-term architecture.

All stages below describe additions to the existing system. The worker training loop,
the training agent infrastructure, the DB schema, and the pipeline execution flow are
not changed. New capabilities are added as scaffolding on top of the existing structure.

---

## Stage Overview

| Stage | Name | Owner | Gate |
|---|---|---|---|
| 0 | Unblock | Grok + Claude | Zero stalls, supervisor running clean |
| 1 | Argumentative Text Outlining | Grok + Outliner Trainer | Outliner passes Hebrews classification + logical antecedent test |
| 2 | Arc Coherence Evaluation | Grok + Outliner Trainer | Arc coherence pass on Hebrews test run |
| 3 | Downstream Worker Gates | Grok + Trainers | All content workers ≥ 50 consecutive passes |
| 4 | Full Hebrews Dispatch | Grok + Claude | 100% pipeline completion, ≥ 90% pass rate |
| 5 | Submission Readiness | Grok + Claude | Hebrews volume scores ≥ 70% on Hebrews Baseline |

Stages 0 → 1 are prerequisites. Stages 2 and 3 can run in parallel after Stage 1 clears.
Stage 4 requires Stage 3 complete. Stage 5 requires Stage 4 complete.

---

## Stage 0: Unblock

**Owner:** Grok (diagnosis), Claude (DB execution)

**What work happens:**
- Archive remaining stalled Psalm 23 assignments in `autoresearch_experiments`
  (status='assigned' AND benchmark_reference LIKE 'Psalm 23%')
- Apply `grok_workspace/proposals/outliner_timeout_rootcause.py` to resolve API
  timeout hangs in the outliner training agent
- Confirm supervisor is cycling cleanly with outliner running last (post-reorder directive)
- Confirm 0 assigned/stalled rows remain before proceeding

**What changes:**
- DB write: archive stale assignments (reversible — archived rows are not deleted)
- Code: outliner timeout fix (additive — adds timeout handling, does not change worker logic)
- Supervisor order: outliner last (configuration change, not architectural)

**Validation Gate — Stage 0 Clear:**
- `SELECT COUNT(*) FROM autoresearch_experiments WHERE status = 'assigned'` returns 0
- Supervisor cycle completes without outliner blocking other workers
- No DB lock errors in the last 2 cycles

---

## Stage 1: Argumentative Text Classification and Outlining

**Owner:** Grok (prompt design), Outliner Trainer (review/approval), Claude (apply)

**What work happens:**
The outliner currently uses a single structural template that treats all texts similarly.
This works for narrative and ethical-didactic texts. It fails for cumulative arguments like
Hebrews, Romans 1-8, and Galatians 3-4.

A text-type classifier is added as a pre-processing step before outline generation:
- Classifies input text as: Narrative / Ethical-Didactic / Cumulative Argument / Mixed
- Hebrews 1-10 must classify as Cumulative Argument
- Classification activates the appropriate structural template

A new Cumulative Argument structural template is added to the outliner's template library.
The template enforces:
1. Logical antecedent requirement for each day transition (Day N must set up Day N+1)
2. Forward momentum check at each week boundary (each week must end at a different
   location in the argument than it began)
3. Escalation audit across weeks (each week's central contrast must carry higher stakes
   than the previous week's)
4. Warning passage positioning (exhortation passages are argument beats, not application days)

**What changes (additive):**
- New text-type classifier prompt in outliner's input processing layer
- New "Cumulative Argument" template in outliner's template library
- Existing Narrative and Ethical-Didactic templates unchanged

**Who does what:**
- Grok: Write the text-type classifier prompt and the Cumulative Argument template spec.
  Submit as a proposal to `grok_workspace/proposals/`.
- Outliner Trainer: Review and approve the template against the Hebrews Baseline criteria.
- Claude: Apply the approved proposal.
- Outliner Worker: Receives updated prompt architecture. No base model retraining needed.

**Validation Gate — Stage 1 Clear:**
On a test run using Hebrews 1-10 as input:
- Outliner correctly classifies the text as Cumulative Argument
- Outline uses the Cumulative Argument template (not the Narrative template)
- Logical antecedent sentence can be written for ≥ 4 of 5 weeks' day transitions
- No SF-1 through SF-6 failures present in the test outline

---

## Stage 2: Arc Coherence Evaluation (Parallel with Stage 3)

**Owner:** Grok (implementation), Outliner Trainer (rubric), Claude (apply)

**What work happens:**
The outliner's evaluation rubric currently assesses each week independently. For
argumentative texts, a week can pass independent evaluation and still fail when assessed
for its contribution to the 5-week arc.

An arc coherence evaluation pass is added *after* per-week evaluation. This pass evaluates:
1. Does each week's conclusion provide the necessary premise for the next week's opening?
2. Does the escalation pattern hold across all five weeks?
3. Does Week 5 function as arrival, not as setup for Hebrews 11?
4. Are all five Week-arc checkpoints met (from the Hebrews Baseline Section 4)?

Output of the arc coherence step: pass/flag/fail for each checkpoint plus a single arc
verdict (Pass / Revise / Fail). On Revise or Fail, the outline is returned with specific
checkpoint failures noted; the worker revises only flagged elements.

**What changes (additive):**
- New arc coherence evaluation step in outliner's output review process (runs after existing
  per-week evaluation, not instead of it)
- Five checkpoint rubric from Hebrews Baseline Section 4 implemented as machine-readable criteria
- Revision loop targets specific failed checkpoints, not a full outline regeneration

**Who does what:**
- Outliner Trainer: Provide the five checkpoint rubric in machine-readable form for Grok's
  implementation use.
- Grok: Implement arc coherence evaluation step as additive post-processing call. Submit as proposal.
- Claude: Apply approved proposal.

**Validation Gate — Stage 2 Clear:**
- Arc coherence evaluation runs automatically on a Hebrews test outline
- All five weekly arc checkpoints are evaluated and reported
- A Week 5 outline that functions as Hebrews 11 setup (SF-6) is correctly flagged as Fail
- A structurally sound test outline (prepared for gate testing) correctly receives Pass verdict

---

## Stage 3: Downstream Worker Gates (Parallel with Stage 2)

**Owner:** Grok (training supervision), domain trainers (scoring)

**What work happens:**
Content workers (Exposition Writer, Be Still Writer, Action Steps Writer, Prayer Writer)
must reach ≥ 50 consecutive passes at competition-level quality before the full Hebrews
dispatch run begins. This is the existing training loop — no new architecture needed.
The changes here are training focus, not structural.

**Training priorities by worker:**

*Exposition Writer:* Focus on argumentative text exposition — passages where the
theological argument is the primary structure (not narrative, not ethical instruction).
Expose to Hebrews-adjacent passages: Romans 1-4, Galatians 3-4. The failure mode to
address is application that imports themes rather than deriving them from the text's argument.

*Be Still Writer:* Address regression on epistolary passages (Colossians, Habakkuk failures).
Quotation validation and focal drift are the current failure patterns.

*Action Steps Writer:* Current contamination pattern must be resolved (focal quote corruption).
Proposals/completed/fix_action_focal_quote.py — verify applied and holding.

*Prayer Writer:* Burden fallback pattern and focal image drift must be addressed.
Proposals/completed/prayer_template_fix.md — verify implemented.

**What changes (additive):**
- Training corpus expanded to include argumentative epistle passages as training material
- No worker prompt architecture changes required (existing templates are sufficient;
  Stages 1-2 improve the upstream input the workers receive)
- Training continues under the existing supervisor cycle infrastructure

**Who does what:**
- Grok: Supervise training, assign argumentative text benchmarks, flag regressions
- Domain trainers: Score against competition-level standards (not degraded standards)
- Claude: Apply any proposals that emerge from training failures

**Validation Gate — Stage 3 Clear:**
- Exposition Writer: ≥ 50 consecutive passes, including ≥ 3 on epistle/argumentative passages
- Be Still Writer: ≥ 50 consecutive passes, no regression in last 10
- Action Steps Writer: ≥ 50 consecutive passes, contamination pattern absent in last 10
- Prayer Writer: ≥ 50 consecutive passes, burden fallback absent in last 10

---

## Stage 4: Full Hebrews Dispatch

**Owner:** Grok (supervision), Claude (gate review)

**What work happens:**
With Stage 0-3 gates cleared, the full Hebrews 1-10 volume (30 days, 5 weeks) is dispatched
through the complete pipeline. This is the first end-to-end run at competition difficulty.

The run should be treated as a diagnostic run, not a repair run. Score and report; do not
diagnose and fix during the run. If failures occur, Stage 4 is repeated after fixes, not
patched mid-run.

**Who does what:**
- Grok: Dispatch and supervise the full Hebrews run through the pipeline
- Claude: Review completion status, confirm gate criteria
- Theological Reviewer + Outliner Trainer: Score the output against the Hebrews Baseline

**Validation Gate — Stage 4 Clear:**
- 100% pipeline completion across all 30 days (no abandoned days)
- ≤ 5% stall rate across the volume
- ≥ 90% pass rate per worker across the volume
- No AC-03, AC-05, or AC-11 violations

---

## Stage 5: Submission Readiness and Competition Decision

**Owner:** Grok + Claude (joint review), operator (final decision)

**What work happens:**
The Hebrews output from Stage 4 is scored against the Hebrews Passing Baseline by the
Theological Reviewer and Outliner Trainer.

**The competition decision is triggered by System B, not by DevG's score alone.** When
System B passes the Hebrews Gate, DevG immediately assesses its current state and asks
one question: given that we have already missed the initial competition deadline, does it
make sense to request the remaining completion time from the competition?

This is not a simple numeric comparison. It accounts for:
- DevG's current stage and what realistically remains
- Whether the competition would consider a deadline extension credible
- Whether the ask is appropriate given the competitive context

The Hebrews score from Stage 4 provides the honest evidence base for that conversation.
A strong score strengthens the case for requesting an extension. A weak score does not.

**Validation Gate — Stage 5 Clear:**
- Hebrews volume scores ≥ 70% overall on the Hebrews Baseline weighted scoring framework
- No DF or SF failures present
- System B has run and passed the Hebrews Gate (triggers the competition decision)
- Operator makes final determination on whether to request completion time

---

## Prohibited During This Plan

The following are explicitly off-limits regardless of competitive pressure:

1. Removing or disabling any worker from the training loop
2. Replacing the training supervisor with a simpler hardcoded pipeline
3. Dropping the consecutive-pass graduation gate
4. Bypassing the Theological Reviewer or Outliner Trainer scoring in the evaluation process
5. Submitting a volume that has not cleared Stage 4

These constraints protect the long-term architecture from competition-driven shortcuts.
