# Outliner Execution Handoff

## Project Root
`/Volumes/claude-projects/projects/devotional-generator-system-a`

## Current Decision State
The system is in an `outliner-evaluation lock`.

Meaning:
- non-outliner worker training is paused
- the current question is whether the redesigned reasoning outliner can honestly replace the current production outliner
- the comparison mode is `adapter-first`, not direct replacement yet

Allowed active roles during this lock:
- `training_manager`
- `outliner`
- `library_trainer`
- `theological_reviewer`
- `policy_guardian`

Paused roles during this lock:
- `exposition_writer`
- `quote_selector`
- `passage_researcher`
- `be_still_writer`
- `action_writer`
- `prayer_writer`
- `pdf_art_director`
- `pdf_layout_engineer`
- `output_training_manager`
- `research_librarian` training cycles

## Core Diagnosis
The current production outliner is still primarily deterministic.

Primary files:
- `src/generation/editorial.py`
- `src/generation/outliner_resources.py`

Important verified facts:
- `PassageCue` lookups are still central
- `differentiate_day_briefs()` still patches adjacent-day duplication after the fact
- `key_verse_reference` still defaults to the full daily reference
- `study_window_reference` still defaults to the same daily reference unless widened upstream
- generic passages can fall back to `"faithful response to God's word"`

Conclusion:
- this is a production architecture problem, not just a training problem

## Main Review Docs
- redesign spec:
  - `/Volumes/claude-projects/projects/devotional-generator-system-a/docs/system/outliner-agent-redesign-spec.md`
- review handoff:
  - `/Volumes/claude-projects/projects/devotional-generator-system-a/docs/system/outliner-agent-review-handoff.md`

## Comparison DB Table
Special table now exists for old-vs-new outliner comparison:
- `outliner_system_comparisons`

It stores:
- assignment payload
- interaction log
- packet snapshot
- reviewer guidance
- artifact paths
- legacy system reference
- redesigned system reference
- statuses / scores / summaries / metrics
- decision rationale
- comparison notes

## Current Comparison State
System-level row exists:
- `cmp__outliner__production-vs-redesign__2026-03-16`

Passage-level scored rows now exist for:
- `Ruth 1`
- `Mark 2`
- `John 10`
- `Romans 5`
- `Philippians 2`

Current readout:
- scored comparisons now exist for `Ruth 1`, `Mark 2`, `John 10`, `Romans 5`, and `Philippians 2`
- after evaluator tightening, the redesigned outliner won all 5 scored comparisons
- legacy scores: `0.0` across the batch
- redesigned scores: `16.0` across the batch

Operational conclusion:
- the redesigned outliner structure is now the clear comparison winner
- next step is migration planning through the adapter path, not more winner-hunting

## Exact Commands

### Environment
```bash
cd /Volumes/claude-projects/projects/devotional-generator-system-a
```

### Monitor
```bash
scripts/autoresearch/devg-watch-live
```

### Menu
```bash
scripts/autoresearch/devg-menu
```

### Start training loop
```bash
scripts/autoresearch/devg-start-training-loop 20
```

### Stop training loop
```bash
scripts/autoresearch/devg-stop-training-loop
```

### Run supervisor once
```bash
.venv/bin/python scripts/autoresearch/run_training_supervisor.py
```

### Run outliner training cycle once
```bash
.venv/bin/python scripts/autoresearch/run_outliner_training_cycle.py --limit 1
```

### Run first comparison / feasibility check
```bash
.venv/bin/python scripts/autoresearch/run_outliner_system_comparison.py --passage 'Ruth 1' --days 6 --weeks 1
```

### Query comparison rows
```bash
.venv/bin/python - <<'PY'
from src.autoresearch.store import list_outliner_system_comparisons
for row in list_outliner_system_comparisons():
    print(row.comparison_id, row.passage_slug, row.decision_status)
PY
```

### Query outliner experiment rows
```bash
.venv/bin/python - <<'PY'
from src.autoresearch.store import list_experiments
rows = [r for r in list_experiments(worker_name='outliner') if r.benchmark_name.startswith('outline-only-')]
for row in rows[-10:]:
    print(row.status, row.benchmark_reference, row.benchmark_name, row.created_at_utc)
PY
```

### Targeted tests for comparison path
```bash
.venv/bin/pytest tests/autoresearch/test_outliner_system_comparison.py tests/test_registry.py::TestAutoresearchLedger::test_outliner_system_comparisons_survive_restart -q
```

## Important Current Constraint
Do not pretend the redesigned outliner is already independent.

Right now `src/autoresearch/outliner_training_agent.py` still imports and uses legacy editorial core functions:
- `build_editorial_day_brief`
- `build_editorial_artifact`
- `differentiate_day_briefs`

That must be addressed before a fair scored old-vs-new comparison can happen.

## Recommended Next Engineering Step
Build an actually independent reasoning outliner path that does not rely on the legacy editorial core for:
- burden derivation
- day brief construction
- adjacent-day differentiation

Only after that should the comparison program move from:
- `blocked_shared_core_dependency`

to:
- real scored old-vs-new comparison

## If A Third-Party Review Is Needed
Use:
- redesign spec
- review handoff
- this execution handoff
- comparison table rows

That should avoid requiring a full system rediscovery.
