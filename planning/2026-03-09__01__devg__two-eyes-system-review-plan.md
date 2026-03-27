# DevG Two-Eyes System Review — Execution Plan

**Artifact ID**: 2026-03-09__01__devg__two-eyes-system-review-plan
**Role**: Planner (Claude)
**Date**: 2026-03-09
**Mode**: debate (planning only — no implementation)
**Branch**: feat/phase-014-rag-infrastructure
**Stop Condition**: Await human approval before Section 2 proceeds

---

## Purpose

This document is the Section 1 planning artifact for the DevG two-eyes system review.
It defines the execution plan for fix cycles, E2E test matrix, and human checkpoints.

A companion findings report (`2026-03-09__02__devg__two-eyes-system-review-findings.md`)
contains the severity-ranked issue list discovered during the clean-room review.

---

## Scope

**Target repo**: /Volumes/claude-projects/projects/devotional-generator-system-a
**Review basis**: Live repository state as of 2026-03-09 (not prior context)
**IRB baseline**: Tiers 1, 1.5, 2, 3 CERTIFIED at SHA 61842ce (2026-03-05)
**Test count at review**: 822 passing (0 failures, 0 errors)
**Last run slug**: 2026-03-09__195419__genesis-1-&-2__12-day__vol-2

---

## E2E Test-and-Review Matrix

| Flow | Coverage Status | Test Surface | Gap? |
|------|-----------------|--------------|------|
| **Generation** | COVERED | `tests/pipeline/test_generators.py`, smoke fixture, `test_generation_day_plan.py` | None |
| **Validation** | COVERED | `tests/validation/`, `tests/pipeline/test_export_gate.py`, `tests/test_schemas.py` | None |
| **Review UI workflow** | PARTIAL | `tests/review/test_approval_contract_parity.py`, `test_review_launcher.py`, `test_review_studio.py`, `test_review_web.py` | No full E2E run on competition-vol-1 artifacts |
| **PDF render path** | COVERED | Personal preview PDFs exist in outputs/; `tests/test_pdf_integration.py` | publish-ready PDF requires approved sections |
| **Publish-ready gate** | COVERED (unit) | `tests/pipeline/test_export_gate.py`, Turabian gate tested | No full E2E: no competition run has reached approved → exported state |
| **Audit/provenance traceability** | COVERED (latest) | `__audit-linkage.json` present on 2 latest runs; `section_meta_by_key` wired into approval report | Earlier runs missing audit artifact; full publish-ready path not exercised |
| **Series child-volume non-dup** | COVERED | `tests/pipeline/test_run_devotional_full_helpers.py`, registry context query | Tested but no post-review export of vol-2 |
| **Scripture correctness (agent validator)** | COVERED | `tests/pipeline/test_full_run_assets.py`, agent validation reports pass | Validator shows text_match: True, no discrepancies |
| **Turabian citation gate** | COVERED | `tests/pipeline/test_export_gate.py` Turabian checks | Not tested in live export path end-to-end |

**Matrix Summary**: 7/9 flows are unit/integration covered. 2 critical gaps: (a) no competition-format run has gone through the full review → approved → publish-ready PDF path; (b) audit-linkage traceability exists in generation artifacts but not exercised in publish-ready export.

---

## Fix-Cycle Execution Plan

Cycles are listed in deterministic execution order. No cycle may begin until prior
cycle's pass criteria are verified.

---

### FC-001 — Commit All Untracked Production Code

**Severity**: SEV-1 (Competition-Blocking)
**Prerequisite**: HC-01 human checkpoint (see below)
**Target files**:
- `scripts/run_devotional_full.py`
- `src/api/full_run_assets.py`
- `src/persistence/` (entire module)
- `src/rag/sqlite_catalog.py`
- `src/scripture/planner.py`
- `scripts/__init__.py`, `scripts/review/`, `scripts/irb/`
- `tests/pipeline/test_full_run_assets.py`, `test_generation_day_plan.py`, `test_run_devotional_full_helpers.py`
- `tests/review/`, `tests/persistence/`, `tests/scripture/`, `tests/irb/`
- `irb/specs/tier-3-plan.md`, `irb/specs/tier-3-spec.yaml`
- `docs/system/approval-contract.md`, `docs/system/competition-readiness-backlog.md`
- `docs/system/outputs/2026-03-05__09__builder__irb-tier-3-report.md`, `...__irb-tier-3-results.json`

**Excluded from commit** (gitignore / runtime state):
- `data/devg_registry.sqlite3` (runtime database)
- `outputs/devotionals/` (runtime pipeline outputs)
- `data/artifacts/` (runtime artifacts)
- `logs/` (runtime logs)

**Pass criteria**:
- `git status --short` shows NO untracked `??` entries except gitignored paths
- `git log --oneline -1` shows new commit with all production files
- `.venv/bin/python3 -m pytest -q --tb=no` still shows 822+ tests passing

**Human checkpoint**: HC-01 — Before executing FC-001, operator confirms the list of files above is complete and no sensitive/unintended files are included.

---

### FC-002 — Merge Branch to Main

**Severity**: SEV-2 (High)
**Prerequisite**: FC-001 complete + HC-02 human checkpoint
**Action**: Merge `feat/phase-014-rag-infrastructure` into `main` via clean merge commit.

**Pass criteria**:
- `git log main --oneline -1` shows the merge commit
- `git status --short` on main is clean
- Test suite passes on main

