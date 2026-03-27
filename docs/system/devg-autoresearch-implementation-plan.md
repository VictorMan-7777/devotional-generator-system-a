# DevG Autoresearch Implementation Plan

## Purpose

This document describes the worker-training architecture for DevG autoresearch.

## Production target

The training manager should evaluate worker readiness against a seminary-level production standard.

That means production workers should display:
- passage sensitivity
- theological care
- genre-aware judgment
- responsible source use
- literary seriousness appropriate for paid devotional publishing

The target is not "acceptable AI output."
The target is a dependable production assistant that works like a well-trained seminary aide.

## Core architectural rule: agents are AI agents

**Every position called an "agent" makes real AI calls (Claude or Codex). No exceptions.**

This was established 2026-03-16 after discovering that all workers were deterministic Python templates with no AI calls. That produced a training loop with no signal — the outliner scored 16 on every passage because templates triggered scaffold penalties, not because the AI was bad.

The design intent is:
1. AI agents generate high-quality content by calling Claude or Codex.
2. Training evaluates the AI output and scores it.
3. Over time, training data accumulates and deterministic templates improve.
4. Eventually the templates match AI quality and AI calls are no longer needed.

The AI agents are the experienced workers who train the system. They are not production code shortcuts. They are the source of the training signal.

## LLM infrastructure

All LLM access goes through `src/llm/`:

```
src/llm/
  interfaces.py      — LLMClient protocol (generate(prompt: str) -> str)
  claude_client.py   — Anthropic SDK client
  codex_client.py    — OpenAI SDK client
  router.py          — Routes by DEVG_LLM_PROVIDER; per-worker overrides
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DEVG_LLM_PROVIDER` | `claude` | Primary provider: `claude` or `codex` |
| `ANTHROPIC_API_KEY` | — | Required for Claude |
| `OPENAI_API_KEY` | — | Required for Codex |
| `DEVG_CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model override |
| `DEVG_CODEX_MODEL` | `gpt-4o` | Codex model override |
| `DEVG_LLM_OUTLINER` | — | Per-worker override for outliner |
| `DEVG_LLM_EXPOSITION_WRITER` | — | Per-worker override for exposition writer |
| `DEVG_LLM_THEOLOGICAL_REVIEWER` | — | Per-worker override for theological reviewer |
| `DEVG_LLM_GRAMMAR_ADVISOR` | — | Per-worker override for grammar advisor |
| `DEVG_LLM_LIBRARY_TRAINER` | — | Per-worker override for library trainer |
| `DEVG_LLM_QUOTE_SELECTOR` | — | Per-worker override for quote selector |
| `DEVG_LLM_BE_STILL_WRITER` | — | Per-worker override for be still writer |
| `DEVG_LLM_ACTION_WRITER` | — | Per-worker override for action writer |
| `DEVG_LLM_PRAYER_WRITER` | — | Per-worker override for prayer writer |

Per-worker overrides allow splitting workers across Claude and Codex to avoid rate limits.

**Note:** The policy guardian does not have an LLM override — it is a law-follower, not an AI judgment agent. See below.

### Worker modes

Some workers have an adapter layer that can route between LLM, reasoning (deterministic fallback), or legacy:

```
DEVG_OUTLINER_MODE=llm        # default — actual AI calls
DEVG_OUTLINER_MODE=reasoning  # deterministic fallback (no API key needed)
DEVG_OUTLINER_MODE=legacy     # original PassageCue path (comparison baseline only)
```

## Scope

Autoresearch in DevG does not mean unrestricted code mutation. It means controlled worker improvement with:
- a scoped worker surface
- stable benchmarks
- objective metrics
- keep/discard decisions
- durable experiment records

## Library

The shared Agentic RAG is the library.
- The resource store is the library itself.
- The general librarian maintains and catalogs resources.
- The research librarian answers passage-specific worker requests.
- The live library catalog lives at `data/library/resource-catalog.json`.
- Example cards live at `data/library/resource-catalog.examples.json`.
- The librarians should have idle-duty work even when no generation request is active.
- Unless a time-sensitive request interrupts, the general librarian's first priority is to acquire the full parent resources behind existing quote/excerpt cuttings.
- The librarian training cycle continues until every cutting source is backed by an acquired resource and an accepted live card.
- After the initial bootstrap, librarian effort should prioritize real worker needs: acquire, card, shelve, and fulfill requests before any optional shelf-reading work.

## Policy guardian

The policy guardian is the compliance cop. It is an LLM agent whose authority comes
exclusively from the written law — it does not invent rules, but it needs LLM capability
to actually read and evaluate agent artifacts against the law intelligently.

A deterministic rule-checker can only verify file existence and fail counts. The cop needs
to read what agents are actually producing and apply the written laws to those outputs.

It:
- Is an LLM agent backed by Claude or Codex (route: `DEVG_LLM_POLICY_GUARDIAN`)
- Reads the rules-laws constitution (Tier 0) and federal laws (Tier 1, L1–L16) as its authority
- Reads actual agent output artifacts and evaluates them against the written law
- Follows any local laws in the repo's `.laws/` directory (Tier 3, currently none)
- Does NOT extrapolate, interpret, or invent rules — authority is the written law only
- When it encounters a situation not covered by written law, it records "no applicable law" and escalates (Art. 1.2)
- When it enforces a repo practice that lacks a ratified law, it writes a gap annotation to `rules-laws/proposed/` for the amendment process

Currently enforced laws:
- **L2** — Evidence Gate: every training session must produce a reviewable output artifact
- **L15** — Retry/Stop Policy: identical failures capped at 3; must halt and escalate after cap

Laws are still in development. The guardian enforces what is written and annotates what is missing.

## Worker order and training state

| Worker | Type | LLM | Training state |
|---|---|---|---|
| training_manager | orchestrator | no (deterministic) | always running |
| output_training_manager | orchestrator | no (deterministic) | always running |
| policy_guardian | law enforcer | **yes** ✅ | always running |
| theological_reviewer | evaluator | **yes** ✅ | always running |
| grammar_advisor | evaluator | **yes** ✅ | always running |
| library_trainer | evaluator | **yes** ✅ | always running |
| research_librarian | resource prep | **yes** ✅ | active |
| outliner | content generator | **yes** ✅ | active (`llm` mode default) |
| exposition_writer | content generator | **yes** ✅ | active (LLM benchmark gate) |
| pdf_layout_engineer | output | no (engine tests) | **graduated** (54 consecutive passes) |
| pdf_art_director | output | no (engine tests) | active (54 consecutive fails) |
| quote_selector | content generator | route registered | waiting |
| be_still_writer | content generator | route registered | waiting |
| action_writer | content generator | route registered | waiting |
| prayer_writer | content generator | route registered | waiting |
| acquisition_librarian | acquisition | pending | active |

**Pending** = position exists, role defined, LLM wiring not yet implemented.
**Route registered** = router entry exists for future activation; training agent not yet created.

## Starting and stopping the training loop

```bash
# Start (from repo root)
scripts/autoresearch/devg-start-training-loop

