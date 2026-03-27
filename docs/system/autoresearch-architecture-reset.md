# AutoResearch Architecture Reset
_Written: 2026-03-19. For retrieval after NAS migration by a new Claude CLI session._

---

## Context

Training was stopped on 2026-03-19 after ~3 days of running. A strategic discussion with ChatGPT identified that the training loop has been in "insanity mode" — looping without a frozen metric or real improvement mechanism. This document captures the full diagnosis, what was built, what is broken, and the decision points that need to be resolved before training restarts.

---

## What the System Currently Does

The DevG autoresearch system runs a training supervisor loop that fires individual worker training cycles every ~20 seconds. Each cycle:

1. Calls a "trainer" LLM (Claude Haiku, previously Sonnet) to evaluate the worker's output
2. Logs the evaluation to an SQLite experiment store (`data/devg_registry.sqlite3`)
3. The loop reads experiment history and tries to improve

### Workers and their current state (as of 2026-03-19 shutdown)

| Worker | Experiments | Passes | Status |
|--------|-------------|--------|--------|
| outliner | ~620 | 17 | ❌ BOTTLENECK — trainer loops without improvement |
| exposition_writer | ~1,270 | 0 | ❌ 0 passes ever |
| passage_researcher | 557 | 536 | ✅ GRADUATED (444 consecutive passes) |
| pdf_art_director | ~146 | ~107 | 🟢 73% pass rate — healthy |
| pdf_layout_engineer | 22 | 19 | ✅ GRADUATED |
| be_still_writer | 94 | 0 | ❌ 0 passes — deterministic template, no improvement mechanism |
| action_writer | 94 | 0 | ❌ 0 passes — deterministic template, no improvement mechanism |
| prayer_writer | 0 | 0 | 🔵 Training agent built, never started |
| research_librarian | ~184 | — | 🟢 Running passively |

---

## The Core Problem: No Frozen Evaluator

### What ChatGPT diagnosed

The training system has LLM trainers evaluating LLM-generated workers. This is LLM-to-LLM evaluation with no frozen ground truth. The evaluator is as capable of being wrong as the worker. This is not an experiment loop — it is recursive self-modification with no anchor.

Specific problems identified:

1. **No frozen evaluator** — the trainer is an LLM, so scores drift based on prompt wording and model temperature
2. **No novelty requirement** — the loop retries the same approach without requiring something different
3. **No actual improvement mechanism** — for deterministic workers (Be Still, Action Steps), the trainer evaluates and logs but nothing changes; next cycle is identical
4. **Proxy optimization** — the system optimizes for "what satisfies the LLM reviewer" not "what is actually better devotional content"
5. **No hard stop conditions with strategic change** — gate reviews were added but they're still LLM-to-LLM

### The insanity loop evidence

- `outliner`: 620 experiments, only 17 passes, no upward trend
- `be_still_writer`: 94 experiments, 0 passes, trainer identifies same problems every cycle, nothing changes
- `action_writer`: 94 experiments, 0 passes, same pattern

The trainer is saying "these steps are generic" every single cycle. But "generic" is a property of the deterministic template, not something training can fix. The template is code. The trainer cannot change code.

---

## What the System Gets Right (Keep These)

These elements align with proper AutoResearch architecture and should be preserved:

- **Attempt ledger** — `src/autoresearch/store.py` with `log_experiment()`, `list_experiments()`. Every attempt is logged with: experiment_id, worker_name, benchmark_name, benchmark_reference, status, metrics, learning_note, keep_decision.
- **Fixed benchmark passages** — `HARNESS_PASSAGES` in `outliner_training_agent.py` — a repeatable test set that doesn't change
- **Deterministic pre-checks** — score components that a Python function can evaluate: structural validity, verse count, section presence, etc.
- **Infeasibility detection** — `count_passage_verses()` deterministic pre-check; Ruth 1 / 18-day = 1.2 verses/day = task_infeasible, logged without LLM call
- **Graduation threshold** — `passage_researcher` graduated when consecutive pass streak hit 200. This worked because the metric was deterministic (did retrieval succeed: yes/no).
- **Gate reviews at 50-experiment intervals** — `src/autoresearch/llm_gate_review_core.py`. The gate review detects stall patterns. The problem is it's LLM-to-LLM, but the structure is right.

---

## What Needs to Change Before Restarting

### 1. Define frozen metrics for each worker

The passage_researcher graduated because its metric was concrete: "did it return valid scripture text — yes or no." No LLM involved.

Every other worker needs the same thing. The metric must be:
- Deterministic (same input → same score every time)
- Not LLM-judged
- Specific enough that a score of 80 means something real

**Open question for the operator to resolve before training restarts:**

For each worker, what is the frozen metric?

- **Be Still**: What does a passing Be Still section look like in terms a Python function can check? Candidates: does it reference the specific passage text? does it end with an open question (not a resolution)? does it avoid imperative mood? These are checkable without an LLM.
- **Action Steps**: Does each step contain a specific verb + object? Does none of the steps use words that appear in every devotional ("pray about", "reflect on", "seek God")? Does at least one step reference a noun from the passage text?
- **Exposition**: Word count in range? Theological terms present? No sentence longer than 40 words? Passage reference appears in first paragraph?
- **Outliner**: All required keys present? Day count matches template? Week structure valid? Commentary citation present?

