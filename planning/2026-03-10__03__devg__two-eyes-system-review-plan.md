# DevG Two-Eyes System Review Plan

Date: 2026-03-10
Scope: Section 1 planning only. No implementation performed.
Repo: `/Volumes/claude-projects/projects/devotional-generator-system-a`
Session: post-debate revision — approved debate transcript applied (debate_transcript_20260310_151015.json)

## Approved Debate Outcome

The debate converged AGREE/AGREE on splitting the original Cycle 1 into two gated substeps (1A and 1B) with a mandatory human checkpoint between them. The verifier required that Cycle 1A produce a concrete evidence artifact (changed test or code-level diff) before the checkpoint — not just a semantic decision statement.

## Verified Repo State

- Full pipeline entrypoint: `scripts/run_devotional_full.py`
- Review decision script: `scripts/review/run_pending_approvals.py`
- Review launchers: `scripts/review/run_review.py`, `run_review_studio.py`, `run_review_web.py`, `run_review_ui.py`
- Latest competition-format sampled run: `2026-03-09__195419__genesis-1-&-2__12-day__vol-2`
  - Present: `__book.json`, `__approval-gate-report.json`, `__agent-validation-report.json`, `__audit-linkage.json`, `__kdp-personal-preview.pdf`, `__meta.json`
  - Missing: `__approval-decisions.json`
  - Approval report: `pending_section_count = 61`, `blocked_reason = 72 section(s) pending approval`
  - `section_meta_by_key` = 72 entries; `section_previews_by_key` = 61 entries
  - Discrepancy: 11 sections with `verification_status = human_review_required` are in `section_meta_by_key` but absent from `section_previews_by_key` and the pending queue
- `.venv` pytest subset: `92 passed in 88.34s`
- `vitest run` in `ui/`: fails on `ui/pdf/__tests__/blocks.test.ts` — `normalizeHeadingText('timeless_wisdom')` returns `'timeless_wisdom'` instead of `'Timeless Wisdom'`
- `pytest tests/ -q` in ambient shell: fails collection — `scripts/run_devotional_full.py` executes `SystemExit` at import time when pydantic is not available

## Root Cause Summary (Fresh Clean-Room)

### SEV-1 Root Causes (Two Sub-Problems)

**Sub-problem A — Queue/export semantic mismatch:**

`build_pending_sections_and_previews()` in `src/api/full_run_assets.py` (line 205) excludes sections where `verification_status == "agent_validated"`. The sampled run shows a different exclusion at work: 11 sections with `verification_status = human_review_required` appear in `section_meta_by_key` but not in `section_previews_by_key`. This indicates a code-evolution discrepancy between the version that generated the current run and the current working copy (`M src/api/full_run_assets.py`).

Regardless of the exact exclusion mechanism, the functional result is proven: operators completing the visible review queue (61 sections) cannot satisfy the ExportGate, which requires all 72 present sections to have `approval_status == APPROVED`.

**Sub-problem B — No decision-application + publish-ready export path:**

`run_pending_approvals.py` creates `__approval-decisions.json` but performs no state mutation on the book. No script in the repo reads `__approval-decisions.json`, applies decisions to `__book.json` (updating `approval_status` per section), re-runs `ExportGate`, and produces a publish-ready PDF. This is the final gap between review completion and competition-ready submission.

### SEV-2 Root Cause

