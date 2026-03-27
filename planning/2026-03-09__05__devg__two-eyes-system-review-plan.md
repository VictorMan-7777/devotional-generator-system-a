# DevG Two-Eyes System Review — Execution Plan (Session 3)

**Artifact ID**: 2026-03-09__05__devg__two-eyes-system-review-plan
**Role**: Planner (Claude)
**Date**: 2026-03-09
**Mode**: debate (planning only — no implementation)
**Branch**: feat/phase-014-rag-infrastructure
**Stop Condition**: Await human approval before Section 2 proceeds
**Supersedes**: 2026-03-09__03__devg__two-eyes-system-review-plan (Session 2)

---

## 1. Executive Summary

This is the Section 1 planning artifact from a fresh clean-room two-eyes review (Session 3)
of the complete DevG system at /Volumes/claude-projects/projects/devotional-generator-system-a.

**Session 3 mandate**: Verify whether any Session 2 findings were resolved. All artifacts
treated as non-authoritative until verified from live repository state.

**Result**: ZERO Session 2 findings have been resolved. All five open findings
(F-001 through F-003, F-005, F-006) remain open. Two new advisory findings identified.

**System status**: Feature-complete. All COMP-001–005 and AUD-001–003 items confirmed
complete. Test suite passes 822 tests with 0 failures (independently verified this session).
Three competition-blocking gaps persist from Session 2.

**Primary blockers** (unchanged from Session 2):
1. Production code not committed (F-001, SEV-1) — 37 untracked entries; fresh git checkout missing all Phase 014-015 work
2. Feature branch not merged to main (F-002, SEV-2) — 13 commits ahead of main, none merged
3. No E2E review session on competition-format outputs (F-003, SEV-2) — latest competition runs (195225, 195419) have no `__approval-decisions.json`

---

## 2. Verified System State (Session 3 Baseline)

| Metric | Verified Value | Method |
|--------|---------------|--------|
| Active branch | `feat/phase-014-rag-infrastructure` | `git status` |
| Commits ahead of main | 13 | `git log --oneline main..HEAD` |
| Untracked entries | 37 (files + dirs) | `git status --short` |
| Modified tracked files | 23 | `git status --short` |
| Test count | 822 passing, 0 failures | `.venv/bin/python3 -m pytest -q` |
| `__approval-decisions.json` on latest competition run | ABSENT | `ls outputs/devotionals/*195225*` |
| `__approval-decisions.json` on latest vol-2 run | ABSENT | `ls outputs/devotionals/*195419*` |
| `__audit-linkage.json` entry count (latest run) | 72 (list, confirmed) | `.venv/bin/python3` JSON parse |
| `approval-gate-report`: exportable | `false` | JSON read |
| `approval-gate-report`: pending_section_count | 61 | JSON read |
| `approval-gate-report`: publish_ready | `None` | JSON read |
| `approval-gate-report`: blocked_reason count | 72 sections | JSON parse + regex |
| `datetime.utcnow()` in src/ | 0 matches | `rg 'datetime\.utcnow\(\)' src/` |
| Competition backlog items completed | COMP-001–005, AUD-001–003 (all 8) | `docs/system/competition-readiness-backlog.md` |
| `.gitignore` covers runtime dirs | NO | `.gitignore` read |
| `approval-contract.md` documents count discrepancy | NO | `docs/system/approval-contract.md` read |
| Planning stub artifacts (malformed) | 2 (113 and 114 bytes) | `wc -c` |

---

## 3. Findings Summary (All Sessions)

Session 3 confirms all Session 2 findings remain open. Two new advisory findings added.

| ID | Severity | Title | Fix Cycle | Status |
|----|----------|-------|-----------|--------|
| F-001 | SEV-1 | Uncommitted production code (37 untracked paths incl. 25+ new modules) | FC-001 | **OPEN — unchanged** |
| F-002 | SEV-2 | Branch not merged to main (13 commits ahead) | FC-002 | **OPEN — unchanged** |
| F-003 | SEV-2 | No full E2E review session on competition-format outputs | FC-004 | **OPEN — unchanged** |
| F-005 | SEV-3 | `pending_section_count` (61) vs `blocked_reason` (72) discrepancy undocumented in approval-contract.md | FC-003 | **OPEN — unchanged** |
| F-006 | SEV-3 | `publish_ready = None` pre-review behavior undocumented | FC-003 | **OPEN — unchanged** |
| F-007 | SEV-4 | Runtime dirs not in .gitignore (`outputs/devotionals/`, `data/artifacts/`, `logs/`, `data/*.sqlite3`) | FC-001 | **OPEN — unchanged** |
| F-008 | SEV-4 | SQLAlchemy deprecation warnings (library-internal, not our code) | Advisory only | Advisory |
| F-009 | SEV-4 | Two malformed stub artifacts in `planning/` (113–114 bytes, not valid planning docs) | FC-001 cleanup | Advisory |
| F-010 | SEV-4 | `planning/debate_transcript_20260309_172649.json` is a runtime artifact in the planning directory | FC-001 cleanup | Advisory |

