# DevG Two-Eyes System Review Findings

Date: 2026-03-10
Scope: clean-room Section 1 findings — fresh verification from repository artifacts, source code, and live run outputs
Repo: `/Volumes/claude-projects/projects/devotional-generator-system-a`
Session: post-debate revision — approved debate transcript applied (debate_transcript_20260310_151015.json)

## Executive Finding

DevG is not yet competition-ready for execution because the current repo does not prove a complete review-to-publish path on competition-format outputs. The primary blocker is a two-part failure in the publish-ready gate: (A) a mismatch between the sections visible in the review queue and the sections that must be approved before publish-ready export, and (B) the absence of a script that applies review decisions back to the book and produces a publish-ready artifact. These are distinct problems that must both be resolved.

## Severity-Ranked Findings

### SEV-1A: Review queue excludes sections that block publish-ready export

Status: Open

Verified evidence:

- Sampled run: `2026-03-09__195419__genesis-1-&-2__12-day__vol-2`
- `__approval-gate-report.json` shows:
  - `pending_section_count = 61` (sections shown in review queue)
  - `blocked_reason = 72 section(s) pending approval` (sections blocking ExportGate)
  - `section_meta_by_key` = 72 entries (total book sections visible to the report builder)
  - `section_previews_by_key` = 61 entries (sections with content previews for reviewers)
  - Discrepancy = 11 sections: `verification_status = human_review_required`, `approval_status = ''` (empty)
- `src/api/full_run_assets.py` `build_pending_sections_and_previews()` at line 205 excludes sections where `verification_status == "agent_validated"` (with `include_agent_validated=False` default)
- `src/api/export_gate.py` `ExportGate.check_exportability()` requires ALL present book sections to have `approval_status == APPROVED` for PUBLISH_READY mode — with no exclusion for validation status
- `src/api/full_run_assets.py` is marked modified in git status (`M`) — the current working copy may differ from the version that generated the sampled run; the discrepancy between section counts in the report is consistent with code evolution

Why this matters:

- Operators completing the 61-section visible review queue will still be blocked from publish-ready export by the 11 excluded sections
- The review workflow makes no distinction between "review complete" and "export unblocked"
- There is no operator-visible signal explaining why approved sections still block export

Required fix direction (two candidate paths — one must be chosen before Cycle 1B):

- Option (a): Expand the review queue to surface all export-blocking sections (include sections currently excluded from the visible queue)
- Option (b): Add an explicit, tested state-promotion path for excluded sections, preserving fail-closed behavior for sections that legitimately should not require human review

### SEV-1B: No decision-application or publish-ready export script exists

Status: Open

Verified evidence:

- `scripts/review/run_pending_approvals.py` exists and creates `__approval-decisions.json` from the approval gate report
- `grep -rn "apply.*decision|finalize.*book|PUBLISH_READY" scripts/ src/ --include="*.py"` returns: no matching script for decision application or finalization
- No script in the repo: (1) reads `__approval-decisions.json`, (2) loads `__book.json`, (3) applies per-section approval decisions to book state, (4) re-runs ExportGate, (5) triggers publish-ready PDF export
- Latest sampled competition-format run has no `__approval-decisions.json`
- Older vol-1 runs (`2026-03-09__063054`, `2026-03-09__172153`) have `__approval-decisions.json` but no corresponding `__kdp-publish-ready.pdf`
- Only the pre-phase-014 run `2026-03-07__175805` has a `__kdp-publish-ready.pdf`, indicating the path existed earlier but is not present in the current competition-format workflow

Why this matters:

- The competition submission requires a publish-ready artifact
- Even if the review queue semantics are fixed (SEV-1A), there is no verified command path to produce that artifact from a completed review session
- Section 3 cannot be certified until this path exists and is exercised on a competition-format run

Required fix direction:

- Add or restore a script that applies `__approval-decisions.json` to `__book.json`, re-evaluates ExportGate, and exports a publish-ready PDF when unblocked
- Add targeted tests for: decision application to book state, ExportGate pass after complete approvals, publish-ready artifact emission

### SEV-2: PDF heading normalization regex corrupts internal section keys

Status: Open

Verified evidence:

- `ui/pdf/blocks.ts` line 59:
  ```typescript
  const normalizedKey = trimmed.toLowerCase().replace(/[\\s-]+/g, '_');
  ```