**Human checkpoint**: HC-02 — Operator approves merge strategy (merge commit vs squash vs rebase).

---

### FC-003 — Resolve `datetime.utcnow()` Deprecation Warnings

**Severity**: SEV-3 (Medium)
**Prerequisite**: FC-001 complete
**Scope**: Replace `datetime.utcnow()` calls in:
- `src/registry/registry.py`
- Any other `src/` files using `datetime.utcnow()`

**Replacement pattern**: `datetime.now(timezone.utc)` (already used correctly in some files)
**SQLAlchemy warnings**: tracked separately; do not touch ORM internals.

**Pass criteria**:
- `pytest -q --tb=no -W error::DeprecationWarning` passes (or at minimum: zero datetime.utcnow warnings in src/ files)
- Test count unchanged

---

### FC-004 — Full E2E Review Session on Competition Vol-1

**Severity**: SEV-2 (High)
**Prerequisite**: FC-001 complete + HC-03 human checkpoint
**Action**:
1. Identify latest competition-volume-1 run slug
2. Launch review UI: `scripts/review/run_review.py --report outputs/devotionals/<slug>__approval-gate-report.json --backend web`
3. Operator reviews all 61 pending human sections
4. System writes `__approval-decisions.json`

**Pass criteria**:
- `<slug>__approval-decisions.json` exists with decisions for all pending sections
- `ExportGate.check_exportability(book, PUBLISH_READY)` returns `exportable=True`
- `publish_ready` gate passes (all required sections approved, Turabian complete)

**Human checkpoint**: HC-03 — Operator runs review session in browser, approves/rejects sections. This is a human-interactive step; agent cannot complete it.

---

### FC-005 — Document `pending_section_count` / blocked_reason Discrepancy

**Severity**: SEV-3 (Medium)
**Prerequisite**: None (can be done in parallel with FC-001)
**Action**: Update `docs/system/approval-contract.md` to document that:
- `blocked_reason` uses total not-approved sections (export gate count)
- `pending_section_count` uses human-review-required sections (excludes agent_validated)
- `publish_ready` field is `None` pre-review, populated post-review

**Pass criteria**:
- Approval contract explains the count difference
- No code change required (behavior is correct by design)

---

### FC-006 — Final Test Devotional Gate (Section 3)

**Severity**: Required gate
**Prerequisite**: FC-001, FC-003, FC-004 complete
**Action**: Run one fresh test devotional end-to-end:
```bash
.venv/bin/python3 scripts/run_devotional_full.py --csv <competition-outline.csv>
```

**Required artifacts (all must be present)**:
1. `<slug>__book.json`
2. `<slug>__approval-gate-report.json`
3. `<slug>__agent-validation-report.json`
4. `<slug>__audit-linkage.json`
5. `<slug>__kdp-personal-preview.pdf`

**Pass criteria**:
- All 5 artifacts present in `outputs/devotionals/`
- `__agent-validation-report.json` → `overall_passed: true`
- `__audit-linkage.json` → `entries` count == (days × 6 sections)
- `__approval-gate-report.json` → `exportable: false`, `pending_section_count > 0` (pre-review, expected)
- PDF renders without error and file size > 0 bytes
- Test suite: 822+ tests passing

**Human checkpoint**: HC-04 — Final operator sign-off. Operator reviews Section 3 gate evidence and marks system as competition-ready or returns to FC-002 cycle.

---

## Human Checkpoints Summary

| ID | When | Action Required | Blocking? |
|----|------|-----------------|-----------|
| HC-01 | Before FC-001 | Confirm file commit list | Yes |
| HC-02 | After FC-001, before FC-002 | Approve merge strategy | Yes |
| HC-03 | After FC-001, for FC-004 | Operator runs review session (interactive) | Yes |
| HC-04 | After FC-006 | Final competition-ready sign-off | Yes |

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Untracked files include sensitive data | Medium | Operator reviews commit list at HC-01 |
| Merge conflict on main | Low | feat branch is clean; main has diverged minimally |
| Review session stalls (UI issue) | Medium | CLI fallback via `--backend cli`; web fallback via `--backend web` |
| datetime.utcnow() fix breaks registry tests | Low | Run targeted registry test subset before full suite |
| Competition outline CSV format mismatch | Medium | load_competition_outline_from_csv() validates required columns; test with dry run before final gate |

---

## Open Questions for Human Decision

1. **Commit scope**: Should `data/artifacts/` directory be gitignored or tracked?
2. **Merge strategy**: Merge commit, squash, or rebase to main?
3. **Review backend**: UI (default) vs web for FC-004 review session?
4. **Competition outline**: Is the `Series 1 - Volume 1 - 30-Day Outline.csv` available for FC-006 final gate?

---

## Artifact Naming Policy Verification

- Today: 2026-03-09
- Prior docs/system/outputs/ for today: none
- NN=01 → this plan document
- NN=02 → findings report

Both artifacts written to:
- `planning/` (plan only)
- `docs/system/outputs/` (plan + findings)

---

## Section 1 Stop Condition

This planning document is **COMPLETE**. The findings report will be written next.
**Implementation (Section 2) must NOT begin until human approval is received.**

Approving this plan means:
1. The findings severity rankings are accepted
2. The fix-cycle order is accepted
3. The human checkpoints are acknowledged
4. Section 2 can proceed starting with FC-001

---

_Produced by: Planner (Claude), 2026-03-09_
_This artifact is immutable once written._
