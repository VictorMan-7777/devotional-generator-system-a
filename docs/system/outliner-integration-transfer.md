# Outliner Integration Transfer

## Project Root
`/Volumes/claude-projects/projects/devotional-generator-system-a`

## Purpose Of This Transfer
This file is the handoff to the next AI that will integrate the winning outliner approach into production and then resume broader worker training.

This file is intentionally compact and points to supporting files where more detail already exists.

## Executive Summary
A real old-vs-new outliner comparison was run.

Result:
- the **redesigned reasoning outliner** is the clear winner over the current deterministic production outliner
- comparison batch: `Ruth 1`, `Mark 2`, `John 10`, `Romans 5`, `Philippians 2`
- final readout:
  - redesigned wins: `5`
  - legacy wins: `0`
  - ties: `0`

Important nuance:
- both systems still need improvement
- the redesigned system won because the evaluator was tightened to measure textual anchoring and penalize generic scaffold language
- the right next step is **integration through the adapter path**, not further winner-hunting

## What Was Actually Learned
### 1. The original blocker was real
The production outliner is still primarily deterministic.

Main files:
- `src/generation/editorial.py`
- `src/generation/outliner_resources.py`

The production path still depended on:
- `PassageCue` lookups
- generic fallback language
- post-hoc patching through `differentiate_day_briefs()`

That made the outliner problem fundamentally architectural, not merely a coaching problem.

### 2. A fair comparison required two key changes
First, the redesigned path needed to be independent enough to compare honestly.
That was done by introducing:
- `src/autoresearch/reasoning_outliner_core.py`

Second, the evaluator needed to become more discriminating.
Initially the comparison produced only ties because the evaluator was too permissive.
It was then tightened to score:
- key-verse narrowing correctly
- textual anchoring
- generic scaffold language penalties

Once the evaluator was tightened, the redesigned outliner consistently outperformed legacy.

## Files To Read First
### Primary transfer files
- `/Volumes/claude-projects/projects/devotional-generator-system-a/docs/system/outliner-agent-redesign-spec.md`
- `/Volumes/claude-projects/projects/devotional-generator-system-a/docs/system/outliner-agent-review-handoff.md`
- `/Volumes/claude-projects/projects/devotional-generator-system-a/docs/system/outliner-execution-handoff.md`

### Core code involved in the comparison
- `/Volumes/claude-projects/projects/devotional-generator-system-a/src/generation/editorial.py`
- `/Volumes/claude-projects/projects/devotional-generator-system-a/src/generation/outliner_resources.py`
- `/Volumes/claude-projects/projects/devotional-generator-system-a/src/autoresearch/reasoning_outliner_core.py`
- `/Volumes/claude-projects/projects/devotional-generator-system-a/src/autoresearch/outliner_system_comparison.py`
- `/Volumes/claude-projects/projects/devotional-generator-system-a/scripts/autoresearch/run_outliner_system_comparison.py`
- `/Volumes/claude-projects/projects/devotional-generator-system-a/src/autoresearch/outliner_training_agent.py`

## Comparison Data Storage
A special DB table was added:
- `outliner_system_comparisons`

It stores richer comparison context than the normal experiment table, including:
- assignment payload
- interaction log
- packet snapshot
- reviewer guidance
- artifact paths
- legacy system reference
- redesigned system reference
- statuses, scores, summaries, metrics
- decision rationale
- comparison notes

This table exists specifically so a third-party review (for example Grok) does not require rediscovering the comparison context.

## Key Results
### First honest comparison state
At first the redesigned system was blocked because it still shared legacy core functions.
That blocker was removed by introducing an independent reasoning core.

### First scored comparison state
At first all scored runs tied because the evaluator was too permissive.
That was corrected by tightening the evaluator.

### Final scored batch outcome
After evaluator tightening:
- `Ruth 1` -> redesigned wins
- `Mark 2` -> redesigned wins
- `John 10` -> redesigned wins
- `Romans 5` -> redesigned wins
- `Philippians 2` -> redesigned wins

## What Changed In The Evaluator
The evaluator now penalizes:
- broad key verse references
- missing key-verse narrowing
- unanchored pastoral burdens
- unanchored theological lanes
- unanchored application lanes
- generic burden scaffold language
- generic theological-lane scaffold language
- generic application scaffold language

