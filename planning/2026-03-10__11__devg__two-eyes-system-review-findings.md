# Two-Eyes System Review — Competition Readiness Findings (Cycle 1B Scope)
**Date:** 2026-03-10
**Artifact:** `2026-03-10__11__devg__two-eyes-system-review-findings.md`
**Session:** Section 1 — Planning Only (no code edits)
**Branch:** feat/phase-014-rag-infrastructure

---

## Executive Summary

Cycle 1A is confirmed deployed. ISSUE-1 (agent_validated sections invisible to operator) is
resolved. 823 Python tests pass. One TypeScript test fails. Two issues remain open before the
system is competition-certified:

- **ISSUE-2** (HIGH — blocks competition submission): No CLI path from approval decisions to
  publish-ready PDF. No `export_approved_devotional.py` script exists.
- **ISSUE-3** (MEDIUM — breaks PDF heading label normalization): `blocks.ts:59` regex
  `[\\s-]+` corrupts lookup keys; 1 vitest test fails.

No scripture correctness, series de-dup, or audit invariant has been compromised.

---

## Test Suite Baseline (Code-Verified 2026-03-10)

### Python Tests
```
.venv/bin/python -m pytest --tb=short -q
823 passed in 188.89s (0:03:08)
```
**Result: 823/823 PASS**

Notable coverage areas confirmed passing:
- `tests/pipeline/test_full_run_assets.py` — 11 tests including
  `test_build_approval_gate_report_surfaces_agent_validated_sections` (Cycle 1A regression test)
- `tests/pipeline/test_export_gate.py` — PERSONAL and PUBLISH_READY export gate
- `tests/review/test_approval_contract_parity.py` — Approval enum/state machine
- `tests/generation/` — Generation pipeline
- `tests/persistence/` — SQLite socket factory
- `tests/pipeline/test_run_devotional_full_helpers.py` — Series dedup helpers

### TypeScript Tests
```
npx vitest run ui/pdf/__tests__/blocks.test.ts
Test Files:  1 failed (1)
Tests:       1 failed | 25 passed (26)
```
**Result: 25/26 PASS — 1 FAIL**

Failing test: `normalizeHeadingText > maps internal section keys to reader-facing labels`
```
AssertionError: expected 'Timeless Wisdom' to be 'Timeless Wisdom'
Expected: "Timeless Wisdom"
Received: "timeless_wisdom"
```
Root cause: `blocks.ts:59` — `[\\s-]+` is a broken regex character class (see ISSUE-3 below).

---

## Issue Register (Severity-Ranked)

### ISSUE-1 — Review/Export Semantic Mismatch
**Severity:** HIGH — WAS BLOCKING
**Status:** RESOLVED in Cycle 1A
**Fix location:** `src/api/full_run_assets.py:530`
**Code evidence:**
```python
# CONFIRMED PRESENT:
pending_sections, previews, section_meta = build_pending_sections_and_previews(
    book, include_agent_validated=True
)
```
**Regression test:** `test_build_approval_gate_report_surfaces_agent_validated_sections` — PASS
**Assessment:** Issue closed. No further action needed.

---

### ISSUE-2 — No Decision-Application + Publish-Ready Export CLI
**Severity:** HIGH — Competition blocker. No executable path from decisions.json to publish-ready PDF.
**Status:** CONFIRMED OPEN

**Code evidence — what exists:**

`scripts/` directory listing (code-verified):
```
__init__.py
irb/
rag/
review/
run_devotional_full.py
```
No `export_approved_devotional.py`. No equivalent in `scripts/review/`.

`scripts/review/run_pending_approvals.py` — writes `__approval-decisions.json` but
does NOT apply approval_status mutations to any book model (confirmed reading lines 176–205):
```python
payload = {
    "source_report": ..., "topic": ..., "decisions": decisions
}
_atomic_write_json(output_path, payload)
# No book load. No book mutation. No ExportGate call.
```

`scripts/run_devotional_full.py:664` — generates PERSONAL mode only:
```python
result = generate_devotional(
    ...
    output_mode=OutputMode.PERSONAL,
    ...
)
```
No PUBLISH_READY generation step follows. Meta JSON does not include `publish_ready_pdf_path`.

**Consequence:** Operator completes review in Studio, approval decisions are saved, but no
command exists to apply those decisions to the book model and emit the publish-ready PDF.

**Fix plan:** See `2026-03-10__10__devg__two-eyes-system-review-plan.md` Cycle 1B section.
Core: create `scripts/export_approved_devotional.py` that applies decisions, runs ExportGate,
and emits the publish-ready PDF (or exits 1 with blocked_reason).

---

### ISSUE-3 — PDF Heading Normalization Regex Regression
**Severity:** MEDIUM — Confirmed failing test. Reader-facing impact when internal keys reach
`normalizeHeadingText`.
**Status:** CONFIRMED OPEN

**Code evidence:**
```typescript
// ui/pdf/blocks.ts:59
const normalizedKey = trimmed.toLowerCase().replace(/[\\s-]+/g, '_');
```