See companion findings report for full evidence: `2026-03-09__06__devg__two-eyes-system-review-findings.md`

---

## 4. E2E Validation Matrix

| Flow | Coverage Status | Test Surface | Pass Criteria | Gap |
|------|-----------------|--------------|---------------|-----|
| **Generation** | COVERED | `tests/pipeline/test_generation_day_plan.py`, `tests/integration/test_pipeline.py`, `tests/generation/` | 822 tests pass; deterministic mock generator | None |
| **Validation** | COVERED | `tests/validation/`, `tests/pipeline/test_export_gate.py`, `tests/test_schemas.py` | All validation, word-count, doctrinal, Turabian gate tests pass | None |
| **Review UI workflow** | PARTIAL | `tests/review/` (unit tests pass) | Prior runs (2026-03-07) have completed review sessions | Latest competition-vol-1 and vol-2 (2026-03-09 ≥ 19:52) have no `__approval-decisions.json` |
| **PDF render path** | COVERED | `tests/test_pdf_integration.py`; `__kdp-personal-preview.pdf` on latest runs | PDF > 0 bytes present on all 2026-03-09 runs | Publish-ready PDF path (PUBLISH_READY mode) blocked pending review completion |
| **Publish-ready gate** | COVERED (unit) | `tests/pipeline/test_export_gate.py` | ExportGate enforces unapproved + Turabian gate | No live publish-ready export on competition-format runs yet |
| **Audit/provenance** | COVERED | `__audit-linkage.json` present on latest 2 runs | 72 entries (list, not dict) confirmed via JSON parse | None |
| **Series child-volume non-dup** | COVERED | `tests/pipeline/test_run_devotional_full_helpers.py`; registry | Vol-2 auto-resolves parent context; no repeated scripture/quote | Not exercised in post-review export path |
| **Scripture correctness (agent validator)** | COVERED | `__agent-validation-report.json`; `tests/pipeline/test_full_run_assets.py` | `overall_passed: true`, 0 discrepancies on latest run | None |
| **Turabian citation gate** | COVERED (unit) | `tests/pipeline/test_export_gate.py` | Missing author/source_title/publication_year/page_or_url blocks export | Not exercised in live publish-ready export end-to-end |
| **Competition CSV loader** | COVERED | `tests/pipeline/test_full_run_assets.py::test_load_competition_outline_from_csv` | Correct column mapping | None |

**Matrix Summary**: 8/10 flows have strong coverage. 2 gaps require HC-03 (human-interactive review session).

---

## 5. Fix Cycle Plan

Deterministic execution order. Each cycle has a stop/go gate.

---

### FC-001 — Commit All Untracked Production Code

**Severity addressed**: F-001 (SEV-1), F-007 (SEV-4), F-009/F-010 (advisory cleanup)
**Prerequisite**: HC-01 (operator confirms file list, confirms runtime dirs to gitignore)

**Files to commit** (verified from git status):

*Source modules (new, untracked)*:
- `src/api/full_run_assets.py`
- `src/persistence/__init__.py`, `src/persistence/config.py`, `src/persistence/factory.py`, `src/persistence/socket.py`
- `src/persistence/adapters/__init__.py` (if present), `src/persistence/adapters/sqlite_adapter.py`
- `src/rag/sqlite_catalog.py`
- `src/scripture/planner.py`

*Scripts (untracked)*:
- `scripts/__init__.py`
- `scripts/run_devotional_full.py`
- `scripts/review/__init__.py`, `run_review.py`, `run_review_studio.py`, `run_review_web.py`, `run_review_ui.py`, `run_pending_approvals.py`
- `scripts/irb/run_tier3.py`

*Tests (untracked)*:
- `tests/pipeline/test_full_run_assets.py`, `test_generation_day_plan.py`, `test_run_devotional_full_helpers.py`
- `tests/review/` (all test files)
- `tests/persistence/` (all test files)
- `tests/scripture/test_planner.py`
- `tests/irb/` (all test files)

