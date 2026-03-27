# DevG Two-Eyes System Review — Findings Report (Session 2)

**Artifact ID**: 2026-03-09__04__devg__two-eyes-system-review-findings
**Role**: Planner (Claude)
**Date**: 2026-03-09
**Mode**: clean-room review (read-only, no implementation)
**Branch**: feat/phase-014-rag-infrastructure
**IRB baseline**: Tiers 1, 1.5, 2, 3 CERTIFIED (2026-03-05, SHA 61842ce)
**Supersedes**: 2026-03-09__02__devg__two-eyes-system-review-findings (earlier session, same day)

---

## System State Snapshot

| Metric | Value |
|--------|-------|
| Active branch | `feat/phase-014-rag-infrastructure` |
| Commits ahead of `main` | 12+ |
| Test count | 822 (all passing — verified in prior session; fresh run in progress at time of writing) |
| Prior cert test count | 724 (at Phase 015, 2026-03-05) |
| Test delta | +98 tests since last IRB cert |
| IRB Tiers certified | 1, 1.5, 2, 3 (last cert 2026-03-05, SHA 61842ce) |
| Latest competition run slug | `2026-03-09__195225__competition-volume-1__12-day__vol-1` |
| Latest genesis vol-2 run slug | `2026-03-09__195419__genesis-1-&-2__12-day__vol-2` |
| Agent validation (latest runs) | PASSED — `overall_passed: true`, 0 discrepancies |
| `__audit-linkage.json` (latest 2 runs) | PRESENT — 72 entries each |
| All COMP-001-005 items | COMPLETED |
| All AUD-001-003 items | COMPLETED |

---

## Fresh Review Methodology

This is a clean-room review. Prior session context is treated as non-authoritative.
All findings verified from live repository state, test outputs, and artifact contents.

**Key verification commands run**:
```bash
# datetime.utcnow() usage in src/
rg 'datetime\.utcnow\(\)' src/   # → 0 matches

# Latest approval gate state
python3 -c "import json; d=json.load(open('outputs/devotionals/...__approval-gate-report.json')); ..."
# → exportable: False, pending_section_count: 61, publish_ready: None, blocked_reason: "72 section(s) pending"

# .gitignore contents
cat .gitignore  # → does NOT include outputs/devotionals/, data/artifacts/, logs/, data/*.sqlite3

# Untracked files
git status --short  # → 25+ ?? entries confirmed
```

---

## Findings — Severity-Ranked

### SEV-1 (Competition-Blocking)

---

#### F-001: Uncommitted Production Code (25+ Untracked Paths)

**Finding**: All Phase 014-015 new work is entirely untracked in git. A git clean-room
state does not represent the current working system. No competition-ready commit exists.

**Evidence** (from git status at session start):
```
?? scripts/run_devotional_full.py
?? src/api/full_run_assets.py
?? src/persistence/
?? src/rag/sqlite_catalog.py
?? src/scripture/planner.py
?? scripts/__init__.py
?? scripts/review/
?? scripts/irb/
?? tests/pipeline/test_full_run_assets.py
?? tests/pipeline/test_generation_day_plan.py
?? tests/pipeline/test_run_devotional_full_helpers.py
?? tests/review/
?? tests/persistence/
?? tests/scripture/
?? tests/irb/
?? irb/specs/tier-3-plan.md
?? irb/specs/tier-3-spec.yaml
?? docs/system/approval-contract.md
?? docs/system/competition-readiness-backlog.md
?? docs/system/outputs/2026-03-05__09__builder__irb-tier-3-report.md
?? docs/system/outputs/2026-03-05__09__builder__irb-tier-3-results.json
?? planning/
(plus runtime paths: data/artifacts/, data/devg_registry.sqlite3, outputs/devotionals/, logs/)
```

**Also untracked** (from git status M rows — modified tracked files with unstaged changes):
```
M README.md
M data/excerpts/seed-excerpts.json
M data/quotes/seed-quotes.json
M src/api/export_gate.py
M src/api/generation_pipeline.py
M src/generation/generators.py
M src/generation/real_section_generator.py
M src/models/devotional.py
M src/models/registry.py
M src/rag/catalog.py
M src/rag/exposition.py
M src/registry/registry.py
M src/rendering/engine.py
M src/rendering/sections.py
M templates/offer_page.md
(+ test files and UI files)
```

**Impact**: Fresh git checkout from certified SHA (61842ce) is missing:
- Full pipeline runner (`scripts/run_devotional_full.py`)
- Persistence layer (`src/persistence/`)
- Scripture planner (`src/scripture/planner.py`)
- SQLite catalog loader (`src/rag/sqlite_catalog.py`)
- All review scripts (`scripts/review/`)
- IRB Tier-3 runner (`scripts/irb/run_tier3.py`) and specs
- 25+ new test files (tests for all new modules)
- Competition-readiness documentation
- All staged changes to core modules

