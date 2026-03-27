# DevG Two-Eyes System Review — Findings Report (Session 3)

**Artifact ID**: 2026-03-09__06__devg__two-eyes-system-review-findings
**Role**: Planner (Claude)
**Date**: 2026-03-09
**Mode**: clean-room review (read-only, no implementation)
**Branch**: feat/phase-014-rag-infrastructure
**IRB baseline**: Tiers 1, 1.5, 2, 3 CERTIFIED (2026-03-05, SHA 61842ce)
**Supersedes**: 2026-03-09__04__devg__two-eyes-system-review-findings (Session 2)

---

## System State Snapshot

| Metric | Value |
|--------|-------|
| Active branch | `feat/phase-014-rag-infrastructure` |
| Commits ahead of `main` | 13 |
| Untracked entries | 37 (files + directories) |
| Modified tracked files | 23 |
| Test count | 822 passing, 0 failures (re-verified this session) |
| Prior cert test count | 724 (at Phase 015, 2026-03-05) |
| Test delta | +98 tests since last IRB cert |
| IRB Tiers certified | 1, 1.5, 2, 3 (last cert 2026-03-05, SHA 61842ce) |
| Competition run slug (latest vol-1) | `2026-03-09__195225__competition-volume-1__12-day__vol-1` |
| Latest genesis vol-2 run slug | `2026-03-09__195419__genesis-1-&-2__12-day__vol-2` |
| Agent validation (latest runs) | PASSED — `overall_passed: true` |
| `__audit-linkage.json` entry count | 72 (list structure, confirmed via JSON parse) |
| `__approval-decisions.json` on latest competition runs | ABSENT |
| All COMP-001–005 items | COMPLETED |
| All AUD-001–003 items | COMPLETED |

---

## Review Methodology

Clean-room review. Session 2 context treated as non-authoritative.
All findings re-verified from live repository state this session.

**Key verification commands run this session**:
```bash
# Untracked file count
git status --short | grep '^\?\?' | wc -l   # → 37

# Modified tracked file count
git status --short | grep '^.M' | wc -l     # → 23

# Commits ahead of main
git log --oneline main..HEAD | wc -l         # → 13

# Test suite (venv)
.venv/bin/python3 -m pytest -q --tb=no      # → 822 passed, 0 failed (background run)

# Audit-linkage entry count
.venv/bin/python3 -c "import json,glob; d=json.load(open(glob.glob('outputs/devotionals/*audit-linkage.json')[0])); print(type(d['entries']).__name__, len(d['entries']))"
# → list 72

# Approval gate report
.venv/bin/python3 -c "import json,glob; f=sorted(glob.glob('outputs/devotionals/*approval-gate-report.json'))[-1]; d=json.load(open(f)); print(d.get('exportable'), d.get('pending_section_count'), d.get('publish_ready'))"
# → False 61 None

# Approval decisions on latest runs
ls outputs/devotionals/*195225*approval-decisions* 2>/dev/null   # → no such file
ls outputs/devotionals/*195419*approval-decisions* 2>/dev/null   # → no such file

# datetime.utcnow in src/
rg 'datetime\.utcnow\(\)' src/               # → 0 matches

# .gitignore check
grep -E 'outputs/devotionals|data/artifacts|logs/|data/\*\.sqlite3' .gitignore  # → no matches
```

---

## Findings — Severity-Ranked

### SEV-1 (Competition-Blocking)

---

#### F-001: Uncommitted Production Code (37 Untracked Paths) — CONFIRMED OPEN

**Status**: OPEN — identical to Session 2 finding. No commits since Session 2.

**Finding**: All Phase 014-015 new work remains entirely untracked in git. A fresh git
checkout from any SHA would be missing the entire new system.