*IRB specs (untracked)*:
- `irb/specs/tier-3-plan.md`
- `irb/specs/tier-3-spec.yaml`

*Docs (untracked)*:
- `docs/system/approval-contract.md`
- `docs/system/competition-readiness-backlog.md`
- `docs/system/outputs/2026-03-05__09__builder__irb-tier-3-report.md`
- `docs/system/outputs/2026-03-05__09__builder__irb-tier-3-results.json`
- `docs/system/outputs/2026-03-09__01__devg__two-eyes-system-review-plan.md`
- `docs/system/outputs/2026-03-09__02__devg__two-eyes-system-review-findings.md`
- `docs/system/outputs/2026-03-09__03__devg__two-eyes-system-review-plan.md`
- `docs/system/outputs/2026-03-09__04__devg__two-eyes-system-review-findings.md`
- `docs/system/outputs/2026-03-09__05__devg__two-eyes-system-review-plan.md` (this artifact)
- `docs/system/outputs/2026-03-09__06__devg__two-eyes-system-review-findings.md`
- `planning/2026-03-09__01__devg__two-eyes-system-review-plan.md`
- `planning/2026-03-09__03__devg__two-eyes-system-review-plan.md`
- `planning/2026-03-09__04__devg__two-eyes-system-review-findings.md`
- `planning/2026-03-09__05__devg__two-eyes-system-review-plan.md` (this artifact)
- `planning/2026-03-09__06__devg__two-eyes-system-review-findings.md`

*Modified tracked files (must be staged)*:
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

*Advisory cleanup (operator decision at HC-01)*:
- Delete or gitignore `planning/2026-03-09__01__DevG-plan.md` (stub, 113 bytes)
- Delete or gitignore `planning/2026-03-09__02__DevG-plan.md` (stub, 114 bytes)
- Gitignore `planning/debate_transcript_20260309_172649.json` (runtime artifact)

**.gitignore additions required**:
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
- `git status --short` → zero `??` untracked entries except newly gitignored paths
- `.venv/bin/python3 -m pytest -q --tb=no` → 822+ passing, 0 failures
- `git log --oneline -1` → new commit with correct message

---

### FC-002 — Merge Branch to Main

**Severity addressed**: F-002 (SEV-2)
**Prerequisite**: FC-001 complete + HC-02 human checkpoint

**Action**: Merge `feat/phase-014-rag-infrastructure` to `main`.
Operator selects strategy at HC-02 (merge commit / squash / rebase).

**Stop/go gate**:
- `git checkout main && git log --oneline -1` shows merge commit
- `git status --short` on main is clean
- `.venv/bin/python3 -m pytest -q --tb=no` → 822+ passing on main

---

### FC-003 — Document Approval Count Discrepancies in approval-contract.md

**Severity addressed**: F-005, F-006 (SEV-3)
**Prerequisite**: FC-001 complete (no code change required, doc-only)
**Can run in parallel with FC-002**

**Action**: Update `docs/system/approval-contract.md` to add a section:
1. `blocked_reason` count = ALL non-approved sections (includes `agent_validated`; total = 72 in a 12-day 6-section-per-day run)
2. `pending_section_count` = human-review-required sections only (excludes `agent_validated`)
3. The 11-section gap = `agent_validated` sections: in export gate but not in UI review queue
4. `publish_ready` = `None` pre-review; populated as `true`/`false` after review session completes

**Stop/go gate**:
- `docs/system/approval-contract.md` contains clear explanation of both count fields
- No code changes required

---

### FC-004 — Full E2E Review Session on Competition Vol-1

**Severity addressed**: F-003 (SEV-2)
**Prerequisite**: FC-001 complete + HC-03 (human-interactive, cannot be automated)

**Action**:
1. Identify target slug: `2026-03-09__195225__competition-volume-1__12-day__vol-1`
2. Operator launches review:
   ```bash
   .venv/bin/python3 scripts/review/run_review.py \
     --report outputs/devotionals/2026-03-09__195225__competition-volume-1__12-day__vol-1__approval-gate-report.json \
     --backend web
   ```
   (CLI fallback: `--backend cli` if web unavailable)
3. Operator reviews all 61 pending human sections (approve/reject with notes)
4. System writes `__approval-decisions.json` on completion
5. Operator verifies ExportGate reaches `exportable=True`

**Stop/go gate**:
- `2026-03-09__195225__competition-volume-1__12-day__vol-1__approval-decisions.json` exists
- Contains decisions for 61+ sections
- All 11 agent_validated sections reach approved state
- `.venv/bin/python3 -c "import json; d=json.load(open('outputs/devotionals/...__approval-gate-report.json')); print(d.get('exportable'))"` → `True`
- Publish-ready PDF generated

