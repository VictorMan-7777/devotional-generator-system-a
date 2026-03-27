from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from src.api.export_gate import ExportGate
from src.generation.generators import MockSectionGenerator
from src.models.devotional import (
    DevotionalBook,
    DevotionalInput,
    OutputMode,
    SectionApprovalStatus,
)


_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "review" / "run_pending_approvals.py"
_SPEC = spec_from_file_location("run_pending_approvals_contract", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
PendingItem = _MODULE.PendingItem
unresolved_items = _MODULE.unresolved_items
run_batch = _MODULE.run_batch


def _make_book(day) -> DevotionalBook:
    return DevotionalBook(
        id="approval-contract-book",
        input=DevotionalInput(topic="approval-contract"),
        days=[day],
    )


def _approved_day():
    day = MockSectionGenerator().generate_day("approval-contract", 1)
    for attr in ("timeless_wisdom", "scripture", "exposition", "be_still", "action_steps", "prayer"):
        section = getattr(day, attr)
        approved = section.model_copy(update={"approval_status": SectionApprovalStatus.APPROVED})
        object.__setattr__(day, attr, approved)
    return day


def test_contract_status_model_contains_rejected() -> None:
    values = {s.value for s in SectionApprovalStatus}
    assert {"pending", "approved", "rejected"}.issubset(values)


def test_contract_publish_ready_blocks_non_approved_states() -> None:
    gate = ExportGate()
    pending_day = MockSectionGenerator().generate_day("approval-contract", 1)
    pending_result = gate.check_exportability(_make_book(pending_day), OutputMode.PUBLISH_READY)
    assert pending_result.exportable is False

    rejected_day = _approved_day()
    rejected_exposition = rejected_day.exposition.model_copy(
        update={"approval_status": SectionApprovalStatus.REJECTED}
    )
    object.__setattr__(rejected_day, "exposition", rejected_exposition)
    rejected_result = gate.check_exportability(_make_book(rejected_day), OutputMode.PUBLISH_READY)
    assert rejected_result.exportable is False


def test_contract_skip_is_not_resolved_for_resume() -> None:
    items = [PendingItem(day=1, section="scripture"), PendingItem(day=1, section="prayer")]
    decision_map = {"1:scripture": {"day": 1, "section": "scripture", "decision": "skipped"}}
    unresolved = unresolved_items(items, decision_map)
    assert unresolved == items


def test_contract_decisions_include_audit_metadata() -> None:
    items = [PendingItem(day=1, section="scripture")]
    decision_map = run_batch(
        items,
        decision="approved",
        decision_map={},
        reviewed_by="Victor",
        decision_source="cli_batch_approve_all",
    )
    rec = decision_map["1:scripture"]
    assert rec["reviewed_by"] == "Victor"
    assert rec["decision_source"] == "cli_batch_approve_all"
    assert "reviewed_at_utc" in rec
