# Stage 1 Design Brief — Argumentative Text Outlining

**Prepared by:** Grok
**Date:** 2026-03-25
**Status:** Awaiting Outliner Trainer and Theological Reviewer approval before proposal is written
**Governance:** Option B — trainers must approve this design basis before any proposal code is written

---

## 1. Text-Type Classifier — What It Must Do and Boundary Cases

**Must do:** Classify the input scripture passage as one of: Narrative / Ethical-Didactic /
Cumulative Argument / Mixed — before the outliner generates its structural template.

The current genre detection in `reasoning_outliner_core.py` (lines 42-59) is coarse:
poetry/psalms, wisdom/proverbs-job, prophecy, epistle/NT letters, narrative. It does not
distinguish between text types within those broad genre categories — a Hebrews passage and
a Romans ethical section both classify as "epistle" but require different structural handling.

**Implementation approach under consideration:** Extend the existing classifier with a
per-passage fine-grained type detection step. Possibly LLM-based for accuracy, or heuristic
(key-term density, clause structure). Evaluation via the existing harness passages
(`outliner_training_agent.py` lines 74-86).

**Boundary cases needing trainer input:**

| Passage | Classification question |
|---|---|
| Romans 12:1 | Imperative + doctrinal motivation in same verse — command or cumulative argument? |
| Psalm 23 | Shepherd imagery + promise + warning — poetry or mixed? |
| Ezekiel 37-39 | Valley narrative (ch. 37) + oracle/warning (ch. 38-39) — how to classify within-passage shifts? |
| Luke 15 | Parable vs. straight narrative — same classifier bucket or distinct? |
| Hebrews 5:11-6:12 | Exhortation interrupting argument — classify the interruption as warning or as argument continuation? |

**Questions for Outliner Trainer:**
- What is the authoritative classification rule for Hebrews 1-10? Should the classifier
  see the entire passage context or classify day by day?
- For "Mixed" type passages, does the classifier need to flag which days are argumentative
  and which are exhortation? Or classify the whole passage as its dominant type?
- Should Luke 15 parable + Romans ethical-didactic be separated into distinct classifier
  outputs, or collapsed into a single "mixed" category?

**Questions for Theological Reviewer:**
- Does the warning passage classification (Heb 6:4-6, 10:26-31) need to be a distinct
  type, or does "Cumulative Argument with embedded exhortation" cover it adequately?
- Are there theological reasons to classify passages differently than their structural
  genre would suggest?

---

## 2. Cumulative Argument Template — What It Must Enforce and Implementation Questions

**Must enforce (based on Hebrews Baseline and Outliner Trainer criteria):**

Day-by-day progression within each week following logical antecedent logic:
- Day 1: Opens a question or tension — does not begin with the answer
- Days 2-4: Sequential argument steps — each day must have a "Because we established [Day N],
  today we address [Day N+1]" sentence
- Day 5: Lands at a distinct location from Day 1 in the argument, not merely adds detail

Week-to-week escalation:
- Each week's conclusion provides the necessary premise for the next week's opening
- Stakes escalate from Week 1 to Week 5
- Warning passages appear as structural beats within the argument, not as application days

**Questions for Outliner Trainer:**
- What is the required JSON schema for the template? Suggested fields:
  `arg_step`, `warning_slot`, `cum_arg_summary` — is this right?
- How is "progression" enforced mechanically? Percentage of days advancing prior argument?
  Or qualitative trainer review?
- How are multi-week cumulative threads tracked across the 5-week / 30-day scope?
- Should the template hard-fail if no logical progression is detectable, or flag for
  trainer review?
- How do week-turn signals work in the current harness (e.g., `PASSAGE_FOCUS 'week turn'`)?

**Questions for Theological Reviewer:**
- Does the warning passage "structural beat" requirement mean the template must reserve
  a specific day slot for exhortation passages, or should the template detect and position
  them based on the text?
- How should the template handle Week 3's structure specifically: the Melchizedek argument
  is interrupted by the maturity warning (5:11-6:12). The warning is mid-argument, not
  end-of-argument. Does the template need a "mid-week warning" slot distinct from the
  normal warning positioning?

---

## 3. Current Outliner Architecture Constraints

The following constraints affect what is feasible in Stages 1 and 2. Trainers should
know these before approving the design.

**Deterministic reasoning path (default):**
`DEVG_OUTLINER_MODE=reasoning` (set in `outliner_adapter.py` lines 18-75). The production
outliner does not use LLM by default — templates anchor on `key_terms` and `focus_clause`.
Adding a text-type classifier must be compatible with this deterministic path.

**Optional LLM burden/lane:**
`llm_outliner_core.py` has `_BURDEN_LANE_PROMPT` for cross-provider evaluation. A
classifier could use LLM here if needed — but this is optional, not the default path.

**Training harness:**
12 fixed `HARNESS_PASSAGES` in `outliner_training_agent.py`. The text-type classifier
will be evaluated against these. Current pass rate: 137/939 (14.6%); 3 consecutive
passes toward 100-gate (as of 2026-03-24 supervisor cycle).

**No sub-verse classification currently:**
Clause splitting is simple (lines 25-26 of `reasoning_outliner_core.py`). The classifier
must work at the passage level, not sub-verse level, unless trainers determine finer
granularity is required.

**Recent performance:**
3/3 fails in the latest outliner training cycle (`2026-03-24__074424__devg__outliner-training-cycle.json`).
This is the baseline we are improving from.

---

## Approval Required Before Stage 1 Proposal is Written

Outliner Trainer: please approve or reject the classifier design and template enforcement
approach, and answer the implementation questions in your domain.

Theological Reviewer: please approve or reject the warning passage classification approach
and the Week 3 mid-week warning slot question.

Neither approval is advisory — if either domain rejects the design basis, no proposal
is submitted until the design is revised.