**Evidence** (re-verified this session via `git status --short`):
```
?? scripts/__init__.py
?? scripts/irb/
?? scripts/review/
?? scripts/run_devotional_full.py
?? src/api/full_run_assets.py
?? src/persistence/
?? src/rag/sqlite_catalog.py
?? src/scripture/planner.py
?? tests/irb/
?? tests/persistence/
?? tests/pipeline/test_full_run_assets.py
?? tests/pipeline/test_generation_day_plan.py
?? tests/pipeline/test_run_devotional_full_helpers.py
?? tests/review/
?? tests/scripture/
?? irb/specs/tier-3-plan.md
?? irb/specs/tier-3-spec.yaml
?? docs/system/approval-contract.md
?? docs/system/competition-readiness-backlog.md
?? docs/system/outputs/2026-03-05__09__builder__irb-tier-3-report.md
?? docs/system/outputs/2026-03-05__09__builder__irb-tier-3-results.json
?? docs/system/outputs/2026-03-09__01..04__ (4 files)
?? planning/ (entire directory)
?? data/artifacts/
?? data/devg_registry.sqlite3
?? logs/
?? outputs/devotionals/
```
(Total: 37 untracked entries)

**Modified tracked files** (23, also unstaged):
```
M src/api/export_gate.py (+43/-0)
M src/api/generation_pipeline.py (+110/-266)
M src/generation/generators.py (+75/-0)
M src/generation/real_section_generator.py (+362/-0)
M src/rag/catalog.py (+80/-0)
M src/rag/exposition.py (+16/-0)
M src/models/devotional.py (+9/-0)
M src/models/registry.py (+26/-0)
M src/registry/registry.py (+267/-0)
M src/rendering/engine.py (+31/-0)
M src/rendering/sections.py (+37/-0)
M data/excerpts/seed-excerpts.json (+52/-266)
M data/quotes/seed-quotes.json (+218/-0)
M templates/offer_page.md (+2/-1)
M README.md (+66/-0)
(+ 8 test and UI files)
```

**Impact**: Fresh git checkout from certified SHA (61842ce) is missing all of Phase 014-015.

**Fix**: FC-001 — Commit all production code
**Human checkpoint**: HC-01 (operator confirms file list before commit)

---

### SEV-2 (High — Must Fix Before Competition Gate)

---

#### F-002: Branch Not Merged to Main (13 Commits Ahead) — CONFIRMED OPEN

**Status**: OPEN — 13 commits ahead of main (up from 12 in Session 2, confirming no merge).

**Finding**: All work on `feat/phase-014-rag-infrastructure`. Competition and IRB
certification reference `main`. No Phase 014-015 work visible from main.

**Evidence**:
```
git log --oneline main..HEAD  # → 13 commits
```
Recent commits (not on main):
```
61842ce chore(phase-015): cp3 — outputs/reviews skeleton + phase-015 completion report
2d8c015 chore(phase-015): cp2 — relocate CTA PDF to canonical docs/marketing/
6eb311a chore(phase-015): cp1 — gitignore .cowork/, commit 6 untracked output artifacts
2ac1e15 docs(governance): add Tier 0 governance reference (rules-laws v0.4)
0c1a7df fix(irb-instance): prevent tier-1.5 self-scan false positives
```

**Fix**: FC-002 — Merge to main
**Human checkpoint**: HC-02

---

#### F-003: No Full E2E Review Session on Competition-Format Outputs — CONFIRMED OPEN

**Status**: OPEN — no `__approval-decisions.json` exists for either of the latest
competition-format runs (195225 vol-1 or 195419 vol-2).

**Note**: Earlier runs (2026-03-07) DO have `__approval-decisions.json` but those
used a different slug format and pre-dated the competition outline CSV loader.
The competition-ready runs (2026-03-09 ≥ 19:52) have not been reviewed.

**Evidence** (re-verified this session):
```python
# Latest competition vol-1 run
"exportable": false
"pending_section_count": 61   # sections in human review queue
"publish_ready": null          # not evaluated yet
"blocked_reason": "72 section(s) pending approval: ..."

# approval-decisions.json for 195225 slug: ABSENT
# approval-decisions.json for 195419 slug: ABSENT
```

