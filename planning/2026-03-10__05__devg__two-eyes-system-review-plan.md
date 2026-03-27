# DevG Two-Eyes System Review Plan

Date: 2026-03-10
Artifact: 2026-03-10__05__devg__two-eyes-system-review-plan.md
Scope: Section 1 planning only. No implementation performed.
Repo: `/Volumes/claude-projects/projects/devotional-generator-system-a`
Session: Post-debate-approval implementation session — debate_transcript_20260310_152343.json (AGREE/AGREE)

---

## Approved Debate Outcome

The debate converged AGREE/AGREE on splitting Cycle 1 into two gated substeps (1A and 1B) with a mandatory human checkpoint between them. The verifier required that Cycle 1A produce concrete code-level evidence (diff + at least one new or modified test) before the checkpoint — not just a semantic decision statement.

The debate references and confirms the findings first documented in:
- `2026-03-10__03__devg__two-eyes-system-review-plan.md`
- `2026-03-10__04__devg__two-eyes-system-review-findings.md`

These findings were re-verified fresh in this session (see paired findings artifact `2026-03-10__06__devg__two-eyes-system-review-findings.md`).

---

## Fresh Clean-Room Verification Summary

The following source files were read directly in this session:

| File | Status |
|---|---|
| `src/api/full_run_assets.py` lines 195–220 | Confirmed: `agent_validated` exclusion at line 205 |
| `src/api/export_gate.py` | Confirmed: ALL sections checked, no `verification_status` exclusion |
| `ui/pdf/blocks.ts` lines 50–64 | Confirmed: `replace(/[\\s-]+/g, '_')` regex bug at line 59 |
| `scripts/run_devotional_full.py` lines 16–22 | Confirmed: `raise SystemExit(...)` on pydantic import failure |
| `scripts/review/` directory listing | Confirmed: no decision-application script exists |
| Grep for `apply.*decision\|finalize.*book\|PUBLISH_READY.*export` in `scripts/` | Confirmed: no matches |

All four severity findings from the prior review are still open and verified in current working copy.

---

## Severity-Ranked Execution Order

1. **SEV-1A** — Review queue excludes sections that block publish-ready export (queue/export semantic mismatch)
2. **SEV-1B** — No decision-application or publish-ready export script exists
3. **SEV-2** — PDF heading normalization regex corrupts internal section keys in reader-facing output
4. **SEV-3** — Documented test execution (`pytest tests/`) fails outside virtualenv due to `SystemExit` at collection

---

## E2E Test-And-Review Matrix

| Flow | Current Status | Verified Evidence | Gap to Close | Pass Criteria |
|---|---|---|---|---|
| Generation | Covered | `run_devotional_full.py`; sampled run artifacts exist; `.venv` pytest 92 passed | Re-run after SEV-1 fixes | Fresh run emits `__book.json`, preview PDF, validation, approval gate, audit linkage |
| Agent validation | Covered, fail-closed | `build_agent_validation_report()`; sampled `overall_status=passed`, `discrepancies=0` | Re-verify on fresh post-fix run | Scripture mismatch still aborts; no validator bypass introduced |
| Review UI workflow | Partially covered | `tests/review/*` pass in `.venv`; decision script exists but does not mutate book | Need live review → publish path | All export-blocking sections visible in review queue; decisions artifact drives book mutation |
| PDF render path | Failing | `vitest run` fails `normalizeHeadingText('timeless_wisdom')` | Fix `blocks.ts:59` regex; rerun `vitest` | `vitest run` passes; reader-facing headings do not expose internal keys |
| Publish-ready gates | Unit-covered, live path blocked | `ExportGate` unit tests pass; sampled run: 61 visible, 72 blocking | Decision application + publish-ready export path | Reviewed devotional transitions to exportable state; gate remains fail-closed |
| Audit / provenance | Artifact generation covered | Sampled `__audit-linkage.json`: 72 entries | Final E2E verify after review completion | Linkage preserved; review and export artifacts remain cross-referenceable |

---

## Fix Cycles — Approved Three-Cycle Plan With 1A/1B Gate

### Cycle 1A: Align Approval Queue Semantics

**Objective:** Make explicit which sections are shown in the review queue and which are required by ExportGate, so the operator workflow is unambiguous and testable.

**Root cause confirmed this session:**
- `build_pending_sections_and_previews()` at `src/api/full_run_assets.py:205` excludes sections where `verification_status == "agent_validated"` when `include_agent_validated=False` (default).
- `ExportGate.check_exportability()` checks ALL present sections regardless of `verification_status`.
- The sampled run shows 11 sections with non-empty `approval_status = ""` that are in `section_meta_by_key` but absent from `section_previews_by_key`. These 11 sections make the ExportGate count 72 while the visible queue shows 61.

