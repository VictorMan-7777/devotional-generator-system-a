# Two-Eyes System Review — Execution Plan (Cycle 1B)
**Date:** 2026-03-10
**Artifact:** `2026-03-10__10__devg__two-eyes-system-review-plan.md`
**Session:** Section 1 — Planning Only (no code edits)
**Branch:** feat/phase-014-rag-infrastructure
**Scope:** Clean-room verification of system state post-Cycle-1A; plan for Cycle 1B

---

## Context: What Cycle 1A Fixed

Cycle 1A (artifact `2026-03-10__09__devg__two-eyes-cycle-1a-results.md`) applied a
one-line semantic fix to `build_approval_gate_report` in `src/api/full_run_assets.py`:

```python
# Before (ISSUE-1 — invisible agent_validated sections):
pending_sections, previews, section_meta = build_pending_sections_and_previews(book)

# After (ISSUE-1 RESOLVED):
pending_sections, previews, section_meta = build_pending_sections_and_previews(
    book, include_agent_validated=True
)
```

**Verified in code:** `src/api/full_run_assets.py:530` — `include_agent_validated=True` confirmed present.

---

## Current Open Issues (Code-Verified)

### ISSUE-2 — No Decision-Application + Publish-Ready Export CLI
**Severity:** HIGH — Blocking. No executable path from decisions.json to publish-ready PDF.
**Status:** Confirmed open. No `export_approved_devotional.py` or equivalent in `scripts/`.
**Evidence:**
- `scripts/` contains: `__init__.py`, `irb/`, `rag/`, `review/`, `run_devotional_full.py`
- No post-approval export script exists
- `run_pending_approvals.py` writes `__approval-decisions.json` but does NOT apply
  `approval_status` mutations to `__book.json`
- `run_review_studio.py` applies in-session edits but is not a CLI command

