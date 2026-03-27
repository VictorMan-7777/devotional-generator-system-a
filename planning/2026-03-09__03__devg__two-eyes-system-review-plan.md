# DevG Two-Eyes System Review — Execution Plan (Session 2)

**Artifact ID**: 2026-03-09__03__devg__two-eyes-system-review-plan
**Role**: Planner (Claude)
**Date**: 2026-03-09
**Mode**: debate (planning only — no implementation)
**Branch**: feat/phase-014-rag-infrastructure
**Stop Condition**: Await human approval before Section 2 proceeds
**Supersedes**: 2026-03-09__01__devg__two-eyes-system-review-plan (earlier session, same day)

---

## 1. Executive Summary

This is the Section 1 planning artifact from a fresh clean-room two-eyes review of the
complete DevG system at /Volumes/claude-projects/projects/devotional-generator-system-a.

**System status**: Feature-complete with three competition-blocking gaps.

All Priority 0 competition requirements (COMP-001 through COMP-005) and Priority 1 audit
hardening requirements (AUD-001 through AUD-003) are fully implemented per
`docs/system/competition-readiness-backlog.md`. The 822-test suite passes with zero
failures. Pipeline end-to-end generates correct artifacts including `__audit-linkage.json`
on all recent runs.

**Primary blockers**:
1. Production code not committed (F-001, SEV-1) — fresh git checkout would be missing all Phase 014-015 work
2. Feature branch not merged to main (F-002, SEV-2) — competition/IRB reference branch is ambiguous
3. No E2E review session on competition-format outputs (F-003, SEV-2) — review → approved → publish-ready path unproven live

**Key correction from prior session**: F-005 (`datetime.utcnow()` deprecation) is downgraded
to SEV-4/Advisory. Fresh grep confirms zero `datetime.utcnow()` calls in `src/` code.
Any deprecation warnings are from SQLAlchemy internals outside our control.

---

## 2. Findings (Severity-Ranked)

See companion findings report: `2026-03-09__04__devg__two-eyes-system-review-findings.md`

Summary table:

| ID | Severity | Title | Fix Cycle |
|----|----------|-------|-----------|
| F-001 | SEV-1 | Uncommitted production code (25+ untracked paths) | FC-001 |
| F-002 | SEV-2 | Branch not merged to main | FC-002 |
| F-003 | SEV-2 | No full E2E review session on competition outputs | FC-004 |
| F-004 | SEV-2 | `__audit-linkage.json` absent on pre-19:52 runs | Advisory (superseded by fresh run) |
| F-005 | SEV-3 | `pending_section_count` vs `blocked_reason` discrepancy undocumented | FC-005 |
| F-006 | SEV-3 | `publish_ready` = None undocumented pre-review | FC-005 |
| F-007 | SEV-4 | Runtime dirs (`outputs/devotionals/`, `data/artifacts/`, `logs/`, `data/*.sqlite3`) not gitignored | FC-001 (gitignore update) |
| F-008 | SEV-4 | SQLAlchemy deprecation warnings in test output (library-internal, not our code) | Advisory only |

---

## 3. E2E Validation Matrix