**Work:**
- Identify whether the 11 excluded sections in the sampled run have `verification_status == "agent_validated"` or something else (the current code excludes `agent_validated`; the sampled run shows `human_review_required` exclusions — this discrepancy may reflect code evolution since the run was generated).
- Choose and implement ONE of:
  - **Option (a):** Expand the review queue to surface all export-blocking sections (include sections currently excluded from the visible queue).
  - **Option (b):** Add an explicit, tested state-promotion path for excluded sections with fail-closed behavior preserved.
- Implement the chosen path with at minimum one new or modified unit test proving the contract.

**Required evidence before human checkpoint:**
- A concrete code diff in `full_run_assets.py` or related module
- At least one new or modified test demonstrating the chosen semantic contract
- Test must pass in `.venv`

**Pass criteria:**
- `section_previews_by_key` count == `section_meta_by_key` count for a representative book, OR explicit tested exemption with fail-closed guarantee
- New or modified tests pass in `.venv`

---

**[HUMAN CHECKPOINT — Required after Cycle 1A, before Cycle 1B]**

Human must review the Cycle 1A code diff and test evidence before Cycle 1B proceeds.

---

### Cycle 1B: Add Decision-Application and Publish-Ready Export Path

**Objective:** Add the missing operator path that applies `__approval-decisions.json` to the book, re-runs ExportGate, and produces a publish-ready PDF.

**Work:**
- Add a script or integrate into existing pipeline:
  1. Reads `__approval-decisions.json`
  2. Loads `__book.json` as `DevotionalBook`
  3. Applies per-section `decision == "approved"` decisions (updates `approval_status` in book)
  4. Re-runs `ExportGate.check_exportability()` in `PUBLISH_READY` mode
  5. If exportable: runs PDF export and writes publish-ready artifact
  6. If not exportable: emits clear actionable blocked message
- Add targeted tests for: decision application to book state, ExportGate pass after complete approvals, publish-ready artifact emission

**Pass criteria:**
- No section excluded from the review queue can silently block publish-ready export
- A fully-reviewed competition-format run can produce a publish-ready export artifact
- Series child-volume non-dup constraints still fail closed
- ExportGate still rejects partial approvals (fail-closed preserved)

---

### Cycle 2: PDF Reader-Facing Output

**Objective:** Restore correct reader-facing headings in PDF output.

**Work:**
- Fix `ui/pdf/blocks.ts:59`: change `replace(/[\\s-]+/g, '_')` to `replace(/[\s-]+/g, '_')`
- Rerun `vitest run` in `ui/`
- Verify `normalizeHeadingText` for: `timeless_wisdom`, `action_steps`, `be_still`, `scripture`, `exposition`, `prayer`, `sending_prompt`, `day7`

**Pass criteria:**
- `vitest run` passes all tests
- Reader-facing headings do not expose internal section key strings

---

### Cycle 3: Execution Discipline Hardening

**Objective:** Make the documented test command reproducible by operators and CI.

**Work:**
- Remove or guard the import-time `SystemExit` in `scripts/run_devotional_full.py` so it does not abort pytest collection, OR update documented commands and verify them explicitly
- Verify the supported test command works as documented

**Pass criteria:**
- Documented test command works as written, or docs are corrected and verified
- No import-time `SystemExit` prevents normal test collection in the supported environment

---

## Full-Plan Pass Criteria

- No hidden section state can block publish-ready export
- Independent validator logic remains authoritative (fail-closed on scripture discrepancy)
- Scripture correctness still fails closed
- Series child-volume non-dup constraints still fail closed
- Review UI local-time behavior is unchanged
- Final evidence includes one fresh end-to-end run with `__book.json`, `__approval-gate-report.json`, `__agent-validation-report.json`, `__audit-linkage.json`, and preview PDF present

---

## Human Checkpoints

1. **Required before Section 2 begins:** Human approval of this plan and paired findings artifact (2026-03-10__06)
2. **Required after Cycle 1A:** Human approves the semantic alignment diff and evidence test before Cycle 1B proceeds
3. **Required after Section 3 gate:** Human confirms review output, blocker accuracy, and operator UX before final competition-ready certification

---

## Section 2 Re-Review Protocol

After each cycle:
- Run targeted tests for changed surfaces
- Run one relevant E2E scenario
- Perform two-eyes re-review on affected artifacts

If any scripture discrepancy appears: fail closed, stop the cycle, return with evidence.

---

## Stop State for Section 1

Section 1 is complete when:
- This plan artifact (2026-03-10__05) exists
- The paired findings artifact (2026-03-10__06) exists
- Both are saved under `planning/` and `docs/system/outputs/`
- No implementation changes have been made
- Human approval is awaited before Section 2