### ISSUE-3 — PDF Heading Normalization Regex Regression
**Severity:** MEDIUM — Confirmed failing. 1 vitest test fails.
**Status:** Confirmed open.
**Evidence:**
- `ui/pdf/blocks.ts:59`: `/[\\s-]+/g` (broken — matches literal `\` and `s`, not whitespace)
- Vitest: 1 FAIL, 25 PASS (test: `normalizeHeadingText maps internal section keys to reader-facing labels`)
- Failure: `expected 'Timeless Wisdom' received 'timeless_wisdom'`

### ISSUE-4 — Ambient pytest Invocation (System Python)
**Severity:** OPERATIONAL
**Status:** Persistent. System Python lacks pydantic; must use `.venv/bin/python -m pytest`.
**Not a blocker for competition readiness.** Documentation/convention issue only.

---

## E2E Test-and-Review Matrix (Post-Cycle-1A)

| Surface | Test / Script | Current Status | Issue |
|---------|---------------|----------------|-------|
| Generation | `tests/generation/` | PASS (venv) | — |
| Section validation | `tests/generation/test_deterministic_real_section_generator.py` | PASS (venv) | — |
| Export gate — PERSONAL | `tests/pipeline/test_export_gate.py` | PASS (venv) | — |
| Export gate — PUBLISH_READY | `tests/pipeline/test_export_gate.py` | PASS (venv) | — |
| Approval gate report (agent_validated) | `tests/pipeline/test_full_run_assets.py` | **PASS** | ISSUE-1 FIXED |
| Decisions application to book model | (none) | **NO TEST, NO SCRIPT** | ISSUE-2 |
| Publish-ready export gate trigger | (none) | **NO TEST, NO SCRIPT** | ISSUE-2 |
| PDF heading normalization | `ui/pdf/__tests__/blocks.test.ts` | **1 FAIL** | ISSUE-3 |
| Audit/provenance | `tests/pipeline/` | PASS (venv) | — |
| Review UI workflow | `scripts/review/run_review_studio.py` | Functional (in-session only) | ISSUE-2 |
| Scripture correctness (fail-closed) | `tests/pipeline/test_full_run_assets.py` | PASS (venv) | — |
| Series child-volume dedup | `tests/pipeline/test_run_devotional_full_helpers.py` | PASS (venv) | — |
| Registry persistence | `tests/persistence/` | PASS (venv) | — |
| Approval contract parity | `tests/review/test_approval_contract_parity.py` | PASS (venv) | — |

---

## Fix-Cycle Execution Plan

### Cycle 1B — ISSUE-2: Decision-Application + Publish-Ready Export CLI

**Order:** Must be implemented first (highest severity, competition blocker).

**Script to create:** `scripts/export_approved_devotional.py`

**Required behavior:**
1. Accept CLI arguments: `--book-json PATH`, `--decisions-json PATH`, `--output-dir DIR`
2. Load `__approval-decisions.json` via `run_pending_approvals.load_existing_decisions()`
3. Load `__book.json` as `DevotionalBook` via `model_validate`
4. Apply `approval_status = SectionApprovalStatus.APPROVED` for all approved decisions
   - Key match: `(day_number, section_name)` against each `DailyDevotional` section
   - Reject decisions are silently noted; sections remain `PENDING` (they block export — expected)
   - Skipped decisions are not applied (sections remain `PENDING` — block is expected and correct)
5. Persist mutated book JSON atomically to `--output-dir` (same slug, `.atomic_write`)
6. Run `ExportGate().check_exportability(book, OutputMode.PUBLISH_READY)`
7. If exportable:
   - Export PDF via `pdf_export.export_pdf(book, OutputMode.PUBLISH_READY, output_dir)`
   - Print `PUBLISH_READY_PDF=<path>`
   - Exit 0
8. If not exportable:
   - Print `BLOCKED: <blocked_reason>` with list of blocking sections
   - Exit 1 (fail-closed — never silently skip blockers)

**Explicit invariants to preserve:**
- Do NOT auto-approve sections — decisions must already exist in decisions.json
- Do NOT bypass `ExportGate` — gate must run on the mutated book
- Agent decision-source policy: inherit `_ensure_decision_source_policy` from `run_pending_approvals`
- Day 1 sections must appear in decisions just as any other — no special bypass
- Scripture correctness check is NOT re-run (it was already run at generation time)

**Tests to add (in `tests/pipeline/test_export_approved_devotional.py`):**
- `test_approved_decisions_applied_to_book_sections`: decisions.json → all sections APPROVED → book mutated correctly
- `test_exportable_after_all_approved`: ExportGate passes → publish-ready PDF path returned
- `test_not_exportable_when_decisions_incomplete`: Partial decisions → gate blocks → exit 1
- `test_no_bypass_skipped_items`: Skipped decisions leave sections PENDING → gate blocks
- `test_rejected_decision_keeps_section_pending`: Rejected section → blocks export → exit 1

**Pass criteria for Cycle 1B:**
- [ ] `scripts/export_approved_devotional.py` exists and executable
- [ ] All 5 new tests pass
- [ ] All existing `tests/pipeline/` tests continue to pass
- [ ] Dry-run: `python3 scripts/export_approved_devotional.py --book-json <book> --decisions-json <decisions> --output-dir <dir>` emits `PUBLISH_READY_PDF=...` or `BLOCKED:...` — no unhandled exceptions

---

### Cycle 1C — ISSUE-3: PDF Heading Normalization Regex Fix

**Order:** Second. Required for full certification but does not block Cycle 1B.

**File:** `ui/pdf/blocks.ts:59`

**Fix:** Change `/[\\s-]+/g` → `/[\s_-]+/g`
- `\\s` inside a TypeScript/JS regex character class matches literal backslash or `s`; `\s` matches whitespace
- Adding `_` to the character class handles underscore-delimited internal keys (the documented input contract)

**Pass criteria for Cycle 1C:**
- [ ] `ui/pdf/__tests__/blocks.test.ts`: 26/26 pass (all tests pass, 1 FAIL resolved)
- [ ] `normalizeHeadingText('timeless_wisdom')` returns `'Timeless Wisdom'`
- [ ] `normalizeHeadingText('action_steps')` returns `'Walk It Out'`
- [ ] `normalizeHeadingText('be_still')` returns `'Still Before God'`

---

## Human Checkpoints

### Checkpoint A — After Section 1 Artifact Review (THIS CHECKPOINT)

**Required before Cycle 1B proceeds:**
- Operator reviews this plan artifact
- Operator reviews the companion findings artifact `2026-03-10__11__devg__two-eyes-system-review-findings.md`
- Operator grants approval to proceed with implementation

**Operator decision scope:**
1. Confirm ISSUE-2 fix approach (scripts/export_approved_devotional.py with fail-closed behavior)
2. Confirm ISSUE-3 fix approach (regex correction only, no behavior change beyond normalization)
3. Confirm test contract for ISSUE-2 (5 new tests per plan above)

### Checkpoint B — After Cycle 1B Test Pass

**Required before Cycle 1C:**
- Operator re-reviews `scripts/export_approved_devotional.py` implementation
- Confirms new tests accurately reflect the approval contract (especially: skipped/rejected sections block export)
- Confirms no auto-approval bypass introduced

### Checkpoint C — After Cycle 1C + Full Test Run

**Required before Section 3 (Final Test Devotional Gate):**
- All Python tests pass: `N` tests, 0 failures (`.venv/bin/python -m pytest`)
- All TypeScript tests pass: 26/26 pass (`npx vitest run`)
- Operator authorizes Section 3 test devotional run

---

## Preserved System Invariants

The following must not be altered by any fix cycle:

1. **Scripture correctness fail-closed:** `_fail_closed_quality_checks` (run_devotional_full.py:399)
   - Missing scripture text, placeholder text, missing verse precision → SystemExit
   - Not touched by Cycle 1B or 1C

2. **Series child-volume non-dup:** `_enforce_child_week_scripture_exclusions` / `_enforce_child_week_quote_exclusions`
   - Scripture/quote reuse across parent-child volumes → SystemExit
   - Not touched by Cycle 1B or 1C

3. **Day 1 human-review requirement:** `_mark_agent_validated_sections` skips day 1
   - Day 1 sections always appear in pending queue
   - Cycle 1B must NOT apply auto-approval to day 1

4. **Review UI local-time display:** No planned change touches review studio timestamp display

5. **Agent decision-source policy:** `_ensure_decision_source_policy` in run_pending_approvals.py
   - Agent reviewers require `decision_source`; Cycle 1B must inherit this policy when loading decisions

6. **ExportGate never mutates:** `ExportGate.check_exportability` must only read the book, never set fields
   - Mutation in Cycle 1B must happen before ExportGate is called

---

## Artifact Index

| Artifact | Path | Status |
|----------|------|--------|
| This plan | `docs/system/outputs/2026-03-10__10__devg__two-eyes-system-review-plan.md` | COMPLETE |
| Companion findings | `docs/system/outputs/2026-03-10__11__devg__two-eyes-system-review-findings.md` | COMPLETE |
| Cycle 1A results | `docs/system/outputs/2026-03-10__09__devg__two-eyes-cycle-1a-results.md` | COMPLETE (approved) |
| Cycle 1B results | (not yet created) | PENDING |
| Cycle 1C results | (not yet created) | PENDING |
| Competition readiness backlog | `docs/system/competition-readiness-backlog.md` | STALE — needs update after cycles |