### 2. LLM proposes, deterministic system decides

The ChatGPT framework that is correct:

> LLMs should PROPOSE. System should DECIDE.

The LLM trainer should generate:
- A specific, actionable proposed change (not a vague "improve this")
- The deterministic test that would prove improvement

The system then:
- Applies the change
- Runs the frozen metric
- Keeps or rejects based on score delta

The LLM never decides whether the change worked. Only the frozen metric decides.

### 3. Consider local LLM for generative workers

The user is paying ~$25/week in Anthropic costs for training that shows no measurable improvement. ChatGPT recommended:

> Use existing local model (inference, not training) → Build one worker with strict contract → Add benchmark + scoring → Improve via prompt/schema/tooling → Only then consider fine-tuning

A local model (Ollama with Mistral 7B, Llama 3.1 8B, or similar) would:
- Eliminate API cost for training entirely
- Remove rate limits and credit depletion problems
- Allow unlimited iteration
- Run offline on the Mac Studio

Fine-tuning (LoRA/QLoRA) would only be considered after:
- Workers have stable prompts
- Failures are consistent and pattern-identifiable
- A dataset of known-good outputs exists

### 4. For deterministic workers: trainer must produce code diffs

Be Still and Action Steps are Python template functions in `src/generation/real_section_generator.py`. They will always produce generic output unless the code changes. The trainer cannot change code through evaluation alone.

Two options:
- **Option A**: The LLM trainer generates a specific code diff (change this function, change this template string) which is applied, and the frozen metric determines if it improved
- **Option B**: Convert Be Still and Action Steps to local LLM-generated (not deterministic), and train via prompt iteration

Option A keeps the architecture constraint (deterministic workers). Option B is faster to show improvement. The operator needs to decide.

---

## The Anti-Pattern to Avoid

The current system's loop is:

```
generate output → LLM evaluates → log "revise" → repeat
```

This is not training. Nothing changes between cycles for deterministic workers. For LLM workers, the loop has leverage only if the prompt/system message changes between cycles — which it currently does not.

The correct loop is:

```
generate output → frozen metric scores → IF below threshold: LLM proposes specific change → apply change → frozen metric scores again → keep if improved, reject if not → log both attempts
```

The frozen metric is the anchor. The LLM is the change-proposal engine, not the judge.

---

## Files Modified in the Last Session (2026-03-18 to 2026-03-19)

These were the last changes made before the NAS migration pause:

- `src/llm/claude_client.py` — fallback to OpenAI on `BadRequestError` (credit balance errors), `RateLimitError`, and `OverloadedError`. Default model changed from `claude-sonnet-4-6` to `claude-haiku-4-5-20251001`.
- `src/scripture/planner.py` — added `count_passage_verses()` public helper
- `src/autoresearch/outliner_training_agent.py` — deterministic infeasibility pre-check in `run_outline_assignment()`: if verse_density < 1.5, log `task_infeasible` and return without any LLM call
- `src/autoresearch/llm_outliner_core.py` — added `build_llm_passage_selection()` for LLM-driven passage selection (replaces static JSON file); density guard client-side
- `src/autoresearch/llm_gate_review_core.py` — new: gate review at every 50 experiments
- `scripts/autoresearch/run_gate_reviews.py` — new: runs gate reviews
- `scripts/autoresearch/run_acquisition_librarian_cycle.py` — new: processes ALL pending acquisition requests (not filtered by requested_by)
- `src/autoresearch/training_manager.py` — passage_researcher graduation fix; gate status tracking
- `scripts/autoresearch/run_training_supervisor.py` — gate_reviews step, acquisition_librarian step, be_still/action/prayer wired every cycle
- `src/autoresearch/llm_prayer_writer_core.py` — new trainer
- `src/autoresearch/prayer_writer_training_agent.py` — new agent
- `scripts/autoresearch/run_prayer_writer_training_cycle.py` — new run script
- `docs/system/nas-migration-plan.md` — pre-move checklist with live DB location (`~/Library/Application Support/DevG/devg_registry.sqlite3` on Mac Studio, 562MB)

---

## What the New Claude Session Should Do First

After NAS migration, before touching any training code:

1. **Read this document**
2. **Read** `docs/system/training-status.md` for current worker state
3. **Read** `docs/system/nas-migration-plan.md` to confirm migration completed correctly
4. **Verify** the DB is accessible at its new NAS path and `DEVG_DB_PATH` is updated in environment
5. **Do not restart training** until the operator has resolved: "What is the frozen metric for each worker?"

The operator (user) said they would think about the metrics during the NAS migration. That discussion needs to happen first. Training should not restart in "insanity mode."

---

## Summary Judgment

The system has good bones:
- Experiment ledger ✅
- Benchmark harness ✅
- Graduation logic ✅
- Infeasibility detection ✅

The system has a fundamental flaw:
- LLM-judged quality is not a frozen metric
- Deterministic workers cannot improve through evaluation alone
- The loop has been measuring without improving

The fix is not more training cycles. The fix is defining what "better" means in terms a Python function can verify — and then building a loop where the LLM proposes specific changes that get tested against that definition.

---

_End of document. Written for handoff to new Claude CLI session post-NAS migration._
