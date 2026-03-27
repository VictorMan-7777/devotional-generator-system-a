# Directive: Design the AC Scoring System

We have a gap that needs to be closed before the competition brief can be finalized: workers currently log only a trainer-based score per experiment. We need each worker to also log an AC-based score so the competition director can see both signals.

## Background

The competition is evaluated against AC-01 through AC-43 from PRD v16. Those are the acceptance criteria that judge whether the devotional output is submission-ready. Right now, trainers evaluate workers using their own rubrics (passage faithfulness, structure, tone, etc.). Those are training signals, not competition signals. We have no direct visibility into how the output is performing against the actual AC criteria.

## What already exists

`src/validation/` has four deterministic validators already written:
- `exposition.py` — checks word count (500–700), voice (we/us not you/your), Grounding Map completeness
- `be_still.py` — checks prompt count (3–5), second-person voice presence
- `action_steps.py` — checks item count (1–3), connector phrase presence
- `prayer.py` — checks word count (120–200), Trinity address, Prayer Trace Map completeness

These validators exist but are NOT connected to the training experiment logging. They're used in the generation pipeline but workers don't know about them.

## What's needed

Design an approach where each worker experiment logs two scores:
1. **Trainer score** — the existing LLM trainer evaluation (what we have now)
2. **AC score** — a structured AC pass/fail against the relevant acceptance criteria for that worker's section

AC mapping by worker:
- Exposition writer → AC-01 through AC-11 (structure, voice, word count, etc.)
- Be Still writer → AC-12 through AC-17 (prompt count, voice, inward-to-outward, etc.)
- Action writer → AC-18 through AC-20b (connector phrase, count, expectation)
- Prayer writer → AC-21 through AC-32 (Trinity address, word count, traceability, etc.)
- Outliner → no direct AC (structural planning, not final content)
- PDF workers → AC-38 (KDP compliance)
- Passage researcher → AC-36 (scripture retrieval accuracy)

Some ACs can be checked deterministically (word counts, structural counts, pattern matching). Others require semantic judgment and should be marked as `requires_review` or skipped in automated scoring for now — be explicit about which you're handling and which you're deferring.

The output format should be something `log_experiment` can carry — either as part of the `metrics` dict or as a new field. The format needs to be queryable: we need to be able to produce a per-AC pass rate across all experiments for a given worker.

## Constraints

- Build on `src/validation/` — don't rewrite what exists
- The `log_experiment` function in `src/autoresearch/store.py` is the single logging path; any new field needs to thread through there
- The solution must be a complete, runnable file (no stubs, no `# rest unchanged`)
- Worker training agents are in `src/autoresearch/`

## What to design

Propose:
1. How the AC scores are computed per worker (which ACs, which are deterministic vs. deferred)
2. How the result is structured (what fields, what format)
3. Where the computation happens (a new `ac_scorer.py`? inside each agent? called from store.py?)
4. How `log_experiment` or the DB schema carries the new field
5. Which worker agents need to be updated and how

You know the system. Design the approach. Submit a complete proposal — if it touches multiple files, include all of them. No stubs.