- In a TypeScript regex literal, `[\\s]` means: literal `\` OR literal `s`. It is NOT the whitespace class.
- Trace for input `timeless_wisdom`:
  1. `.toLowerCase()` → `timeless_wisdom`
  2. `.replace(/[\\s-]+/g, '_')` replaces each `s` (and consecutive runs of `\`, `s`, `-`) with `_`
  3. `ss` at positions 6–7 → `_`; `s` at position 11 (in `wisdom`) → `_`
  4. Result: `timele__wi_dom` — NOT in `HUMAN_SECTION_HEADINGS`
  5. Falls through to `return raw` → returns `'timeless_wisdom'`
- `ui/pdf/__tests__/blocks.test.ts` line 100: `expect(normalizeHeadingText('timeless_wisdom')).toBe('Timeless Wisdom')` — FAILS
- Also fails for: `action_steps` → `action_step_` (not in map), `be_still` → correct (no `s` issue in `be_still`... wait: `b,e,_,s,t,i,l,l` — `s` → `_` → `be__till` — fails)

Why this matters:

- Reader-facing PDF output exposes implementation identifiers instead of devotional labels for every affected section
- Any heading block using a section key will render the raw key string to the printed page

Required fix direction:

- Change `replace(/[\\s-]+/g, '_')` to `replace(/[\s-]+/g, '_')` in `blocks.ts` line 59
- Rerun `vitest run` and verify all `normalizeHeadingText` test cases pass

### SEV-3: Documented test execution fails outside virtualenv

Status: Open

Verified evidence:

- `README.md` instructs `pytest tests/`
- `tests/pipeline/test_run_devotional_full_helpers.py` line 3: `from scripts.run_devotional_full import ...`
- `scripts/run_devotional_full.py` lines 17–22: `raise SystemExit(...)` if `pydantic` not found at import time
- Ambient-shell `pytest tests/ -q` fails during collection with `SystemExit`, not a collection error
- `.venv/bin/pytest` (targeted subset): `92 passed in 88.34s`

Why this matters:

- Operators or CI using the documented command from the wrong interpreter get a `SystemExit` before any test runs
- Lower severity than the publish-ready path blocker, but degrades reproducibility and can mask real failures

Required fix direction:

- Remove or guard the import-time `SystemExit` so collection does not abort, OR update documented commands and verify them explicitly

## What Is Working

- Competition-outline CSV loading exists and is tested
- Full-run artifact bundle generation exists and is exercised
- Independent validator artifact generation exists; sampled run `overall_status = passed`, `discrepancies = 0`
- Child-volume scripture/quote exclusion enforcement exists in the full-run path
- Audit linkage artifact generation exists; sampled latest vol-2 run contains 72 linkage entries
- Review decision script (`run_pending_approvals.py`) exists, is interactive, and produces a decisions artifact
- Core review, export-gate, pipeline, and IRB test subset passed in `.venv`
- SectionApprovalStatus, ExportGate, and PUBLISH_READY mode are correctly modeled and unit-tested

## Unproven or Incomplete Areas

- No verified live path from completed review decisions to publish-ready export artifact
- No post-review E2E evidence for competition-format run artifacts
- Latest competition-format sampled run still lacks `__approval-decisions.json`
- The exact inclusion/exclusion contract between `build_pending_sections_and_previews` and `ExportGate` is not consistent in the current codebase
- Final Section 3 fresh-run gate has not been exercised on a post-fix reviewed devotional

## Evidence Snapshot

### Source files verified (fresh)

| File | Finding |
|---|---|
| `src/api/export_gate.py` | Checks ALL present sections; no verification_status exclusion |
| `src/api/full_run_assets.py` | `build_pending_sections_and_previews()` excludes `agent_validated` by default; `build_approval_gate_report()` uses default (excludes) |
| `scripts/review/run_pending_approvals.py` | Creates decisions file from visible queue only; no book state mutation |
| `ui/pdf/blocks.ts:59` | `replace(/[\\s-]+/g, '_')` — regex corrupts keys with `s` or `-` |
| `scripts/run_devotional_full.py:17-22` | `raise SystemExit(...)` on pydantic import failure — breaks test collection |

### Sampled run artifacts (fresh)

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

### section_meta_by_key distribution in sampled approval gate report

| Field | Value | Count |
|---|---|---|
| `approval_status` | `SectionApprovalStatus.PENDING` | 61 |
| `approval_status` | `` (empty) | 11 |
| `verification_status` | `` (empty) | 59 |
| `verification_status` | `human_review_required` | 11 |
| `verification_status` | `catalog_verified` | 1 |
| `verification_status` | `verified` | 1 |

### Commands and observed outcomes

| Command | Outcome |
|---|---|
| `.venv/bin/pytest tests/review tests/pipeline/test_full_run_assets.py tests/pipeline/test_export_gate.py tests/integration/test_pipeline.py tests/irb/test_tier3_runner.py -q` | 92 passed in 88.34s |
| `pytest tests/ -q` (ambient shell) | FAILED at collection — `SystemExit` from `scripts/run_devotional_full.py` |
| `cd ui && node_modules/.bin/vitest run` | FAILED — `blocks.test.ts` `normalizeHeadingText` assertion |

## Recommended Section 2 Order (Incorporating Debate Outcome)

1. Cycle 1A: fix queue/export semantic mismatch (produce concrete code diff + test evidence)
2. **Human checkpoint** — approve Cycle 1A evidence before Cycle 1B
3. Cycle 1B: add decision-application and publish-ready export path
4. Cycle 2: fix PDF heading normalization regex
5. Cycle 3: harden documented test execution

## Required Human Re-Review Points

1. Approve Section 1 artifacts before any implementation
2. Approve the Cycle 1A semantic alignment evidence (code diff + test) before Cycle 1B builds on it
3. Approve the first complete post-fix review/export evidence set before competition submission use