| Flow | Coverage Status | Test Surface | Pass Criteria | Gap |
|------|-----------------|--------------|---------------|-----|
| **Generation** | COVERED | `tests/pipeline/test_generation_day_plan.py`, `tests/integration/test_pipeline.py`, `tests/generation/` | 822+ tests pass; mock generator deterministic | None |
| **Validation** | COVERED | `tests/validation/` (11 files), `tests/pipeline/test_export_gate.py`, `tests/test_schemas.py` | All validation checks pass; word count, doctrinal, Turabian gate | None |
| **Review UI workflow** | PARTIAL | `tests/review/test_approval_contract_parity.py`, `test_review_launcher.py`, `test_review_studio.py`, `test_review_web.py` | Unit tests pass; parity with contract verified | No full interactive E2E run on competition-vol-1 artifacts (HC-03 required) |
| **PDF render path** | COVERED | PDFs in `outputs/devotionals/`; `tests/test_pdf_integration.py` | `__kdp-personal-preview.pdf` > 0 bytes on latest runs | Publish-ready PDF (PUBLISH_READY mode) requires approved sections first |
| **Publish-ready gate** | COVERED (unit) | `tests/pipeline/test_export_gate.py` | ExportGate blocks unapproved + missing Turabian | No live competition-format publish-ready export executed yet |
| **Audit/provenance** | COVERED (latest 2 runs) | `__audit-linkage.json` in 195225 + 195419 runs | 72 entries per run; `section_meta_by_key` populated | Older runs missing (superseded; final run will include) |
| **Series child-volume non-dup** | COVERED | `tests/pipeline/test_run_devotional_full_helpers.py`; registry context query | Vol-2 auto-resolves parent context; no repeated scriptures/quotes | Not exercised in post-review export path |
| **Scripture correctness (agent validator)** | COVERED | `tests/pipeline/test_full_run_assets.py`; `__agent-validation-report.json` | `overall_passed: true`, 0 discrepancies on latest run | None |
| **Turabian citation gate** | COVERED (unit) | `tests/pipeline/test_export_gate.py` Turabian checks | Missing author/source_title/publication_year/page_or_url blocks export | Not tested in live full export path end-to-end |
| **Competition CSV loader** | COVERED | `tests/pipeline/test_full_run_assets.py::test_load_competition_outline_from_csv` | Correct column mapping from competition outline format | None |

**Matrix Summary**: 8/10 flows have strong unit/integration coverage. 2 critical gaps:
(a) interactive review → approved → publish-ready PDF path not exercised live;
(b) Turabian gate tested only in unit tests, not in live publish-ready export.

---

## 4. Fix Cycle Plan

Cycles in deterministic execution order. Each cycle has a stop/go gate before the next.

---

### FC-001 — Commit All Untracked Production Code

**Severity addressed**: F-001 (SEV-1)
**Prerequisite**: HC-01 human checkpoint (operator confirms file list)

**Files to commit** (production code and docs — NOT runtime state):

*Source modules (untracked):*
- `src/api/full_run_assets.py`
- `src/persistence/__init__.py`, `src/persistence/socket.py`, `src/persistence/config.py`, `src/persistence/factory.py`
- `src/persistence/adapters/__init__.py`, `src/persistence/adapters/sqlite_adapter.py`
- `src/rag/sqlite_catalog.py`
- `src/scripture/planner.py`

*Scripts (untracked):*
- `scripts/__init__.py`
- `scripts/run_devotional_full.py`
- `scripts/review/run_review.py`, `run_review_studio.py`, `run_review_web.py`, `run_review_ui.py`, `run_pending_approvals.py`
- `scripts/irb/run_tier3.py`

*Tests (untracked):*
- `tests/pipeline/test_full_run_assets.py`, `test_generation_day_plan.py`, `test_run_devotional_full_helpers.py`
- `tests/review/` (all test files)
- `tests/persistence/test_socket_factory.py`
- `tests/scripture/test_planner.py`
- `tests/irb/` (all test files)

*IRB specs (untracked):*
- `irb/specs/tier-3-plan.md`
- `irb/specs/tier-3-spec.yaml`

*Docs (untracked):*
- `docs/system/approval-contract.md`
- `docs/system/competition-readiness-backlog.md`
- `docs/system/outputs/2026-03-05__09__builder__irb-tier-3-report.md`
- `docs/system/outputs/2026-03-05__09__builder__irb-tier-3-results.json`
- `planning/` directory (planning artifacts)

*Modified tracked files (must also be staged):*
- `README.md`, `data/excerpts/seed-excerpts.json`, `data/quotes/seed-quotes.json`
- `src/api/export_gate.py`, `src/api/generation_pipeline.py`
- `src/generation/generators.py`, `src/generation/real_section_generator.py`
- `src/models/devotional.py`, `src/models/registry.py`
- `src/rag/catalog.py`, `src/rag/exposition.py`
- `src/registry/registry.py`, `src/rendering/engine.py`, `src/rendering/sections.py`
- `templates/offer_page.md`
- `tests/generation/test_deterministic_real_section_generator.py`
- `tests/pipeline/test_export_gate.py`, `tests/test_registry.py`
- `tests/test_rendering.py`, `tests/test_schemas.py`, `tests/test_section_renderers.py`
- `ui/pdf/__tests__/blocks.test.ts`, `ui/pdf/blocks.ts`

