# Two-Eyes System Review — Competition Readiness Findings
**Date:** 2026-03-10
**Artifact:** `2026-03-10__08__devg__two-eyes-system-review-findings.md`
**Session:** Section 1 — Planning Only (no code edits)
**Branch:** feat/phase-014-rag-infrastructure

---

## Executive Summary

Three code-verified issues block a certified competition run. Two are HIGH severity — they prevent the operator from ever completing the review-to-publish path. One is MEDIUM severity — a reader-facing PDF regression with a confirmed failing test. One is OPERATIONAL — ambient pytest invocation fails with system Python. No issue requires a design reversal; all are targeted one-to-three line fixes.

---

## Issue Register (severity-ranked)

### ISSUE-1 — Review/Export Semantic Mismatch
**Severity:** HIGH — Blocks publish-ready export even after successful human review
**Status:** Confirmed in code
**Files:** `src/api/full_run_assets.py:529`, `src/api/export_gate.py:55`

**Evidence:**

`build_approval_gate_report` calls `build_pending_sections_and_previews(book)` with default `include_agent_validated=False`. Sections with `verification_status == "agent_validated"` are silently excluded from the pending queue. `ExportGate.check_exportability` independently checks `approval_status != APPROVED` for all sections — it sees these sections and blocks export.

An operator drains all visible pending items. Export gate fires: `N sections pending approval`. No actionable path forward.

**Fix path (Cycle 1A):** Pass `include_agent_validated=True` in `build_approval_gate_report`.

---

### ISSUE-2 — Missing Decision-Application + Publish-Ready Export CLI
**Severity:** HIGH — No executable path from decisions to publish-ready PDF
**Status:** Confirmed — no such script exists
**Files:** `scripts/run_pending_approvals.py`, `scripts/review/run_review_studio.py`, `scripts/run_devotional_full.py`

**Evidence:** `run_pending_approvals.py` writes `__approval-decisions.json` but does not apply `approval_status` changes to `__book.json`. `run_review_studio.py` applies edits within the web UI session only. `run_devotional_full.py` emits `PERSONAL` mode only.

**Fix path (Cycle 1B):** New `scripts/apply_decisions_and_export.py` that reads decisions, applies approval_status changes, re-runs ExportGate, and emits publish-ready PDF.

---

### ISSUE-3 — PDF Heading Normalization Regex Regression
**Severity:** MEDIUM — Confirmed failing vitest test; broken normalization fallback
**Status:** Confirmed — test fails
**Files:** `ui/pdf/blocks.ts:59`, `ui/pdf/__tests__/blocks.test.ts:100`

**Evidence:** `/[\\s-]+/g` — `\\s` in JS regex character class is literal `\` + `s`, not whitespace. `s` characters in keys are replaced by `_`, corrupting lookup. `normalizeHeadingText('timeless_wisdom')` returns `'timeless_wisdom'` not `'Timeless Wisdom'`.

**Fix path (Cycle 2):** Change `/[\\s-]+/g` to `/[\s_-]+/g`.

---

### ISSUE-4 — Ambient Pytest Invocation Fails
**Severity:** OPERATIONAL
**Status:** Confirmed
**Files:** `tests/pipeline/test_run_devotional_full_helpers.py:3`

System Python lacks pydantic → `INTERNALERROR` on import. Must use `.venv/bin/python3 -m pytest`. 83 tests pass with venv.

**Fix path (Cycle 3):** Add Makefile target or run_tests.sh using `.venv/bin/python3`.

---

## Competition Readiness: NOT READY

Blockers: ISSUE-1 + ISSUE-2. ISSUE-3 and ISSUE-4 required for full certification.