This was the key change that allowed the comparison to become meaningful.

## Current Recommended Next Step
Proceed with **adapter-based integration**:
1. keep the current production outliner available temporarily
2. route outlining through the redesigned reasoning outliner in adapter mode
3. compare real production-side outcomes during migration
4. cut over fully once the adapter path is stable
5. retire the legacy deterministic outliner path as the primary outline engine

## Broader Training Program Status
The system is currently in an `outliner-evaluation lock`.
That lock was the correct choice while determining the winner.

Now that a winner exists, the next AI should:
1. create the migration plan for integrating the redesigned outliner
2. implement the adapter path
3. decide when to unlock the rest of worker training
4. then continue training other workers using the new standard where appropriate

## Dashboard / Monitor Notes
Current monitor script:
- `/Volumes/claude-projects/projects/devotional-generator-system-a/scripts/autoresearch/devg-watch`

Current monitor capabilities already in place:
- worker freshness dots
- library status
- compact worker counts
- training freshness
- local-time visibility
- stale detection workflow
- menu-driven access

Dashboard updates that should now be made based on the comparison result:
1. show outliner comparison state
   - for example: `comparison_winner: redesigned`
2. show whether the system is in:
   - evaluation lock
   - migration mode
   - normal training mode
3. optionally show latest scored comparison summary
   - passage
   - winner
   - legacy score
   - redesigned score

This should help operators see that the system is no longer in pure comparison mode once adapter integration begins.

## Exact Commands
### Move into repo
```bash
cd /Volumes/claude-projects/projects/devotional-generator-system-a
```

### Run the outliner comparison on one passage
```bash
.venv/bin/python scripts/autoresearch/run_outliner_system_comparison.py --passage 'Ruth 1' --days 6 --weeks 1
```

### Query all scored comparison rows
```bash
.venv/bin/python - <<'PY'
from src.autoresearch.store import list_outliner_system_comparisons
for row in list_outliner_system_comparisons(decision_status='scored'):
    print(row.scripture_reference, row.winner, row.legacy_score, row.redesigned_score)
PY
```

### Run the targeted test slice for comparison support
```bash
.venv/bin/pytest tests/autoresearch/test_outliner_training_agent.py tests/autoresearch/test_outliner_system_comparison.py tests/test_registry.py::TestAutoresearchLedger::test_outliner_system_comparisons_survive_restart -q
```

### Run the monitor
```bash
scripts/autoresearch/devg-watch-live
```

### Run the menu
```bash
scripts/autoresearch/devg-menu
```

### Start the training loop
```bash
scripts/autoresearch/devg-start-training-loop 20
```

### Stop the training loop
```bash
scripts/autoresearch/devg-stop-training-loop
```

## Environment / Tooling
### Core runtime tools observed in use
- `sqlite3`
- `node`
- `pnpm`
- system `python3`
- project virtualenv Python: `.venv/bin/python`

### Versions observed
- `sqlite3 --version`
  - `3.51.0`
- `node --version`
  - `v25.8.1`
- `pnpm --version`
  - `10.32.1`
- system `python3 --version`
  - `Python 3.9.6`
- project venv Python
  - `Python 3.14.3`

### Homebrew packages observed
- `node 25.8.1_1`
- `pnpm 10.32.1`
- `sqlite 3.52.0`
- `tmux 3.6a`
- `watch 4.0.6`

### Monitoring / terminal tools observed
- `VibeTunnel Server v1.0.0-beta.15`
- `/Applications/VibeTunnel.app` installed

Important note:
- there is a version mismatch between Homebrew sqlite and the currently active `sqlite3` CLI version shown in PATH
- if the next environment is sandboxed or missing tools, reinstalling the above tools is the safest baseline

## One Existing Unrelated Failure
There is still an older unrelated registry backup test failure in the full registry suite.
That is not the same as the outliner comparison work and should not be confused with it.

## Final Instruction To The Next AI
Do not restart broad worker training first.

First:
- integrate the redesigned outliner through the adapter path
- update the dashboard to reflect migration state and comparison winner
- then reopen the broader training program based on the new outliner standard
