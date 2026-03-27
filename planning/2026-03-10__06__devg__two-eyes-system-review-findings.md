# DevG Two-Eyes System Review Findings

Date: 2026-03-10
Artifact: 2026-03-10__06__devg__two-eyes-system-review-findings.md
Scope: Clean-room Section 1 findings — fresh verification from repository source code in this session
Repo: `/Volumes/claude-projects/projects/devotional-generator-system-a`
Session: Post-debate-approval implementation session — debate_transcript_20260310_152343.json (AGREE/AGREE)

---

## Executive Finding

DevG is not yet competition-ready. The current repo does not prove a complete review-to-publish path on competition-format outputs. Two distinct SEV-1 problems are both open and verified in the current working copy:

- **(SEV-1A)** A mismatch between the sections visible in the review queue and the sections ExportGate requires to be approved before publish-ready export.
- **(SEV-1B)** No script exists to apply review decisions back to the book and produce a publish-ready export artifact.

Both must be resolved before the system can be certified competition-ready.

---

## Source Verification (This Session)

All findings below were verified by direct file reads in this session. Previous session findings are treated as non-authoritative and re-confirmed independently.

---

## Severity-Ranked Findings

### SEV-1A — Review Queue Excludes Sections That Block Publish-Ready Export

**Status: Open**

**Fresh verification:**

- `src/api/full_run_assets.py` line 205 (read this session):
  ```python
  if not include_agent_validated and verification_status == "agent_validated":
      continue
  ```
  This exclusion is applied when `include_agent_validated=False` (the default). Sections with `verification_status == "agent_validated"` are excluded from `pending`, `previews`, and `section_meta`.

- `src/api/export_gate.py` (read this session): Iterates `always_present` and `optional` sections unconditionally. No check of `verification_status`. Any section with `approval_status != SectionApprovalStatus.APPROVED` blocks PUBLISH_READY export.

- Prior sampled run `2026-03-09__195419__genesis-1-&-2__12-day__vol-2` (per prior session artifacts, confirmed as reference):
  - `section_meta_by_key` = 72 entries
  - `section_previews_by_key` = 61 entries
  - `blocked_reason = 72 section(s) pending approval`
  - 11 sections: `verification_status = human_review_required`, `approval_status = ""` — present in `section_meta_by_key`, absent from `section_previews_by_key`

- Note: `src/api/full_run_assets.py` is marked `M` in git status; the current codebase excludes `agent_validated` sections. The sampled run shows `human_review_required` exclusions, indicating the exclusion logic may have evolved since that run. The functional result is the same regardless: operators completing the visible queue cannot satisfy the ExportGate.

**Why this matters:**
- Operators completing the 61-section visible queue are still blocked from publish-ready export by 11 (or more) hidden sections.
- No operator-visible signal explains why approved sections still block export.
- The review workflow makes no distinction between "review complete" and "export unblocked".

**Required fix direction (one path must be chosen before Cycle 1B):**
- Option (a): Expand the review queue to surface all export-blocking sections.
- Option (b): Add an explicit, tested state-promotion path for excluded sections with fail-closed behavior preserved.

---

### SEV-1B — No Decision-Application or Publish-Ready Export Script Exists

**Status: Open**

**Fresh verification:**

- `scripts/review/` directory (listed this session): contains `run_pending_approvals.py`, `run_review_studio.py`, `run_review_ui.py`, `run_review_web.py`, `run_review.py`. No decision-application or finalization script.

- Grep for `apply.*decision|finalize.*book|PUBLISH_READY.*export|apply_decisions` in `scripts/` (this session): **no matches**.

- `scripts/run_pending_approvals.py` creates `__approval-decisions.json` from the approval gate report but performs no state mutation on the book.

- Prior session verification confirmed: no script reads `__approval-decisions.json`, loads `__book.json`, applies per-section decisions, re-runs ExportGate, and produces a publish-ready PDF. This is still true in the current working copy.

- Sampled competition-format run has no `__approval-decisions.json` and no `__kdp-publish-ready.pdf`.

**Why this matters:**
- The competition submission requires a publish-ready artifact.
- Even after fixing SEV-1A, there is no verified command path to produce that artifact from a completed review session.
- Section 3 cannot be certified until this path exists and is exercised.

**Required fix direction:**
- Add a script that: reads `__approval-decisions.json`, loads `__book.json`, applies per-section approval decisions, re-runs ExportGate in PUBLISH_READY mode, and exports a publish-ready PDF when unblocked.
- Add targeted tests for decision application and ExportGate pass after complete approvals.

---

### SEV-2 — PDF Heading Normalization Regex Corrupts Internal Section Keys

**Status: Open**

**Fresh verification:**

- `ui/pdf/blocks.ts` line 59 (read this session):
  ```typescript
  const normalizedKey = trimmed.toLowerCase().replace(/[\\s-]+/g, '_');
  ```