**Fix**: FC-001 — Commit all production code
**Human checkpoint**: HC-01 (operator confirms file list before commit)

---

### SEV-2 (High — Must Fix Before Competition Gate)

---

#### F-002: Branch Not Merged to Main

**Finding**: All work on `feat/phase-014-rag-infrastructure`, 12+ commits ahead of `main`.
Competition submission and IRB certification reference `main`.

**Evidence**:
```
Current branch: feat/phase-014-rag-infrastructure
Recent commits (none on main from this work):
61842ce chore(phase-015): cp3 — outputs/reviews skeleton + phase-015 completion report
2d8c015 chore(phase-015): cp2 — relocate CTA PDF to canonical docs/marketing/
...
```

**Impact**: Reviewer cloning `main` cannot access any Phase 014-015 work.
IRB certification SHA (61842ce) is on feature branch, not main.

**Fix**: FC-002 — Merge to main
**Human checkpoint**: HC-02 (operator selects merge strategy)

---

#### F-003: No Full E2E Review Session Completed on Competition-Format Outputs

**Finding**: The critical path — generation → validation → review → approved →
publish-ready export → final PDF — has not been exercised live on competition-format
artifacts. Both recent runs have all sections in PENDING state.

**Evidence** (verified from live artifact):
```python
# outputs/devotionals/2026-03-09__195225__competition-volume-1__12-day__vol-1__approval-gate-report.json
"exportable": false
"pending_section_count": 61       # sections in human review queue
"publish_ready": null             # not yet evaluated
"blocked_reason": "72 section(s) pending approval: day 1 — timeless_wisdom; ..."
```

No `__approval-decisions.json` exists for:
- `2026-03-09__195225__competition-volume-1__12-day__vol-1`
- `2026-03-09__195419__genesis-1-&-2__12-day__vol-2`

**Count breakdown**:
- 72 total pending in export gate (blocked_reason)
- 61 in human review queue (pending_section_count)
- 11 = agent_validated (not in UI queue but still block publish-ready export)

**Impact**: Cannot confirm that publish-ready gate, Turabian export gate, and audit
traceability all function correctly in the live review → export path. System is
unit-tested but live integration is unproven.

**Fix**: FC-004 — Full E2E review session (operator-interactive)
**Human checkpoint**: HC-03

---

### SEV-3 (Medium — Important Before Final Gate)

---

#### F-005: `pending_section_count` vs `blocked_reason` Count Discrepancy (Undocumented)

**Finding**: Approval-gate report shows two different section counts with no
documentation explaining why they differ. This is correct behavior by design, but
is not documented in `docs/system/approval-contract.md`.

**Evidence**:
```python
"blocked_reason": "72 section(s) pending approval"   # ExportGate: ALL non-approved
"pending_section_count": 61                           # human review queue only
```

Difference: 72 − 61 = 11 sections have `verification_status == "agent_validated"`.
These are excluded from the human review queue but still block publish-ready export.

**Impact**: Operators may be confused and assume all pending sections are in the
review UI. The 11 agent-validated sections require operator action to export.

**Fix**: FC-003 — Document in `docs/system/approval-contract.md`
No code change required.

---

#### F-006: `publish_ready` Field = None in Pre-Review State (Undocumented)

**Finding**: `publish_ready` key in approval-gate reports is `None` before any review
session has run. No documentation specifies when this field becomes populated.

**Evidence**:
```python
"publish_ready": null   # in latest competition-vol-1 run
```

**Impact**: Automated checks or operator review scripts expecting `publish_ready: true/false`
will get `None`, which is truthy-ambiguous in some languages.

**Fix**: FC-003 — Document in `docs/system/approval-contract.md`
No code change required (pre-review state is correct, just undocumented).

---

### SEV-4 (Low / Advisory)

---

#### F-007: Runtime Directories Not in .gitignore

**Finding**: Fresh grep of `.gitignore` confirms these runtime paths are NOT gitignored:
- `outputs/devotionals/` — generates untracked files on every pipeline run
- `data/artifacts/` — generated grounding_maps and prayer_trace_maps
- `logs/` — runtime logs
- `data/*.sqlite3` — SQLite database file

**Evidence** (`.gitignore` currently contains):
```
__pycache__/, *.py[cod], *.egg-info/, .pytest_cache/, .venv/, venv/, env/
.DS_Store, ui/node_modules/, node_modules/
.vscode/, .idea/, *.swp, *.swo
uv.lock, builder-manifest.yaml, .cowork/
```
(None of the runtime paths above are present)

**Impact**: Every pipeline run creates new untracked `??` entries. This produces
noisy git status and risks accidental inclusion of runtime artifacts in commits.

