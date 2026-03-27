# Approval Contract (DevG)

As of: 2026-03-07

This document defines the operator approval behavior that must remain consistent in `DevG` and `DevG-S`.

## Contract

1. Canonical section state model is `pending | approved | rejected`.
2. Approval sessions must be resumable.
3. `skip` keeps a section pending (not resolved).
4. Publish-ready export is blocked unless all required sections are approved.
5. Every approval decision must carry audit metadata (`reviewed_by` and timestamp; source when available).

## Current DevG runner scope

- Primary entry point: `scripts/review/run_review.py` (defaults to UI backend)
- Browser fallback backend: `scripts/review/run_review.py --backend web` (local HTTP UI)
- CLI fallback: `scripts/review/run_pending_approvals.py`
- Runner currently operates from approval-gate report JSON and writes decision artifacts.
- It supports long-running review by persisting progress and resuming from prior output.
- Decision metadata fields:
  - `reviewed_at_utc` (UTC timestamp, stored)
  - `reviewed_by` (defaults to `Victor`, override via `--reviewed-by` or `DEVG_REVIEWED_BY`)
  - `decision_source` (required for agent reviewers; optional for human reviewers)
    - Agent examples: `secondary_source_crosscheck`, `cli_batch_reject_all`
    - Human decisions may omit `decision_source`

## Parity Checklist (Automated)

Run:

```bash
pytest tests/review/test_approval_contract_parity.py tests/review/test_pending_approvals.py tests/pipeline/test_export_gate.py tests/test_schemas.py
```

Checks covered:

1. Enum contains `pending`, `approved`, `rejected`.
2. Publish-ready export blocks any non-approved section.
3. `skip` is not treated as resolved on resume.
4. Batch actions can overwrite stale `skipped` entries with final decisions.
5. Approval decision artifacts still round-trip correctly.
