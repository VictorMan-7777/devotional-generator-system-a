# Two-Eyes System Review — Fix-Cycle Execution Plan
**Date:** 2026-03-10
**Artifact:** `2026-03-10__07__devg__two-eyes-system-review-plan.md`
**Session:** Section 1 — Planning Only (no code edits)

---

## Overview

This plan covers three fix cycles and one final gate, ordered by severity. All issues are code-verified against the current repo state. The plan is deterministic: each cycle has explicit entry conditions, pass criteria, and human checkpoints.

---

## Cycle 1A — Resolve review/export semantic mismatch

### Entry condition
Planning approval received from human.

### Scope
**File:** `src/api/full_run_assets.py`
**Function:** `build_approval_gate_report` (line 528–543)

**Root cause confirmed:**
`build_approval_gate_report` calls `build_pending_sections_and_previews(book)` without `include_agent_validated=True`. This means sections with `verification_status == "agent_validated"` are invisible in the operator-facing pending queue. However, `ExportGate.check_exportability` (export_gate.py:55) checks `approval_status != APPROVED` for all sections, regardless of verification status. An operator can drain every visible item in the pending queue and still get a blocked publish-ready export.

### Chosen semantic (to be implemented)
Surface `agent_validated` sections in the review queue by passing `include_agent_validated=True` inside `build_approval_gate_report`. This is the minimal, fail-closed fix that does not require a new promotion path and preserves the existing export gate invariant.

**Do NOT implement the alternative** (a silent promotion path that auto-approves agent-validated sections without surfacing them) — that would bypass the human review requirement and violate the fail-closed contract.

### Deliverables
1. One-line change to `build_approval_gate_report`: add `include_agent_validated=True` to the `build_pending_sections_and_previews` call.
2. Targeted test demonstrating the fix:
   - Book with at least one `agent_validated` section must appear in the pending report's `pending_sections` list.
   - Book with all sections `APPROVED` must have empty pending list and `exportable=True`.
3. Written one-paragraph summary of what Cycle 1B will codify.

### Pass criteria
- [ ] `pending_sections` in approval gate report includes `agent_validated` sections
- [ ] `ExportGate.check_exportability(book, PUBLISH_READY)` still blocks when any section has `approval_status != APPROVED`
- [ ] All existing `tests/pipeline/test_full_run_assets.py` and `tests/pipeline/test_export_gate.py` tests pass
- [ ] New targeted test passes

---

## HUMAN CHECKPOINT — Between Cycle 1A and 1B

**Approval required before Cycle 1B starts.**

The operator must review:
1. The code change (one-line diff in `build_approval_gate_report`)
2. The new test and its assertion
3. The Cycle 1B scope summary

**Decision needed:** Approve the semantic (surface `agent_validated` in queue) and authorize Cycle 1B.

---

## Cycle 1B — Add deterministic decision-application and publish-ready export path

### Entry condition
Human checkpoint after Cycle 1A approved.

### Scope
**New script:** `scripts/apply_decisions_and_export.py`
(or inline extension to `scripts/run_devotional_full.py` — see below)

**Root cause confirmed:**
No CLI path exists that reads a committed `__approval-decisions.json`, applies `approval_status = APPROVED` for each `approved` decision back into `__book.json`, re-runs `ExportGate.check_exportability(book, PUBLISH_READY)`, and emits a publish-ready PDF.

`run_pending_approvals.py` writes decisions to the JSON file but does not mutate the book model.
`run_review_studio.py` applies edits to `__book.json` atomically within the web UI session, but only for edited content, not for approval-status promotion.

### Required behavior
A new CLI command (separate script or new subcommand) must:
1. Accept `--book-json <path>` and `--decisions-json <path>` as inputs.
2. Load the book JSON and decisions JSON.
3. For each `decision == "approved"` record, set `sections[day][section].approval_status = "approved"` in the book model.
4. For each `decision == "rejected"` record, set `approval_status = "rejected"`.
5. Persist the updated book JSON atomically (tmp-then-replace).
6. Re-run `ExportGate.check_exportability(book, OutputMode.PUBLISH_READY)`.
7. If `exportable=True`, run the PDF export and emit the publish-ready PDF.
8. If `exportable=False`, print blocked reasons and exit non-zero (fail-closed).
9. Print `PUBLISH_READY_PDF=<path>` on success.

### Deliverables
1. New script implementing the above.
2. Tests covering:
   - All sections approved → export proceeds → `exportable=True`
   - One section rejected → export blocked → non-zero exit
   - Decisions file has decision for unknown section → tolerated without error (extra decisions ignored)
   - Empty decisions file → all sections remain PENDING → export blocked
3. Updated `scripts/run_devotional_full.py` meta output to include the apply-decisions command as a follow-up hint.