**Count breakdown** (re-verified):
- 72 total blocked in export gate (blocked_reason — ALL non-approved)
- 61 in human review queue (pending_section_count — excludes agent_validated)
- 11 = agent_validated sections (not in UI queue, still block publish-ready export)

**Fix**: FC-004 — Full E2E review session (operator-interactive)
**Human checkpoint**: HC-03

---

### SEV-3 (Medium — Important Before Final Gate)

---

#### F-005: `pending_section_count` vs `blocked_reason` Discrepancy Undocumented — CONFIRMED OPEN

**Status**: OPEN — `docs/system/approval-contract.md` read this session and does NOT
contain documentation of this count difference.

**Evidence**:
```
# From 195419 run:
"blocked_reason": "72 section(s) pending approval"   # ExportGate: ALL non-approved
"pending_section_count": 61                           # UI review queue only

# approval-contract.md current content:
# - Defines section states (pending | approved | rejected)
# - Defines approval session resumability
# - Does NOT explain 61 vs 72 discrepancy
# - Does NOT define what "agent_validated" sections mean in context of both counts
```

**Fix**: FC-003 — Add section to approval-contract.md

---

#### F-006: `publish_ready = None` Pre-Review State Undocumented — CONFIRMED OPEN

**Status**: OPEN — same as F-005, the contract does not document this lifecycle state.

**Evidence**:
```python
"publish_ready": null   # in both latest competition-vol-1 and vol-2 runs
```

**Fix**: FC-003 — Covered in same doc update as F-005

---

### SEV-4 (Low / Advisory)

---

#### F-007: Runtime Directories Not in .gitignore — CONFIRMED OPEN

**Status**: OPEN — re-verified this session; none of the four runtime paths are in .gitignore.

**Evidence** (`.gitignore` complete contents — runtime entries absent):
```
__pycache__/, *.py[cod], *.egg-info/, *.egg
.pytest_cache/, .coverage, htmlcov/
.venv/, venv/, env/
.DS_Store, .AppleDouble, .LSOverride
ui/node_modules/, node_modules/
.vscode/, .idea/, *.swp, *.swo
uv.lock, builder-manifest.yaml
.cowork/
```
Not present: `outputs/devotionals/`, `data/artifacts/`, `logs/`, `data/*.sqlite3`

**Fix**: FC-001 (gitignore additions bundled with commit)

---

#### F-008: SQLAlchemy Deprecation Warnings (Library-Internal) — Advisory

**Status**: Advisory — unchanged. Zero `datetime.utcnow()` calls in `src/` (re-verified).
Warnings originate from SQLAlchemy internals.

**Fix**: None required in our codebase.

---

#### F-009: Malformed Stub Artifacts in `planning/` Directory — NEW (Session 3)

**Finding**: Two files in `planning/` are not valid planning documents:
- `planning/2026-03-09__01__DevG-plan.md` — 113 bytes
- `planning/2026-03-09__02__DevG-plan.md` — 114 bytes

Content of both files is a single line of test-run result text, not planning content.
These appear to be artifacts from a session where a prior planner tested the artifact
naming system. They follow the NN naming convention but are not actual planning artifacts.

**Evidence**:
```bash
wc -c planning/2026-03-09__01__DevG-plan.md  # → 113 bytes
wc -c planning/2026-03-09__02__DevG-plan.md  # → 114 bytes
```

**Impact**: Low — but if committed, they pollute the planning history. Operator should
decide whether to delete them or exclude them from the commit at HC-01.

**Fix**: Advisory — operator decision at HC-01 (delete before commit, or leave untracked)

---

#### F-010: Runtime Artifact in `planning/` Directory — NEW (Session 3)

**Finding**: `planning/debate_transcript_20260309_172649.json` is a 6,457-byte runtime
transcript file in the planning directory. Not a planning artifact.

**Impact**: Low — should not be committed. Operator should gitignore or delete at HC-01.

**Fix**: Advisory — add to gitignore pattern or delete at HC-01

---

