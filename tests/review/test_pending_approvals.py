from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "review" / "run_pending_approvals.py"
_SPEC = spec_from_file_location("run_pending_approvals", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
parse_pending_item = _MODULE.parse_pending_item
load_existing_decisions = _MODULE.load_existing_decisions
main = _MODULE.main
run_batch = _MODULE.run_batch
unresolved_items = _MODULE.unresolved_items
write_decisions = _MODULE.write_decisions
PendingItem = _MODULE.PendingItem
format_section_label = _MODULE.format_section_label


def test_parse_pending_item_valid() -> None:
    item = parse_pending_item("day 12 — prayer")
    assert item.day == 12
    assert item.section == "prayer"


def test_format_section_label_known_keys() -> None:
    assert format_section_label("timeless_wisdom") == "Timeless Wisdom"
    assert format_section_label("action_steps") == "Action Steps"
    assert format_section_label("be_still") == "Be Still"


def test_format_section_label_fallback() -> None:
    assert format_section_label("my_custom_field") == "My Custom Field"


@pytest.mark.parametrize(
    "raw",
    [
        "day12 prayer",
        "day -1 — prayer",
        "x 3 — prayer",
        "day 3 — ",
    ],
)
def test_parse_pending_item_invalid(raw: str) -> None:
    with pytest.raises(Exception):
        parse_pending_item(raw)


def test_script_exists() -> None:
    p = Path(__file__).resolve().parents[2] / "scripts" / "review" / "run_pending_approvals.py"
    assert p.exists()


def test_run_batch_respects_existing_decisions() -> None:
    items = [PendingItem(day=1, section="scripture"), PendingItem(day=1, section="prayer")]
    existing = {
        "1:scripture": {
            "day": 1,
            "section": "scripture",
            "decision": "approved",
            "reviewed_at_utc": "2026-03-07T00:00:00+00:00",
        }
    }
    out = run_batch(
        items,
        decision="rejected",
        decision_map=existing.copy(),
        reviewed_by="Victor",
        decision_source="cli_batch_reject_all",
    )
    assert out["1:scripture"]["decision"] == "approved"
    assert out["1:prayer"]["decision"] == "rejected"
    assert out["1:prayer"]["reviewed_by"] == "Victor"
    assert out["1:prayer"]["decision_source"] == "cli_batch_reject_all"


def test_write_and_load_decisions_round_trip(tmp_path: Path) -> None:
    output = tmp_path / "decisions.json"
    report = {"source_report": "r.json", "topic": "Genesis 1-2", "days": 12}
    decision_map = {
        "1:scripture": {
            "day": 1,
            "section": "scripture",
            "decision": "approved",
            "reviewed_at_utc": "2026-03-07T00:00:00+00:00",
        }
    }
    write_decisions(
        output_path=output,
        report=report,
        decision_map=decision_map,
        mode="interactive",
        total_pending=72,
    )
    loaded = load_existing_decisions(output)
    assert "1:scripture" in loaded
    assert loaded["1:scripture"]["decision"] == "approved"


def test_unresolved_items_filters_existing() -> None:
    items = [PendingItem(day=1, section="scripture"), PendingItem(day=2, section="prayer")]
    existing = {"1:scripture": {"day": 1, "section": "scripture", "decision": "approved"}}
    unresolved = unresolved_items(items, existing)
    assert unresolved == [PendingItem(day=2, section="prayer")]


def test_unresolved_items_includes_skipped_entries() -> None:
    items = [PendingItem(day=1, section="scripture"), PendingItem(day=2, section="prayer")]
    existing = {"1:scripture": {"day": 1, "section": "scripture", "decision": "skipped"}}
    unresolved = unresolved_items(items, existing)
    assert unresolved == items


def test_run_batch_overwrites_prior_skipped() -> None:
    items = [PendingItem(day=1, section="scripture")]
    existing = {
        "1:scripture": {
            "day": 1,
            "section": "scripture",
            "decision": "skipped",
            "reviewed_at_utc": "2026-03-07T00:00:00+00:00",
        }
    }
    out = run_batch(
        items,
        decision="approved",
        decision_map=existing.copy(),
        reviewed_by="Victor",
        decision_source="cli_batch_approve_all",
    )
    assert out["1:scripture"]["decision"] == "approved"
    assert out["1:scripture"]["reviewed_by"] == "Victor"
    assert out["1:scripture"]["decision_source"] == "cli_batch_approve_all"


def test_load_existing_decisions_backfills_metadata_for_legacy_records(tmp_path: Path) -> None:
    output = tmp_path / "decisions.json"
    output.write_text(
        """
{
  "decisions": [
    {"day": 1, "section": "scripture", "decision": "approved", "reviewed_at_utc": "2026-03-07T00:00:00+00:00"}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    loaded = load_existing_decisions(output)
    assert loaded["1:scripture"]["reviewed_by"] == "Victor"
    assert "decision_source" not in loaded["1:scripture"]


def test_load_existing_decisions_ignores_mismatched_source_report(tmp_path: Path) -> None:
    output = tmp_path / "decisions.json"
    output.write_text(
        """
{
  "source_report": "/tmp/old-report.json",
  "decisions": [
    {"day": 1, "section": "scripture", "decision": "approved", "reviewed_at_utc": "2026-03-07T00:00:00+00:00"}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    loaded = load_existing_decisions(output, expected_source_report=tmp_path / "new-report.json")
    assert loaded == {}


def test_agent_reviewer_requires_decision_source(tmp_path: Path) -> None:
    report = tmp_path / "r.json"
    report.write_text('{"pending_sections": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="Agent decisions require decision_source"):
        main(
            [
                "--report",
                str(report),
                "--mode",
                "interactive",
                "--reviewed-by",
                "agent:verifier-1",
            ]
        )


def test_approve_all_is_gated_by_default(tmp_path: Path) -> None:
    report = tmp_path / "r.json"
    report.write_text('{"pending_sections": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="approve-all is disabled by default"):
        main(["--report", str(report), "--mode", "approve-all"])