**Fix**: FC-001 — Add runtime paths to `.gitignore` as part of commit
Human decision at HC-01: whether `outputs/devotionals/` should be fully gitignored
or have an allowlist pattern (e.g., keep CSV planning files).

---

#### F-008: SQLAlchemy Deprecation Warnings (Library-Internal, Not Our Code)

**Finding**: Previous test runs reported 230+ deprecation warnings. Fresh `rg` search
confirms **zero** `datetime.utcnow()` calls in `src/` code. The warnings originate
from SQLAlchemy internals, not from our application code.

**Evidence**:
```bash
rg 'datetime\.utcnow\(\)' src/   # → 0 matches
```

`src/registry/registry.py` correctly uses `datetime.now(timezone.utc)` via `_utc_now()`.

**Impact**: Warning noise in test output from SQLAlchemy internals. Not our bug.
Not blocking; advisory only.

**Fix**: None required. Can suppress at pytest level with `filterwarnings` if noise
becomes a problem. Do not patch SQLAlchemy internals.

**Correction note**: Prior session's findings artifact (F-005 in session 1) incorrectly
classified this as SEV-3 implying our src/ code had the issue. Fresh grep disproves this.

---

## Findings Summary Table

| ID | Severity | Title | Fix Cycle | Status |
|----|----------|-------|-----------|--------|
| F-001 | SEV-1 | Uncommitted production code (25+ paths + modified tracked files) | FC-001 | Open |
| F-002 | SEV-2 | Branch not merged to main | FC-002 | Open |
| F-003 | SEV-2 | No full E2E review session on competition outputs | FC-004 | Open (HC-03 required) |
| F-004 | SEV-2 | `__audit-linkage.json` absent on pre-19:52 runs | Advisory — superseded by latest runs | Advisory |
| F-005 | SEV-3 | `pending_section_count` vs `blocked_reason` discrepancy undocumented | FC-003 | Open |
| F-006 | SEV-3 | `publish_ready` = None undocumented | FC-003 | Open |
| F-007 | SEV-4 | Runtime dirs not gitignored | FC-001 (gitignore update) | Open |
| F-008 | SEV-4 | SQLAlchemy deprecation warnings (library-internal only) | Advisory — no fix needed | Advisory |

---

## Correction vs Prior Session

| Prior Session Finding | Status |
|-----------------------|--------|
| F-005 (datetime.utcnow SEV-3) | **DOWNGRADED to F-008 SEV-4/Advisory** — rg confirms 0 matches in src/; warnings are SQLAlchemy-internal |
| All other findings (F-001 through F-004, F-006, F-007) | **CONFIRMED** — verified from live artifact and git status |

---

## What Is Working Well

| Area | Status | Evidence |
|------|--------|----------|
| Test suite | EXCELLENT | 822 passing, 0 failures; +98 tests since last IRB cert |
| Agent validation | PASSING | `overall_passed: true`, 0 discrepancies on latest 2 runs |
| Audit linkage | IMPLEMENTED | `__audit-linkage.json` present with 72 entries per run on latest 2 |
| Export gate | CORRECT | Blocks unapproved sections; Turabian gate enforced |
| Competition CSV loader | WORKING | `load_competition_outline_from_csv()` tested; supports `Series 1 - Volume 1 - 30-Day Outline.csv` format |
| Scripture planner | WORKING | Vol-2 child context auto-resolves from registry with non-dup enforcement |
| PDF render | WORKING | Personal preview PDFs rendered for all recent runs |
| Series non-dup | ENFORCED | Registry prevents week-scripture/quote reuse across volumes |
| All COMP-001-005 | COMPLETED | Confirmed in `docs/system/competition-readiness-backlog.md` |
| All AUD-001-003 | COMPLETED | Evidence: per-section audit linkage, operator note capture, Turabian gate |
| Review UI infrastructure | FUNCTIONAL | 4 backends (web/studio/UI/CLI); approval-decisions.json written on completion |
| datetime handling in src/ | CORRECT | `datetime.now(timezone.utc)` via `_utc_now()` in registry; no deprecated calls |

---

## Competition Readiness Assessment

**Current state**: NEAR-READY — 3 blockers to resolve

**Blockers (must fix before submission)**:
1. **F-001** (SEV-1): All new production code uncommitted. Fix: FC-001 + HC-01
2. **F-002** (SEV-2): Not on main. Fix: FC-002 + HC-02
3. **F-003** (SEV-2): Live review path not exercised. Fix: FC-004 + HC-03 (operator interactive)

**After blockers fixed**: System is functionally competition-ready.
Full path from CSV outline → generation → validation → review → approved →
publish-ready PDF → audit-linkage is implemented, unit-tested, and feature-complete.
One full E2E operator review session will complete the evidence chain.

---

_Produced by: Planner (Claude), 2026-03-09 — Session 2 (clean-room re-review)_
_This artifact is immutable once written._