In a TypeScript/JavaScript regex literal, `\\s` inside `[...]` is NOT `\s` whitespace.
`\\s` is an escaped backslash followed by literal `s` — the character class matches `\` and `s`.
Every `s` in a key like `timeless_wisdom` is replaced by `_`, corrupting the lookup.

**Trace for `normalizeHeadingText('timeless_wisdom')`:**
1. `trimmed = 'timeless_wisdom'`
2. `/[\\s-]+/g` matches every `s` → replaces with `_`
3. Result: `'timele__wi_dom'` → `HUMAN_SECTION_HEADINGS['timele__wi_dom']` is `undefined`
4. Falls through to raw title-case → returns `'timeless_wisdom'` (not `'Timeless Wisdom'`)

**Confirmed failing assertion (vitest output):**
```
AssertionError: expected 'timeless_wisdom' to be 'Timeless Wisdom'
Expected: "Timeless Wisdom"
Received: "timeless_wisdom"
```

**Fix:** `[\\s-]+` → `[\s_-]+`
- `\s` (single backslash) correctly matches whitespace in the character class
- Adding `_` handles the underscore-delimited internal key contract

**Practical impact today:** Python `sections.py` already emits reader-facing labels
(e.g., `"Timeless Wisdom"` not `"timeless_wisdom"`). Broken normalization fires only when
internal keys reach this function — which is the documented API contract and verified by test.

---

### ISSUE-4 — Ambient pytest Invocation (System Python)
**Severity:** OPERATIONAL — Not a competition blocker.
**Status:** PERSISTENT

**Evidence:**
```
$ python3 -m pytest tests/ -q
INTERNALERROR> SystemExit: Missing runtime dependencies (pydantic not found).
```
Must use: `.venv/bin/python -m pytest`

**Assessment:** Convention-only. No code change required.

---

## E2E Test-and-Review Matrix (Post-Cycle-1A State)

| Surface | Files | Current Status | Issue |
|---------|-------|----------------|-------|
| Generation pipeline | `tests/generation/` | PASS (823/823) | — |
| Section validation | `tests/generation/test_deterministic_real_section_generator.py` | PASS | — |
| Export gate — PERSONAL | `tests/pipeline/test_export_gate.py` | PASS | — |
| Export gate — PUBLISH_READY | `tests/pipeline/test_export_gate.py` | PASS | — |
| Approval gate report | `tests/pipeline/test_full_run_assets.py` | **PASS** | ISSUE-1 RESOLVED |
| Decision application to book | (missing) | **NO SCRIPT / NO TEST** | ISSUE-2 |
| Publish-ready export gate | (missing) | **NO SCRIPT / NO TEST** | ISSUE-2 |
| Publish-ready PDF path | (missing) | **NEVER GENERATED** | ISSUE-2 |
| PDF heading normalization | `ui/pdf/__tests__/blocks.test.ts` | **1 FAIL** | ISSUE-3 |
| Audit/provenance | `tests/pipeline/` | PASS | — |
| Review workflow (decisions.json) | `tests/review/` | PASS | ISSUE-2 downstream |
| Scripture correctness (fail-closed) | `tests/pipeline/test_full_run_assets.py` | PASS | — |
| Series child-volume dedup | `tests/pipeline/test_run_devotional_full_helpers.py` | PASS | — |
| Registry persistence | `tests/persistence/` | PASS | — |
| Approval contract parity | `tests/review/test_approval_contract_parity.py` | PASS | — |

---

## Invariant Verification (Code-Verified)

### 1. Scripture Correctness — Fail-Closed (INTACT)
`_fail_closed_quality_checks` (run_devotional_full.py:399):
- Checks: non-empty scripture text, no placeholders, regex `\d+:\d+` (verse precision),
  retrieval_source present
- Blocks with `SystemExit` on any failure
- Not modified by Cycle 1A. Not planned for modification in 1B/1C.

### 2. Series Child-Volume Non-Dup (INTACT)
`_enforce_child_week_scripture_exclusions` and `_enforce_child_week_quote_exclusions`
(run_devotional_full.py:273–325):
- Scripture and quote reuse across parent-child volumes raises `SystemExit`
- Not modified by Cycle 1A. Not planned for modification in 1B/1C.

### 3. Day 1 Human-Review Requirement (INTACT)
`_mark_agent_validated_sections` (run_devotional_full.py:341):
- Explicitly skips day 1: `if idx == 0: continue`
- Day 1 sections always remain `approval_status = PENDING`
- Must also be preserved in Cycle 1B: apply-decisions must not special-case day 1.

### 4. ExportGate — Never Mutates (INTACT)
`ExportGate.check_exportability` reads only, never writes.
- Cycle 1B plan: book mutation occurs before ExportGate call — consistent with invariant.

### 5. Agent Decision-Source Policy (INTACT)
`_ensure_decision_source_policy` in run_pending_approvals.py:
- Agent reviewers require `decision_source` (non-empty string)
- Must be inherited by Cycle 1B export script when loading and validating decisions.

### 6. Review UI Local-Time Display (INTACT)
No planned change in Cycle 1B or 1C affects review studio timestamp display.

---

## Competition Readiness Summary

| Requirement | Status | Blocker |
|-------------|--------|---------|
| Generation produces valid book JSON | READY | — |
| Agent validation report generated | READY | — |
| Approval gate report shows all pending (incl. agent_validated) | **READY** | ISSUE-1 RESOLVED |
| Human review workflow (review studio) | FUNCTIONAL | ISSUE-2 downstream |
| Approval decisions applied to book model | **BLOCKED** | ISSUE-2 |
| Publish-ready export gate (all sections approved) | **BLOCKED** | ISSUE-2 |
| Publish-ready PDF artifact | **BLOCKED** | ISSUE-2 |
| Audit linkage artifact | READY | — |
| PDF heading label normalization | PARTIAL | ISSUE-3 |
| Test suite executable (venv) | READY | — |

**Certification status: NOT READY**
**Blockers:** ISSUE-2 (competition-blocking), ISSUE-3 (required for full certification)

**Path to certification:**
1. Cycle 1B → resolves ISSUE-2 → publish-ready PDF path unlocked
2. Cycle 1C → resolves ISSUE-3 → 26/26 TypeScript tests pass
3. Section 3 → final test devotional gate → CERTIFIED