- In a TypeScript regex literal, `[\\s]` inside `[...]` matches literal `\` OR literal `s`. It is **not** the whitespace character class `[\s]`.
- Trace for `timeless_wisdom`:
  1. `.toLowerCase()` → `timeless_wisdom`
  2. `ss` at positions 6–7 replaced with `_`; `s` in `wisdom` replaced with `_`
  3. Result: `timele__wi_dom` — not in `HUMAN_SECTION_HEADINGS`
  4. Falls through → returns `'timeless_wisdom'` (raw)
- This affects any section key containing `s` or `-`.

**Why this matters:**
- Reader-facing PDF output exposes implementation identifiers instead of devotional labels for affected sections.
- Any heading block using an affected section key will render the raw key string to the printed page.

**Required fix:**
- Change `replace(/[\\s-]+/g, '_')` to `replace(/[\s-]+/g, '_')` at `blocks.ts:59`.
- Rerun `vitest run` and verify all `normalizeHeadingText` test cases pass.

---

### SEV-3 — Documented Test Execution Fails Outside Virtualenv

**Status: Open**

**Fresh verification:**

- `scripts/run_devotional_full.py` lines 16–22 (read this session):
  ```python
  try:
      import pydantic  # noqa: F401
  except ModuleNotFoundError as exc:
      raise SystemExit(
          "Missing runtime dependencies (pydantic not found). "
          "Use the project virtualenv, e.g. .venv/bin/python3."
      ) from exc
  ```
- `tests/pipeline/test_run_devotional_full_helpers.py` imports from `scripts.run_devotional_full`.
- When `pytest tests/` is invoked in the ambient shell (no `.venv`), collection reaches the `SystemExit` during module import and aborts — producing a false total failure.

**Required fix direction:**
- Remove or guard the import-time `SystemExit` so it does not break pytest collection, OR update documented commands to use `.venv/bin/pytest` and verify them explicitly.

---

## What Is Working

- Competition-outline CSV loading exists and is tested.
- Full-run artifact bundle generation exists and is exercised.
- Independent validator artifact generation exists; sampled run `overall_status = passed`, `discrepancies = 0`.
- Child-volume scripture/quote exclusion enforcement exists in the full-run path.
- Audit linkage artifact generation exists; sampled run has 72 linkage entries.
- Review decision script (`run_pending_approvals.py`) exists, is interactive, and produces a decisions artifact.
- Core review, export-gate, pipeline, and IRB test subset passed in `.venv` (92 passed in 88.34s).
- `SectionApprovalStatus`, `ExportGate`, and `PUBLISH_READY` mode are correctly modeled and unit-tested.

---

## Unproven or Incomplete Areas

- No verified live path from completed review decisions to publish-ready export artifact.
- No post-review E2E evidence for competition-format run artifacts.
- Latest competition-format sampled run has no `__approval-decisions.json`.
- Queue/export inclusion contract is inconsistent between `build_pending_sections_and_previews` and `ExportGate`.
- Final Section 3 fresh-run gate not yet exercised on a post-fix reviewed devotional.

---

## Evidence Snapshot

### Source files verified (fresh this session)

| File | Finding |
|---|---|
| `src/api/export_gate.py` | Checks ALL present sections; no `verification_status` exclusion — confirmed |
| `src/api/full_run_assets.py:205` | Excludes `agent_validated` sections by default — confirmed |
| `scripts/review/` listing | No decision-application or finalization script present — confirmed |
| Grep `apply.*decision` in `scripts/` | No matches — confirmed |
| `ui/pdf/blocks.ts:59` | `replace(/[\\s-]+/g, '_')` — regex bug confirmed |
| `scripts/run_devotional_full.py:16-22` | `raise SystemExit(...)` on pydantic import — confirmed |

### Sampled run reference (from prior session, confirmed as consistent)

Run slug: `2026-03-09__195419__genesis-1-&-2__12-day__vol-2`

| Artifact | Present | Notes |
|---|---|---|
| `__book.json` | Yes | |
| `__approval-gate-report.json` | Yes | `pending_section_count=61`; `blocked_reason: 72 sections` |
| `__agent-validation-report.json` | Yes | `overall_status=passed`, `discrepancies=0` |
| `__audit-linkage.json` | Yes | 72 entries |
| `__kdp-personal-preview.pdf` | Yes | Personal mode only |
| `__approval-decisions.json` | **No** | Not generated for this run |
| `__kdp-publish-ready.pdf` | **No** | Publish-ready path not available |

---

## Recommended Section 2 Order

1. **Cycle 1A:** Fix queue/export semantic mismatch — produce code diff + test evidence
2. **[HUMAN CHECKPOINT]** — approve Cycle 1A evidence before Cycle 1B
3. **Cycle 1B:** Add decision-application and publish-ready export path
4. **Cycle 2:** Fix PDF heading normalization regex
5. **Cycle 3:** Harden documented test execution

---

## Required Human Re-Review Points

1. Approve Section 1 artifacts (this artifact + paired plan) before any implementation.
2. Approve Cycle 1A semantic alignment evidence (code diff + test) before Cycle 1B builds on it.
3. Approve the first complete post-fix review/export evidence set before competition submission use.