### Pass criteria
- [ ] `apply_decisions_and_export.py --book-json X --decisions-json Y` applies decisions and re-runs export gate
- [ ] `exportable=True` path emits publish-ready PDF without error
- [ ] `exportable=False` path exits non-zero and prints blocked reasons
- [ ] All new tests pass
- [ ] No validator bypass introduced (scripture correctness path untouched)

---

## Cycle 2 — Fix PDF heading normalization regex

### Entry condition
Cycle 1B complete (can be done independently if Cycle 1B takes time, but must not be merged before Cycle 1A is approved).

### Scope
**File:** `ui/pdf/blocks.ts`
**Function:** `normalizeHeadingText` (line 56–64)

**Root cause confirmed:**
Line 59: `/[\\s-]+/g` is a double-escaped regex. Inside a JS/TS character class, `\\s` means literal `\` and `s`, not the `\s` whitespace shorthand. The correct expression is `/[\s_-]+/g` (whitespace, underscore, hyphen → underscore).

**Impact:** `normalizeHeadingText('timeless_wisdom')` returns `'timeless_wisdom'` instead of `'Timeless Wisdom'` (confirmed by failing vitest test at `blocks.test.ts:100`).

**Practical blast radius:** Python rendering already emits correct reader-facing label strings (e.g., "Timeless Wisdom"). The broken path only fires if an internal section key is passed directly as heading content. However, the function is exported and the test contract documents the expected behavior — the regression must be fixed.

### Deliverable
Single-character fix: change `/[\\s-]+/g` to `/[\s_-]+/g` (add `_` to normalize underscores to underscores, fix `\\s` → `\s`).

### Pass criteria
- [ ] `normalizeHeadingText('timeless_wisdom')` returns `'Timeless Wisdom'`
- [ ] `normalizeHeadingText('action_steps')` returns `'Walk It Out'`
- [ ] `normalizeHeadingText('be_still')` returns `'Still Before God'`
- [ ] `normalizeHeadingText('Day 1 — Hope')` returns `'Day 1 — Hope'` (passthrough preserved)
- [ ] All 26 vitest tests pass

---

## Cycle 3 — Harden execution discipline

### Entry condition
Cycles 1A, 1B, and 2 complete.

### Scope
1. **Ambient pytest invocation:** `python3 -m pytest tests/ -q` fails with `SystemExit: Missing runtime dependencies`. Operator must use `.venv/bin/python3 -m pytest`. Fix by adding a `Makefile` target or `scripts/run_tests.sh` that uses the venv Python.
2. **Documented command set:** `scripts/run_devotional_full.py` meta output and `docs/system/competition-readiness-backlog.md` must include canonical commands for: (a) full run, (b) review studio launch, (c) decision apply + publish-ready export.

### Deliverables
1. `Makefile` or `scripts/run_tests.sh` with `.venv/bin/python3 -m pytest tests/` as the test command.
2. Updated `docs/system/competition-readiness-backlog.md` with canonical competition run command set.

### Pass criteria
- [ ] `make test` or `./scripts/run_tests.sh` runs all Python tests via venv without INTERNALERROR
- [ ] All 83 Python tests pass
- [ ] Competition command set is documented and correct

---

## E2E Test-and-Review Matrix

| Surface | Test File(s) | Status |
|---------|-------------|--------|
| Generation pipeline | `tests/generation/` | 83 Python tests pass |
| Export gate — PERSONAL mode | `tests/pipeline/test_export_gate.py` | PASS |
| Export gate — PUBLISH_READY mode | `tests/pipeline/test_export_gate.py` | PASS |
| Full run assets — pending queue | `tests/pipeline/test_full_run_assets.py` | PASS (but `agent_validated` exclusion is the mismatch) |
| PDF block rendering | `ui/pdf/__tests__/blocks.test.ts` | **1 FAIL** (normalizeHeadingText regex) |
| Decision-application path | (missing) | **NO TEST EXISTS** |
| Publish-ready export CLI | (missing) | **NO SCRIPT EXISTS** |
| Scripture correctness (validator) | `tests/pipeline/test_full_run_assets.py` | PASS |
| Audit/provenance linkage | `tests/pipeline/` | PASS |
| Review UI workflow | Manual / `run_review_studio.py` | Functional within session |
| Series child-volume dedup | `tests/pipeline/test_run_devotional_full_helpers.py` | PASS (with venv) |

---

## Immutable Pass Criteria (all cycles)

1. No section hidden from the active review path can still block publish-ready export.
2. No validator bypass on scripture correctness.
3. Series child-volume non-dup constraints remain fail-closed.
4. Review UI local-time display behavior remains unchanged.
5. One reviewed competition-format run can deterministically produce the required publish-ready artifact set.

---

## Artifact Dependency Order

```
Cycle 1A (queue fix) → HUMAN CHECKPOINT → Cycle 1B (apply-decisions CLI)
                                         → Cycle 2 (regex fix) [independent, can parallel]
                                         → Cycle 3 (discipline) [after 1B + 2]
                                         → Section 3 Final Gate
```
