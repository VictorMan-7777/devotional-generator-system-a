# DevG Two-Eyes System Review Plan

Date: 2026-03-10
Scope: Section 1 planning only. No implementation performed.
Repo: `/Volumes/claude-projects/projects/devotional-generator-system-a`

## Proposal

Proceed with a deterministic three-cycle execution plan:

1. Unblock the publish-ready path first.
2. Repair the PDF reader-facing heading regression second.
3. Harden operator and CI execution so the validated path is reproducible from documented commands.

Rationale: the current system can generate review bundles, but the repo does not yet prove an end-to-end path from competition-format generation through review completion to publish-ready export. That is a harder blocker than the PDF label regression or shell-environment drift.

## Verified Repo State

- Full pipeline entrypoint exists: `scripts/run_devotional_full.py`
- Review launchers exist: `scripts/review/run_review.py`, `scripts/review/run_review_studio.py`, `scripts/review/run_review_web.py`, `scripts/review/run_review_ui.py`
- Approval gate and audit artifacts exist in current outputs
- Latest verified volume-2 run sampled: `2026-03-09__195419__genesis-1-&-2__12-day__vol-2`
- Latest sampled run contains:
  - `__book.json`
  - `__approval-gate-report.json`
  - `__agent-validation-report.json`
  - `__audit-linkage.json`
  - preview PDF
- Current sampled run remains blocked for publish-ready export:
  - approval report `pending_section_count = 61`
  - approval report `blocked_reason` reports `72 section(s) pending approval`
- Core Python subset in repo virtualenv passed:
  - `92 passed in 88.34s`
- UI PDF tests are not green:
  - `ui/pdf/__tests__/blocks.test.ts` fails on `normalizeHeadingText('timeless_wisdom')`
- Ambient-shell `pytest tests/ -q` fails collection because `scripts/run_devotional_full.py` exits at import time when `pydantic` is missing outside `.venv`

## Severity-Ranked Execution Order

1. SEV-1: Publish-ready path is functionally incomplete
2. SEV-2: PDF heading normalization regression
3. SEV-3: Documented test command is environment-fragile outside the project virtualenv

## E2E Test-And-Review Matrix

| Flow | Current status | Verified evidence | Gap to close in Section 2 | Pass criteria |
| --- | --- | --- | --- | --- |
| Generation | Covered | `scripts/run_devotional_full.py`; `.venv` pytest subset passed; sampled run artifacts exist | Re-run on fresh competition-format input after fixes | Fresh run emits `__book.json`, preview PDF, agent validation, approval gate, audit linkage |
| Validation | Covered, fail-closed | `build_agent_validation_report(...)` aborts on validator failure; sampled run `overall_status = passed` | Re-verify on fresh run after publish-ready-path changes | Any scripture mismatch still aborts run; no validator bypass |
| Review UI workflow | Partially covered | `tests/review/*` pass in `.venv`; studio retains local-time display strings | Need live review completion on a fresh run and parity across queued sections | Review session writes `__approval-decisions.json`; timestamps remain UTC in storage and local-time in studio display |
| PDF render path | Failing | `vitest` failure in `ui/pdf/__tests__/blocks.test.ts` | Fix heading normalization and rerun UI PDF suite | `vitest run` passes; internal section keys do not leak into PDF headings |
| Publish-ready gates | Unit-covered, live path blocked | `ExportGate` tests pass in `.venv`; sampled run blocked with 72 pending approvals | Need decision application plus publish-ready export execution | Reviewed devotional can transition to exportable publish-ready state without bypassing gate rules |
| Audit / provenance traceability | Covered at artifact generation, not yet re-proved after full review/export | sampled `__audit-linkage.json` has 72 entries; approval report contains section metadata | Need final E2E verification after review completion and export | Final run preserves linkage artifact and review/export artifacts remain cross-referencable |

## Fix Cycles

### Cycle 1: Publish-Ready Path

Objective: make the review-to-publish path real and deterministic.

Work:
- Resolve the mismatch between review queue construction and publish-ready exportability.
- Preserve fail-closed rules for scripture correctness and validator independence.
- Add or wire the missing operator path that applies approval decisions to the book and produces a publish-ready export artifact.
- Add targeted tests for:
  - queued section selection vs export gate parity
  - decision application to book state
  - publish-ready export after complete approvals

Pass criteria:
- No section excluded from the review queue can still silently block publish-ready export.
- Fresh reviewed run can produce a publish-ready export artifact after valid approvals.
- Volume 2 series constraints still fail closed on duplicates.

### Cycle 2: PDF Reader-Facing Output

Objective: restore reader-facing headings in PDF output.

Work:
- Fix heading normalization in `ui/pdf/blocks.ts`
- Rerun `vitest`
- Rerun Python PDF integration coverage touching export path

Pass criteria:
- `vitest run` passes
- Reader-facing headings map correctly for section keys such as `timeless_wisdom`, `action_steps`, `be_still`

### Cycle 3: Execution Discipline Hardening

Objective: make the documented validation workflow reproducible by operators and CI.

Work:
- Remove or isolate import-time dependency exits that break test collection under the documented command path, or update the documented command path to be explicit and enforceable
- Verify README/start commands against actual runtime behavior

Pass criteria:
- Documented test command works as written, or docs are corrected to the exact required command and verified
- No import-time `SystemExit` prevents normal test collection in the supported environment

## Human Checkpoints

1. Required before Section 2 begins:
   - Human approval of this plan and the paired findings artifact
2. Required after Cycle 1:
   - Human re-review approval of the chosen publish-ready semantics before proceeding to broad E2E reruns
3. Required after first full reviewed devotional run:
   - Human confirms review output, blocker accuracy, and operator UX are acceptable before final competition-ready certification

## Section 2 Re-Review Protocol

- After each cycle:
  - run targeted tests for changed surfaces
  - run one relevant E2E scenario
  - perform two-eyes re-review on affected artifacts
- If any scripture discrepancy appears:
  - fail closed
  - stop the cycle
  - return with evidence

## Stop State For Section 1

Section 1 is complete when:

- this plan artifact exists
- the paired findings artifact exists
- both are saved under `planning/` and `docs/system/outputs/`
- no implementation changes have been made
- human approval is awaited before Section 2