## Findings Summary Table

| ID | Severity | Title | Fix Cycle | Status |
|----|----------|-------|-----------|--------|
| F-001 | SEV-1 | Uncommitted production code (37 untracked entries + 23 modified tracked) | FC-001 | **OPEN** |
| F-002 | SEV-2 | Branch not merged to main (13 commits ahead) | FC-002 | **OPEN** |
| F-003 | SEV-2 | No full E2E review session on competition-format runs | FC-004 | **OPEN** (HC-03 required) |
| F-005 | SEV-3 | `pending_section_count` (61) vs `blocked_reason` (72) undocumented | FC-003 | **OPEN** |
| F-006 | SEV-3 | `publish_ready = None` pre-review lifecycle undocumented | FC-003 | **OPEN** |
| F-007 | SEV-4 | Runtime dirs not in .gitignore | FC-001 | **OPEN** |
| F-008 | SEV-4 | SQLAlchemy deprecation warnings (library-internal) | Advisory | Advisory |
| F-009 | SEV-4 | Malformed stub artifacts in planning/ (113–114 bytes) | HC-01 cleanup | Advisory |
| F-010 | SEV-4 | `planning/debate_transcript` runtime artifact | HC-01 cleanup | Advisory |

---

## Corrections vs Prior Sessions

| Prior Session Finding | Session 3 Status |
|-----------------------|-----------------|
| Explore agent reported audit-linkage "4 top-level dict keys" | **CORRECTED**: Structure is `list` with 72 elements. Explore agent misread. Confirmed by `.venv/bin/python3` JSON parse: `list 72`. |
| All F-001–F-008 from Session 2 | **CONFIRMED OPEN** — zero changes between Session 2 and Session 3 |
| F-008 (datetime.utcnow) advisory classification | **CONFIRMED** — 0 matches in src/ |

---

## What Is Working Well

| Area | Status | Evidence |
|------|--------|----------|
| Test suite | EXCELLENT | 822 passing, 0 failures (re-verified Session 3) |
| Agent validation | PASSING | `overall_passed: true` on latest competition runs |
| Audit linkage | IMPLEMENTED | 72-entry list in `__audit-linkage.json` (not dict as explore agent misreported) |
| Export gate | CORRECT | Correctly blocks; 72 pending, Turabian gate enforced |
| Competition CSV loader | WORKING | Tested; accepts competition outline format |
| Scripture planner | WORKING | Vol-2 child context auto-resolves; non-dup enforced |
| PDF render (personal) | WORKING | `__kdp-personal-preview.pdf` ~1MB on latest runs |
| Series non-dup | ENFORCED | Registry prevents scripture/quote reuse across volumes |
| All COMP-001–005 | COMPLETED | Confirmed in competition-readiness-backlog.md |
| All AUD-001–003 | COMPLETED | Confirmed in competition-readiness-backlog.md |
| datetime handling | CORRECT | `datetime.now(timezone.utc)` via `_utc_now()`; no deprecated calls |
| Earlier review sessions | FUNCTIONAL | 6 `__approval-decisions.json` files from 2026-03-07 sessions |

---

## Competition Readiness Assessment

**Current state**: NEAR-READY — same 3 blockers as Session 2, unchanged.

**Blockers (must fix before submission)**:
1. **F-001** (SEV-1): All new production code uncommitted. Fix: FC-001 + HC-01
2. **F-002** (SEV-2): Not on main. Fix: FC-002 + HC-02
3. **F-003** (SEV-2): Live review path not exercised on competition-format runs. Fix: FC-004 + HC-03

**Timeline note**: All three blockers were identified in Session 1. No progress toward
resolution has occurred between Session 1 (∼16:25), Session 2 (∼16:53–17:28), and
Session 3 (this session). The fix cycles are ready to execute; HC-01 approval is the
only gate remaining before FC-001 can begin.

---

_Produced by: Planner (Claude), 2026-03-09 — Session 3 (clean-room re-review)_
_This artifact is immutable once written._