`ui/pdf/blocks.ts` line 59:
```typescript
const normalizedKey = trimmed.toLowerCase().replace(/[\\s-]+/g, '_');
```
In a TypeScript regex literal, `\\s` inside a character class `[...]` means: match literal `\` OR literal `s` OR literal `-`. It is NOT the whitespace character class. For input `timeless_wisdom`, the `ss` and the `s` in `wisdom` are both replaced with `_`, producing `timele__wi_dom`, which fails the `HUMAN_SECTION_HEADINGS` lookup and falls through to `return raw`. Reader-facing headings therefore expose internal section keys.

Fix: change `replace(/[\\s-]+/g, '_')` to `replace(/[\s-]+/g, '_')`.

### SEV-3 Root Cause

`scripts/run_devotional_full.py` lines 17–22: `raise SystemExit(...)` when pydantic import fails. `tests/pipeline/test_run_devotional_full_helpers.py` imports from this module at collection time. When pytest is invoked in the ambient shell (no `.venv`), collection fails with a `SystemExit`, not a collection error — producing misleading total test failure.

## Severity-Ranked Execution Order

1. SEV-1: Publish-ready path is functionally incomplete (queue/export mismatch + no decision application)
2. SEV-2: PDF heading normalization regex bug — reader-facing output corrupted
3. SEV-3: Documented test command is environment-fragile outside the project virtualenv

## E2E Test-And-Review Matrix

| Flow | Current Status | Verified Evidence | Gap to Close | Pass Criteria |
|---|---|---|---|---|
| Generation | Covered | `scripts/run_devotional_full.py`; `.venv` pytest passed; sampled run artifacts exist | Re-run after publish-ready path changes | Fresh run emits `__book.json`, preview PDF, agent validation, approval gate, audit linkage |
| Validation | Covered, fail-closed | `build_agent_validation_report()` aborts on discrepancy; sampled `overall_status = passed` | Re-verify on fresh run after SEV-1 fixes | Scripture mismatch still aborts; no validator bypass introduced |
| Review UI workflow | Partially covered | `tests/review/*` pass in `.venv`; decision script exists | Need live review completion path and parity with export gate | Review session writes `__approval-decisions.json`; all sections visible or explicitly exempted |
| PDF render path | Failing | `vitest` fails `blocks.test.ts` on `normalizeHeadingText` | Fix `blocks.ts` regex and rerun `vitest` | `vitest run` passes; internal keys do not appear in reader-facing PDF headings |
| Publish-ready gates | Unit-covered, live path blocked | `ExportGate` unit tests pass in `.venv`; sampled run blocked at 72 pending | Decision application + publish-ready export path | Reviewed devotional transitions to exportable state without bypassing gate rules |
| Audit / provenance | Artifact generation covered | Sampled `__audit-linkage.json` has 72 entries | Final E2E verify after review completion | Linkage artifact preserved; review and export artifacts remain cross-referenceable |

## Fix Cycles — Approved Three-Cycle Plan With 1A/1B Gate

### Cycle 1A: Align Approval Semantics

**Objective:** Resolve the queue/export semantic mismatch so that the contract for "review complete" is unambiguous and provably correct before the finalization path is built.

**Work:**
- Identify exact cause of the 72 vs 61 discrepancy between `section_meta_by_key` and `section_previews_by_key` in the current codebase
- Decide which path to implement:
  - Option (a): Expand the review queue to surface all export-blocking sections (including those currently excluded)
  - Option (b): Add an explicit, tested state-promotion path for excluded sections that preserves fail-closed behavior
- Implement the chosen path with targeted unit tests demonstrating queue/export parity

**Required evidence artifact before human checkpoint:**
- A concrete code-level diff (changed logic in `full_run_assets.py` or related) AND at least one new or modified test that proves the chosen semantic contract holds
- No implementation in Cycle 1B proceeds until this artifact exists and is approved

**Pass criteria for 1A:**
- `section_previews_by_key` count == `section_meta_by_key` count for a representative book (no hidden sections)
- OR an explicit, tested exemption path exists and fail-closed behavior is preserved for excluded sections
- New or modified tests pass in `.venv`

---

**[HUMAN CHECKPOINT — Required after Cycle 1A, before Cycle 1B]**

Human must review the Cycle 1A code diff and test evidence before proceeding. This checkpoint resolves which operator workflow is correct.

---

### Cycle 1B: Add Decision-Application and Publish-Ready Export Path

**Objective:** Add the missing operator path that applies `__approval-decisions.json` to the book, re-runs `ExportGate`, and produces a publish-ready PDF export artifact.

**Work:**
- Add a script (or integrate into existing pipeline) that:
  1. Reads `__approval-decisions.json`
  2. Loads `__book.json` as `DevotionalBook`
  3. Applies per-section `decision = "approved"` decisions (mutates `approval_status` in book)
  4. Re-runs `ExportGate.check_exportability()` in `PUBLISH_READY` mode
  5. If exportable: runs PDF export and writes a publish-ready artifact
  6. If not exportable: emits a clear, actionable blocked message
- Add targeted tests for decision application and publish-ready export

**Pass criteria for 1B:**
- No section excluded from the review queue can silently block publish-ready export
- A fresh, fully-reviewed devotional run can produce a publish-ready export artifact after valid approvals
- Volume 2 series constraints still fail closed on duplicate sections
- ExportGate still rejects partial approvals (fail-closed preserved)

### Cycle 2: PDF Reader-Facing Output

**Objective:** Restore reader-facing headings in PDF output.

**Work:**
- Fix `ui/pdf/blocks.ts` line 59: change `replace(/[\\s-]+/g, '_')` to `replace(/[\s-]+/g, '_')`
- Rerun `vitest run` in `ui/`
- Verify `normalizeHeadingText` for: `timeless_wisdom`, `action_steps`, `be_still`, `scripture`, `exposition`, `prayer`, `sending_prompt`, `day7`

**Pass criteria:**
- `vitest run` passes all tests
- Reader-facing headings do not expose internal section key strings

### Cycle 3: Execution Discipline Hardening

**Objective:** Make the documented test workflow reproducible by operators and CI.

**Work:**
- Either:
  - Remove or isolate the import-time `SystemExit` in `scripts/run_devotional_full.py` so it does not break pytest collection, OR
  - Update `tests/pipeline/test_run_devotional_full_helpers.py` import to avoid triggering the exit, OR
  - Update documented commands to be explicit and verified
- Verify the supported test command works as documented

**Pass criteria:**
- Documented test command works as written, or docs are corrected and verified
- No import-time `SystemExit` prevents normal test collection in the supported environment

## Human Checkpoints

1. **Required before Section 2 begins:**
   - Human approval of this plan and paired findings artifact
2. **Required after Cycle 1A:**
   - Human approves the semantic alignment diff and evidence tests before Cycle 1B proceeds
   - This is the decision point that determines the operator review workflow contract
3. **Required after first full reviewed devotional run (Section 3 gate):**
   - Human confirms review output, blocker accuracy, and operator UX before final competition-ready certification

## Section 2 Re-Review Protocol

- After each cycle:
  - Run targeted tests for changed surfaces
  - Run one relevant E2E scenario
  - Perform two-eyes re-review on affected artifacts
- If any scripture discrepancy appears:
  - Fail closed
  - Stop the cycle
  - Return with evidence

## Stop State For Section 1

Section 1 is complete when:
- This plan artifact exists
- The paired findings artifact exists
- Both are saved under `planning/` and `docs/system/outputs/`
- No implementation changes have been made
- Human approval is awaited before Section 2
