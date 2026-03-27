# DevG Two-Eyes System Review Findings

Date: 2026-03-10
Scope: clean-room Section 1 findings from current repo state and observed test/artifact evidence
Repo: `/Volumes/claude-projects/projects/devotional-generator-system-a`

## Executive Finding

DevG is not yet competition-ready for execution because the current repo does not prove a complete review-to-publish path on competition-format outputs. The primary blocker is not generation quality; it is state-transition completeness between review artifacts and publish-ready export.

## Severity-Ranked Findings

### SEV-1: Publish-ready path is blocked by queue/export mismatch and missing finalization path

Status: Open

Verified evidence:

- `src/api/full_run_assets.py` builds review queues with `include_agent_validated=False` by default
- same file excludes `verification_status == "agent_validated"` sections from `pending_sections`
- `src/api/export_gate.py` still requires `approval_status == APPROVED` for all present sections
- sampled latest run `2026-03-09__195419__genesis-1-&-2__12-day__vol-2` shows:
  - `pending_section_count = 61`
  - `blocked_reason` begins with `72 section(s) pending approval`
- sampled `__book.json` contains `11` sections with:
  - `approval_status = pending`
  - `verification_status = agent_validated`
- repo search found no script that applies `__approval-decisions.json` back into the book and exports a publish-ready PDF

Why this matters:

- Operators can finish the visible review queue and still remain blocked from publish-ready export.
- The repo currently proves generation and review bundle creation, but not the state transition from reviewed content to publish-ready output.
- Section 3 cannot be certified until this path exists and is exercised.

Required fix direction:

- Align review queue semantics with export gate semantics, or add an explicit, tested state promotion path for agent-validated sections that still preserves fail-closed behavior.
- Add a deterministic decision-application and publish-ready export command path.

### SEV-2: PDF heading normalization regression leaks internal section keys

Status: Open

Verified evidence:

- `ui/pdf/__tests__/blocks.test.ts` fails:
  - expected `Timeless Wisdom`
  - received `timeless_wisdom`
- `ui/pdf/blocks.ts` uses `trimmed.toLowerCase().replace(/[\\s-]+/g, '_')`, which does not normalize underscores the way the test expects

Why this matters:

- Reader-facing PDF output can expose implementation identifiers instead of devotional labels.
- This directly affects the preview/export presentation surface.

Required fix direction:

- Correct heading normalization and rerun `vitest run`.

### SEV-3: Documented test execution is shell-environment fragile

Status: Open

Verified evidence:

- README instructs `pytest tests/`
- ambient-shell `pytest tests/ -q` fails collection with:
  - `ModuleNotFoundError: No module named 'pydantic'`
  - followed by import-time `SystemExit` from `scripts/run_devotional_full.py`
- repo virtualenv succeeds on the relevant subset:
  - `92 passed in 88.34s`

Why this matters:

- Operators or CI using the documented command from the wrong interpreter get a misleading repository failure before test collection completes.
- This is lower severity than the publish-ready path blocker, but it weakens reproducibility.

Required fix direction:

- Make the supported command explicit and verified, and/or remove import-time termination behavior from test-collectable modules.

## What Is Working

- Competition-outline CSV loading exists and is tested
- Full-run artifact bundle generation exists
- Independent validator artifact generation exists and sampled runs pass
- Child-volume scripture/quote exclusion enforcement exists in the full-run path
- Audit linkage artifact generation exists and sampled latest volume-2 run contains `72` linkage entries
- Review backends exist across UI, web, CLI, and studio
- Core review, export-gate, pipeline, and IRB test subset passed in `.venv`

## Unproven Or Incomplete Areas

- No verified live path from completed review decisions to publish-ready export artifact
- No post-review E2E evidence yet for competition-format run artifacts
- Latest competition-format sampled runs still lack `__approval-decisions.json`
- Final Section 3 fresh-run gate has not been exercised on a post-fix reviewed devotional

## Evidence Snapshot

### Commands and observed outcomes

- `pytest tests/ -q`
  - failed in ambient shell during collection because `pydantic` was unavailable and `scripts/run_devotional_full.py` exits at import time
- `.venv/bin/pytest tests/review tests/pipeline/test_full_run_assets.py tests/pipeline/test_export_gate.py tests/integration/test_pipeline.py tests/irb/test_tier3_runner.py -q`
  - passed: `92 passed in 88.34s`
- `cd ui && node_modules/.bin/vitest run`
  - failed in `pdf/__tests__/blocks.test.ts`

### Sampled artifact facts

- Run slug: `2026-03-09__195419__genesis-1-&-2__12-day__vol-2`
- Present:
  - `__book.json`
  - `__approval-gate-report.json`
  - `__agent-validation-report.json`
  - `__audit-linkage.json`
  - preview PDF
- Missing for sampled latest run:
  - `__approval-decisions.json`
- Approval report:
  - `pending_section_count = 61`
  - `section_meta_by_key = 72 entries`
  - `section_previews_by_key = 61 entries`
- Agent validation report:
  - `overall_status = passed`
  - `discrepancies = 0`

## Recommended Section 2 Order

1. Fix SEV-1 publish-ready path completeness
2. Fix SEV-2 PDF heading regression
3. Fix SEV-3 execution-discipline hardening
4. Run fresh E2E devotional, live review completion, and publish-ready verification

## Required Human Re-Review Points

1. Approve Section 1 artifacts before any implementation
2. Approve the Cycle 1 publish-ready semantics after code changes but before final certification reruns
3. Approve the first complete post-fix review/export evidence set before competition submission use