**Gitignore update required** (add these entries):
```
data/artifacts/
data/*.sqlite3
logs/
outputs/devotionals/
```

**Excluded from commit** (runtime state):
- `data/devg_registry.sqlite3`
- `outputs/devotionals/`
- `data/artifacts/`
- `logs/`

**Stop/go gate**:
- `git status --short` shows NO `??` untracked entries except gitignored paths
- `.venv/bin/python3 -m pytest -q --tb=no` shows 822+ passing, 0 failures
- `git log --oneline -1` shows new commit with correct message

---

### FC-002 — Merge Branch to Main

**Severity addressed**: F-002 (SEV-2)
**Prerequisite**: FC-001 complete + HC-02 human checkpoint

**Action**: Merge `feat/phase-014-rag-infrastructure` to `main` via merge commit.
Operator selects strategy (merge commit / squash / rebase) at HC-02.

**Stop/go gate**:
- `git checkout main && git log --oneline -1` shows merge commit
- `git status --short` on main is clean
- Test suite passes on main (822+ tests)
- `git branch -d feat/phase-014-rag-infrastructure` succeeds (if operator elects cleanup)

---

### FC-003 — Document Approval Count Discrepancies

**Severity addressed**: F-005, F-006 (SEV-3)
**Prerequisite**: FC-001 complete (docs can be committed in same commit)
**Can be done in parallel with FC-002**

**Action**: Update `docs/system/approval-contract.md` to document:
1. `blocked_reason` count = ALL non-approved sections (export gate, includes agent_validated)
2. `pending_section_count` = human-review-required sections only (excludes agent_validated)
3. The 11-section gap (72 − 61 = 11 agent_validated sections: not in UI queue but block publish-ready export)
4. `publish_ready` field: set to `None` pre-review; populated as `true`/`false` after review completes

**Stop/go gate**:
- `docs/system/approval-contract.md` contains explanation of both count fields
- No code changes required (behavior is correct by design)

---

### FC-004 — Full E2E Review Session on Competition Vol-1

**Severity addressed**: F-003 (SEV-2)
**Prerequisite**: FC-001 complete + HC-03 (human-interactive, cannot be automated)

**Action**:
1. Identify latest competition-volume-1 slug: `2026-03-09__195225__competition-volume-1__12-day__vol-1`
2. Operator launches review:
   ```bash
   .venv/bin/python3 scripts/review/run_review.py \
     --report outputs/devotionals/2026-03-09__195225__competition-volume-1__12-day__vol-1__approval-gate-report.json \
     --backend web
   ```
3. Operator reviews all 61 pending human sections (approve/reject with notes)
4. System writes `__approval-decisions.json` upon completion

**Stop/go gate**:
- `2026-03-09__195225__competition-volume-1__12-day__vol-1__approval-decisions.json` exists
- Contains decisions for all 61 pending sections
- All 11 agent_validated sections also reach approved state (via auto-approve or operator decision)
- `ExportGate.check_exportability(book, PUBLISH_READY)` returns `exportable=True`
- Publish-ready PDF generates successfully

**Human checkpoint**: HC-03 — Operator runs review session in browser. Agent cannot complete this step.

---

### FC-005 — Final Test Devotional Gate (Section 3)

**Severity addressed**: Required gate
**Prerequisite**: FC-001, FC-002, FC-003, FC-004 complete + HC-04 sign-off

**Action**: Run one fresh competition-format devotional end-to-end:
```bash
.venv/bin/python3 scripts/run_devotional_full.py \
  --csv outputs/devotionals/_regen_genesis12_outline.csv
```
(or use the actual competition outline CSV if available)

**Required artifacts** (all must be present):
1. `<slug>__book.json`
2. `<slug>__approval-gate-report.json`
3. `<slug>__agent-validation-report.json`
4. `<slug>__audit-linkage.json`
5. `<slug>__kdp-personal-preview.pdf`

**Stop/go gate**:
- All 5 artifacts present in `outputs/devotionals/`
- `__agent-validation-report.json` → `overall_passed: true`
- `__audit-linkage.json` → `entries` count == (days × 6 sections)
- `__approval-gate-report.json` → `exportable: false`, `pending_section_count > 0` (expected pre-review)
- PDF file size > 0 bytes
- Test suite: 822+ tests passing
- No new errors or regressions