# Monitor
scripts/autoresearch/devg-watch

# Suspend all training (monitoring workers continue)
# Set SUPERVISOR_SUSPENDED["enabled"] = True in:
scripts/autoresearch/run_training_supervisor.py
```

When training is suspended, the monitoring workers (theological_reviewer, library_trainer, policy_guardian) continue running. Only content generation training halts.

To resume after a full agent update:
1. Ensure `ANTHROPIC_API_KEY` is set in the training loop environment
2. Set `SUPERVISOR_SUSPENDED["enabled"] = False`
3. Set `OUTLINER_TRAINING_PAUSED["enabled"] = False` (if outliner was separately paused)
4. Run `devg-start-training-loop`

## Worker contracts

### Outliner
Owns:
- genre detection
- natural day boundaries
- week turns
- burden assignment
- passage movement
- deciding when to request research-librarian help
- receiving outline-only assignments from an expert outliner-training agent

Implementation: `src/autoresearch/outliner_adapter.py` → `src/autoresearch/llm_outliner_core.py`

Benchmarks: Exodus 19-20, Proverbs 1-2, Acts 9, Habakkuk 1-3

Metrics: BOOK_DAY_PROGRESS, BOOK_WEEK_TRANSITION, BOOK_THEOLOGICAL_BOUNDARY, harness pass rate

Pass threshold: score >= 85

### Exposition writer
Owns:
- exposition research
- paragraph construction
- readability (target grade ≤ 8)
- passage-faithful devotional prose

Implementation: `src/autoresearch/exposition_training_agent.py` → `src/autoresearch/llm_exposition_core.py`

Training: LLM generates a fresh exposition for a benchmark passage; scorer evaluates word count, scaffold avoidance, passage anchoring.

Pass threshold: LLM benchmark score >= 80

Benchmark passages: Habakkuk 1:2-4, Colossians 3:1-4, Psalm 23:1-4, Luke 15:11-24, Ruth 1:16-17

### Quote selector
Owns: quote suitability, citation completeness, source-search order, duplicate avoidance

Benchmarks: Psalms 23-25, Exodus 19-20, Colossians 3-4

Metrics: complete Turabian rate, duplicate quote failure rate, validator quote pass rate

### General librarian
Owns: library acquisition, cataloging readiness, metadata normalization, shelving resources

Benchmarks: Habakkuk 1-3, Luke 15, Colossians 3-4

### Research librarian
Owns: passage-specific research, shared bundle preparation, acquisition handoff when library is thin

Role: seminary reference librarian — not a training evaluator. Runs in the generation pipeline
(not autoresearch). Acts as the intelligence layer between the RAG catalog and the workers
who depend on it. Knows the collection, understands passage genre, annotates each resource
with passage-specific notes, identifies gaps, and triggers acquisition escalation.

Implementation: `src/rag/research_librarian.py` → `src/rag/llm_research_librarian_core.py`

Benchmarks: Exodus 19-20, Luke 15, Colossians 3-4

### Be Still writer
Owns: meditative stillness prompts, passage anchoring in stillness language, devotional calm without generic drift

Benchmarks: Habakkuk 1-3, Psalms 23-25, Exodus 19-20

### Action writer
Owns: concrete action steps, text-shaped application, resistance to vague moralism and productivity drift

Benchmarks: Luke 5-6, Proverbs 1-2, Colossians 3-4

### Prayer writer
Owns: closing prayer tone, theological boundary in prayer, passage-faithful devotional response

Benchmarks: Habakkuk 1-3, Ezekiel 38-39, Psalms 23-25

### PDF art director
Owns: title page quality, introduction presentation, day-start hierarchy, typography scale, premium visual direction

Status: 54 consecutive fails as of 2026-03-16. Active bottleneck.

### PDF layout engineer
Owns: pagination stability, overflow prevention, KDP-safe margins, reviewed-proof watermarking

Status: **Graduated** (54 consecutive passes as of 2026-03-16). Re-open training only if regression appears.

### Theological reviewer
Owns: expert review of theological writing, doctrinal boundaries, quote appropriateness

Implementation: `src/autoresearch/theological_reviewer_agent.py` → `src/autoresearch/llm_theological_reviewer_core.py`

Runs three sequential stages: (1) resource review, (2) quote review, (3) content review.
Each stage must clear before the next proceeds. The LLM benchmark evaluates the exposition writer's
output for passage faithfulness, theological drift, and doctrinal boundary compliance.

Pass threshold: LLM score >= 80. Deterministic stage checks (resource strength, quote validation,
book-level theological failures) are supporting context, not independent gates.

### Grammar advisor
Owns: expert review of grammar, paragraph clarity, sentence rhythm, readable prose quality

Implementation: `src/autoresearch/grammar_advisor_agent.py` → `src/autoresearch/llm_grammar_advisor_core.py`

Works alongside the theological reviewer as a coaching pair for the exposition writer.
The LLM benchmark evaluates the exposition writer's output for prose clarity, sentence variety,
and mechanical discipline. Deterministic regex checks (long sentence count, repeated openings)
are supplementary signals.

### Library trainer
Owns: evaluation of research librarian reading notes, note quality, shelf utilization discipline

Implementation: `src/autoresearch/library_trainer_agent.py` → `src/autoresearch/llm_library_trainer_core.py`

LLM evaluates reading notes for specificity, passage awareness, and accomplished vs beginner behavior.
Up to 5 notes evaluated per cycle. Deterministic checks (blank/metadata packets, pending requests)
run alongside the LLM evaluation.

### Policy guardian
Owns: compliance enforcement against written law only (constitution + federal laws + local laws)

Does NOT own: training quality judgment, worker improvement assessment, rule interpretation.

See policy guardian section above for full description.

## Persistence

All experiment records persist through `src/autoresearch/store.py`.

Minimum experiment fields:
- experiment id
- worker name
- benchmark name
- benchmark reference
- status
- attempted change summary
- metrics payload
- learning note
- keep/discard decision
- timestamps

## Loop design

1. Load worker spec.
2. Prepare the shared passage library bundle through the research librarian.
3. Pick one benchmark passage.
4. Invoke the AI agent (LLM call via `get_llm_client(worker=...)`).
5. Score the AI output against the worker's rubric.
6. Log the experiment record (keep or review).
7. If fail: step down, change method, or escalate — do not retry identically (L15).

Hard-coded passage cues are debt and should be removed, not expanded.
The target is AI agent generation backed by library resources, evaluated by objective scoring.
