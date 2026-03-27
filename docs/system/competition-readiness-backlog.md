# DevG Competition Readiness Backlog

Last updated: 2026-03-11 (America/New_York)
Scope: DevG System A only. This file is the interim tracker until local persistent memory is online.

## Priority 0 (Must finish before submission)

- [x] COMP-001: Competition outline CSV native loader
  - Status: pending
  - Requirement: `scripts/run_devotional_full.py` must accept `Series 1 - Volume 1 - 30-Day Outline.csv` directly.
  - Input schema: `Day, Week, Attribute, Scripture, Theme/Focus, Notes, Status`
  - Acceptance:
    - Build succeeds without conversion CSV.
    - Day scripture references come from `Scripture` column.
    - Day topic/focus derives from `Theme/Focus` + `Attribute`.

- [x] COMP-002: Agent scripture validator first, manual Logos only on mismatch/unavailable
  - Status: completed
  - Current behavior: agent comparison exists; manual fallback path exists.
  - Remaining:
    - Prefer independent machine validator text when available (API.Bible or import).
    - Trigger manual Logos reconciliation only when discrepancy or unavailable validator text.
  - Acceptance:
    - `__agent-validation-report.json` includes generated/validator scripture text comparison.
    - `manual_review_flags` is empty when texts match.
    - Manual-only state appears only for mismatch/unavailable validator text.

- [x] COMP-003: Series-level week-to-volume de-dup invariant (all series)
  - Status: completed
  - Rule:
    - Volume 1 defines canonical weeks.
    - Volume N (N>=2) expands corresponding week from Volume 1.
    - No scripture/quote from that parent week may reappear in mapped child volume.
  - Acceptance:
    - Enforced by registry checks for any `series_id`.
    - Violations fail publish-ready generation/export.

- [x] COMP-004: Auto-context for volume 2+ from registry
  - Status: completed
  - Requirement: requesting `series_id + volume_number` should be sufficient; no manual re-entry of week mapping.
  - Acceptance:
    - Generator resolves parent volume context automatically.
    - Child volume inherits canonical structure and exclusions.

- [x] COMP-005: Volume length inheritance rule
  - Status: completed
  - Rule: Volumes 2+ in a series must have same `num_days` as Volume 1 and expand related week.
  - Acceptance:
    - Preflight blocks mismatched day count.
    - Error includes expected vs provided values.

## Priority 1 (Audit/operability hardening)

- [x] AUD-001: Immutable audit linkage bundle per section
  - Status: completed
  - Requirement: each section should link decision + source provenance + artifact IDs deterministically.
  - Acceptance:
    - Persist section keys with: source id/url, retrieval timestamp, validator source, grounding/prayer ids.

- [x] AUD-002: UI discrepancy workflow polish
  - Status: completed
  - Requirement: when mismatch exists, UI shows both versions and explicit operator decision path.
  - Acceptance:
    - Studio panel includes generated vs validator text, source labels, and operator note capture.

- [x] AUD-003: Full Turabian quality gate
  - Status: completed
  - Requirement: enforce complete Turabian components in review/export path.
  - Acceptance:
    - Missing author/source/year/page-or-url blocks publish-ready export.

## Run discipline (until persistent memory is live)

- [ ] Always update this file before ending a major implementation session.
- [ ] Move completed items to a dated "Completed" section with artifact evidence.
- [ ] Keep one-line execution note for last successful test devotional run.

## Completed (2026-03-09 America/New_York)

- COMP-001
  - Evidence:
    - `src/api/full_run_assets.py` `load_competition_outline_from_csv(...)`
    - `scripts/run_devotional_full.py` outline path with direct `--csv` handling
    - `tests/pipeline/test_full_run_assets.py::test_load_competition_outline_from_csv`
- COMP-002
  - Evidence:
    - `src/api/full_run_assets.py` scripture validation now forces independent-source check (`_try_api_bible` for Bolls originals, `_try_bolls_life` for API.Bible/original-import) and reserves manual path for unavailable/mismatch cases
    - `tests/pipeline/test_full_run_assets.py` validation-path assertions
- COMP-003
  - Evidence:
    - registry context storage/query APIs in `src/registry/registry.py` and socket adapter
    - child-volume exclusion enforcement in `scripts/run_devotional_full.py` (`_enforce_child_week_scripture_exclusions`)
- COMP-004
  - Evidence:
    - auto-context lookup for `volume_number > 1` via registry volume/day-plan data in `scripts/run_devotional_full.py`
    - new registry/socket methods for volume lookup and day-plan retrieval
- COMP-005
  - Evidence:
    - preflight day-count inheritance enforcement in `scripts/run_devotional_full.py`
    - mismatch message includes expected vs provided counts
- AUD-001
  - Evidence:
    - per-run immutable linkage artifact: `__audit-linkage.json`
    - approval report `section_meta_by_key` enriched with section key + validator/source/artifact linkage
- AUD-002
  - Evidence:
    - studio discrepancy/manual-required workflow now requires operator note for approve/reject
    - decision metadata includes `operator_note`
- AUD-003
  - Evidence:
    - publish-ready export gate now blocks missing Turabian fields (`author`, `source_title`, `publication_year`, `page_or_url`)
    - tests updated in `tests/pipeline/test_export_gate.py`

## Completed (2026-03-11 America/New_York)

- CYCLE-1A semantic fix (queue/export mismatch)
  - Evidence:
    - `src/api/full_run_assets.py` now builds approval gate queue with `include_agent_validated=True`
    - `tests/pipeline/test_full_run_assets.py::test_build_approval_gate_report_surfaces_agent_validated_sections`
    - `docs/system/outputs/2026-03-10__09__devg__two-eyes-cycle-1a-results.md`
- CYCLE-1B decision-application + publish-ready CLI path
  - Evidence:
    - `scripts/apply_decisions_and_export.py` (deterministic decision apply, export-gate recheck, publish-ready PDF emit)
    - `scripts/run_devotional_full.py` now emits `PUBLISH_READY=...` operator command
    - `tests/review/test_apply_decisions_and_export.py`
    - `docs/system/outputs/2026-03-11__01__devg__two-eyes-cycle-1b-results.md`
- CYCLE-1B hardening (residual-risk closure)
  - Evidence:
    - Added rejected-path, missing-day, and explicit-out-pdf tests in `tests/review/test_apply_decisions_and_export.py`
    - Persistence path optimized in `scripts/apply_decisions_and_export.py` (`model_dump(mode="json")`)
    - `docs/system/outputs/2026-03-11__02__devg__two-eyes-cycle-1b-hardening.md`

## Current latest validated run

- Run slug: `2026-03-09__195419__genesis-1-&-2__12-day__vol-2`
- Artifacts root: `outputs/devotionals/`
- Notes:
  - Full pipeline succeeded with independent scripture import CSV.
  - Volume 2 child context auto-resolved from registry and completed with non-duplicate scripture/quote planning.
  - Audit linkage artifact emitted and wired into approval metadata.