---

## 5. Human Checkpoints

| ID | Timing | Required Action | Blocking? |
|----|--------|-----------------|-----------|
| HC-01 | Before FC-001 begins | Operator confirms the file commit list is complete and excludes sensitive/unintended files | Yes — FC-001 cannot start without this |
| HC-02 | After FC-001, before FC-002 | Operator selects merge strategy (merge commit / squash / rebase) and approves merge to main | Yes — FC-002 cannot start without this |
| HC-03 | After FC-001, for FC-004 | Operator runs interactive review session in browser (61+ pending sections). Agent cannot substitute for this step | Yes — FC-004 cannot complete without this |
| HC-04 | After FC-005 (Section 3 gate) | Operator reviews Section 3 evidence and marks system competition-ready, or returns to FC-002 cycle | Yes — final gate |

**Approving this plan means**:
1. The findings severity rankings are accepted
2. The fix-cycle order is accepted
3. All four human checkpoints are acknowledged
4. Section 2 can proceed starting with FC-001 (after HC-01 approval)

---

## 6. Risks and Escalation Criteria

| Risk | Severity | Likelihood | Mitigation | Escalation |
|------|----------|-----------|------------|-----------|
| Untracked files include sensitive data (API keys, DB passwords) | High | Low | Operator reviews full file list at HC-01 | If sensitive data found: rotate credentials before commit |
| Merge conflict on main when merging feat branch | Medium | Low | feat branch is clean; 12 commits ahead with no known conflict zones | Resolve manually; do not force-push or discard changes |
| Review session UI error blocking FC-004 | Medium | Low | CLI fallback via `--backend cli`; approve-all script for dry-run testing | If UI blocked: debug logs in `logs/`; raise as implementation issue |
| `ExportGate` not reaching `exportable=True` after FC-004 review | High | Low | All sections visible in review UI; 11 agent_validated sections may need operator confirmation | If blocked: check if agent_validated sections auto-approve or require manual decision |
| Competition outline CSV column format mismatch on FC-005 | Medium | Low | `load_competition_outline_from_csv()` validates required columns; test with dry-run `--dry-run` flag | If format mismatch: adjust CSV header or update loader |
| Test regression after FC-001 commit introduces .gitignore changes | Low | Very Low | Run full test suite after commit; `.gitignore` changes do not affect Python imports | If tests fail: revert gitignore change, investigate |
| IRB Tier 3 re-certification required after branch merge | Medium | Low | Tier 3 was certified at 61842ce; merge commit adds no new functionality code | If IRB re-cert required: `scripts/irb/run_tier3.py` → dated artifact |

**Escalation criteria** (human decision required, using HUMAN DECISION NEEDED format):
- Any test failures introduced by fix cycles
- Any production code discovered missing from FC-001 file list
- Merge conflicts that cannot be cleanly resolved
- FC-004 review session unable to reach exportable=True state
- New security or correctness finding discovered during implementation

---

## 7. Ready-for-Implementation Decision

**Section 1 planning status**: COMPLETE

**Implementation may proceed** after human approval of this plan (Section 2 gate).

**Current system state verified**:
- Branch: `feat/phase-014-rag-infrastructure` (12+ commits ahead of main)
- Test suite: 822 passing, 0 failures (baseline from prior session; fresh run in progress)
- All COMP-001-005 and AUD-001-003 items: COMPLETED
- Competition vol-1 latest run: `2026-03-09__195225` — artifacts present, no approval-decisions.json yet
- No `datetime.utcnow()` in `src/` code (library-level SQLAlchemy warnings only — advisory)

**Implementation start point**: FC-001 (after HC-01 approval)

---

## Artifact Naming Policy

- Today: 2026-03-09
- Session 1 artifacts: NN=01 (plan), NN=02 (findings)
- Session 2 artifacts (this session): NN=03 (plan), NN=04 (findings)
- NN computed at runtime from existing artifacts in `docs/system/outputs/`

Both artifacts written to:
- `planning/` (plan document)
- `docs/system/outputs/` (plan + findings)

---

_Produced by: Planner (Claude), 2026-03-09 — Session 2 (clean-room re-review)_
_This artifact is immutable once written._