**Human checkpoint**: HC-03 — Operator runs interactive review session. Agent cannot substitute.

---

### FC-005 — Final Test Devotional Gate (Section 3)

**Severity addressed**: Required gate
**Prerequisite**: FC-001, FC-002, FC-003, FC-004 complete + HC-04 sign-off

**Action**: Run one fresh competition-format devotional end-to-end:
```bash
.venv/bin/python3 scripts/run_devotional_full.py \
  --csv "<competition-outline.csv>"
```

**Required artifacts** (all must be present post-run):
1. `<slug>__book.json`
2. `<slug>__approval-gate-report.json`
3. `<slug>__agent-validation-report.json`
4. `<slug>__audit-linkage.json`
5. `<slug>__kdp-personal-preview.pdf`

**Stop/go gate**:
- All 5 artifacts present
- `__agent-validation-report.json` → `overall_passed: true`
- `__audit-linkage.json` → entries list count = days × 6 (sections per day)
- `__approval-gate-report.json` → `exportable: false`, `pending_section_count > 0` (expected pre-review)
- PDF file size > 0 bytes
- 822+ tests passing, 0 failures

---

## 6. Human Checkpoints

| ID | Timing | Required Action | Blocking? |
|----|--------|-----------------|-----------|
| HC-01 | Before FC-001 | Operator confirms commit file list (no sensitive files); selects gitignore strategy for `outputs/devotionals/`; decides fate of stub planning artifacts | Yes — FC-001 cannot start without this |
| HC-02 | After FC-001, before FC-002 | Operator selects merge strategy (merge commit / squash / rebase) and approves merge to main | Yes — FC-002 cannot start without this |
| HC-03 | After FC-001, for FC-004 | Operator runs interactive review session (61 pending sections + 11 agent-validated). Agent cannot substitute | Yes — FC-004 cannot complete without this |
| HC-04 | After FC-005 | Operator reviews Section 3 evidence and marks system competition-ready, or returns to fix cycle | Yes — final gate |

**Approving this plan means**:
1. Session 3 finding confirmations are accepted
2. Fix-cycle order is accepted (FC-001 → FC-002/003 → FC-004 → FC-005)
3. All four human checkpoints acknowledged
4. Section 2 may proceed starting with FC-001 (after HC-01 approval)

---

## 7. Risks and Escalation

| Risk | Severity | Mitigation | Escalation |
|------|----------|------------|-----------|
| Sensitive data in untracked files | High | Operator reviews at HC-01 | Rotate credentials before commit if found |
| Merge conflict on main | Medium | feat branch clean; 13 commits ahead; no known conflicts | Resolve manually; no force-push or discard |
| Review session UI failure at FC-004 | Medium | CLI fallback `--backend cli` | Debug via `logs/`; raise as implementation issue |
| ExportGate not reaching exportable=True after FC-004 | High | All 72 sections must reach approved state | Check agent_validated auto-approve logic; emit HUMAN DECISION NEEDED |
| Test regression from .gitignore changes | Low | Run suite post-commit; gitignore doesn't affect Python | Revert gitignore, investigate |
| IRB Tier 3 re-cert required after merge | Medium | Tier 3 certified at 61842ce; merge adds no new functionality code | `scripts/irb/run_tier3.py` → new dated artifact |

**Escalation triggers** (emit HUMAN DECISION NEEDED):
- Any test failure after fix cycles
- Production code missing from FC-001 file list discovered
- Unresolvable merge conflicts
- FC-004 unable to reach exportable=True

---

## 8. Session 3 Corrections vs Prior Sessions

| Item | Status |
|------|--------|
| Audit-linkage entry count: Prior explore agent reported "4 top-level dict keys" | **CORRECTED**: Structure is a list with 72 elements (confirmed via `.venv/bin/python3` JSON parse). The explore agent misread a dict-keyed structure. Actual count = 72 entries. |
| All Session 2 findings (F-001–F-008) | **CONFIRMED OPEN** — zero fixes applied between Session 2 and Session 3 |
| Test count | **CONFIRMED**: 822 passing, 0 failures (independently re-verified this session via background venv run) |
| F-005/F-006 (SEV-3): approval-contract.md count discrepancy | **CONFIRMED OPEN** — file does not document 61 vs 72 discrepancy |

---

_Produced by: Planner (Claude), 2026-03-09 — Session 3 (clean-room re-review)_
_This artifact is immutable once written._
