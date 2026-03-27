from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from src.generation.generators import MockSectionGenerator
from src.models.devotional import DevotionalBook, DevotionalInput, OutputMode, SectionApprovalStatus
from src.review_store import build_review_socket, infer_run_slug, save_decision

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "apply_decisions_and_export.py"
_SPEC = spec_from_file_location("apply_decisions_and_export", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)


def _book_one_day() -> DevotionalBook:
    day = MockSectionGenerator().generate_day("grace", 1)
    if day.timeless_wisdom.publication_year is None:
        day.timeless_wisdom.publication_year = 1900
    return DevotionalBook(
        id="book-1",
        input=DevotionalInput(topic="grace", num_days=1, output_mode=OutputMode.PUBLISH_READY),
        days=[day],
    )


def _write_book(path: Path, book: DevotionalBook) -> None:
    path.write_text(book.model_dump_json(indent=2), encoding="utf-8")


def _write_decisions(path: Path, decisions: list[dict]) -> None:
    payload = {
        "source_report": "report.json",
        "decisions": decisions,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _approved_record(day: int, section: str) -> dict:
    return {
        "day": day,
        "section": section,
        "decision": "approved",
        "reviewed_by": "Victor",
        "reviewed_at_utc": "2026-03-11T00:00:00+00:00",
    }


def test_apply_decisions_blocks_when_not_all_sections_approved(tmp_path: Path) -> None:
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    _write_book(book_path, _book_one_day())
    _write_decisions(decisions_path, [_approved_record(1, "scripture")])

    pdf_path, blocked_reason, applied, skipped, ignored = _MODULE.run_apply_decisions_and_export(
        book_json_path=book_path,
        decisions_json_path=decisions_path,
    )

    assert pdf_path is None
    assert blocked_reason is not None and "pending approval" in blocked_reason
    assert applied == 1
    assert skipped == 0
    assert ignored == 0


def test_apply_decisions_exports_when_all_sections_approved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    _write_book(book_path, _book_one_day())
    _write_decisions(
        decisions_path,
        [
            _approved_record(1, "timeless_wisdom"),
            _approved_record(1, "scripture"),
            _approved_record(1, "exposition"),
            _approved_record(1, "be_still"),
            _approved_record(1, "action_steps"),
            _approved_record(1, "prayer"),
        ],
    )

    monkeypatch.setattr(_MODULE, "export_pdf", lambda document, output_mode="publish-ready": b"%PDF-1.4\nmock")

    pdf_path, blocked_reason, applied, skipped, ignored = _MODULE.run_apply_decisions_and_export(
        book_json_path=book_path,
        decisions_json_path=decisions_path,
    )

    assert blocked_reason is None
    assert applied == 6
    assert skipped == 0
    assert ignored == 0
    assert pdf_path is not None
    assert pdf_path.exists()
    assert pdf_path.name.endswith("__publish-ready.pdf")
    assert pdf_path.read_bytes().startswith(b"%PDF")

    persisted = DevotionalBook.model_validate(json.loads(book_path.read_text(encoding="utf-8")))
    day = persisted.days[0]
    assert day.timeless_wisdom.approval_status == SectionApprovalStatus.APPROVED
    assert day.scripture.approval_status == SectionApprovalStatus.APPROVED
    assert day.exposition.approval_status == SectionApprovalStatus.APPROVED
    assert day.be_still.approval_status == SectionApprovalStatus.APPROVED
    assert day.action_steps.approval_status == SectionApprovalStatus.APPROVED
    assert day.prayer.approval_status == SectionApprovalStatus.APPROVED


def test_apply_decisions_exports_reviewed_proof_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    _write_book(book_path, _book_one_day())
    _write_decisions(
        decisions_path,
        [
            _approved_record(1, "timeless_wisdom"),
            _approved_record(1, "scripture"),
            _approved_record(1, "exposition"),
            _approved_record(1, "be_still"),
            _approved_record(1, "action_steps"),
            _approved_record(1, "prayer"),
        ],
    )

    captured_modes: list[str] = []

    def _mock_export(document, output_mode="publish-ready"):
        captured_modes.append(output_mode)
        return b"%PDF-1.4\nmock"

    monkeypatch.setattr(_MODULE, "export_pdf", _mock_export)

    pdf_path, blocked_reason, applied, skipped, ignored = _MODULE.run_apply_decisions_and_export(
        book_json_path=book_path,
        decisions_json_path=decisions_path,
        output_mode=OutputMode.PERSONAL,
    )

    assert blocked_reason is None
    assert applied == 6
    assert skipped == 0
    assert ignored == 0
    assert pdf_path is not None
    assert pdf_path.name.endswith("__reviewed-proof.pdf")
    assert captured_modes == ["reviewed-proof"]


def test_apply_decisions_supports_label_variants(tmp_path: Path) -> None:
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    _write_book(book_path, _book_one_day())
    _write_decisions(
        decisions_path,
        [
            _approved_record(1, "Timeless Wisdom"),
            _approved_record(1, "Action Steps"),
        ],
    )

    pdf_path, blocked_reason, applied, skipped, ignored = _MODULE.run_apply_decisions_and_export(
        book_json_path=book_path,
        decisions_json_path=decisions_path,
    )

    assert pdf_path is None
    assert blocked_reason is not None
    assert applied == 2
    assert skipped == 0
    assert ignored == 0


def test_apply_decisions_raises_for_unknown_section(tmp_path: Path) -> None:
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    _write_book(book_path, _book_one_day())
    _write_decisions(
        decisions_path,
        [
            {
                "day": 1,
                "section": "mystery_section",
                "decision": "approved",
                "reviewed_by": "Victor",
                "reviewed_at_utc": "2026-03-11T00:00:00+00:00",
            }
        ],
    )

    with pytest.raises(ValueError, match="Unknown section name"):
        _MODULE.run_apply_decisions_and_export(
            book_json_path=book_path,
            decisions_json_path=decisions_path,
        )


def test_main_returns_nonzero_when_blocked(tmp_path: Path) -> None:
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    _write_book(book_path, _book_one_day())
    _write_decisions(decisions_path, [_approved_record(1, "scripture")])

    rc = _MODULE.main([
        "--book-json",
        str(book_path),
        "--decisions-json",
        str(decisions_path),
    ])
    assert rc == 2


def test_apply_decisions_sets_rejected_and_gate_blocks(tmp_path: Path) -> None:
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    _write_book(book_path, _book_one_day())
    _write_decisions(
        decisions_path,
        [
            {
                "day": 1,
                "section": "scripture",
                "decision": "rejected",
                "reviewed_by": "Victor",
                "reviewed_at_utc": "2026-03-11T00:00:00+00:00",
            }
        ],
    )

    pdf_path, blocked_reason, applied, skipped, ignored = _MODULE.run_apply_decisions_and_export(
        book_json_path=book_path,
        decisions_json_path=decisions_path,
    )

    assert pdf_path is None
    assert blocked_reason is not None and "pending approval" in blocked_reason
    assert applied == 1
    assert skipped == 0
    assert ignored == 0

    persisted = DevotionalBook.model_validate(json.loads(book_path.read_text(encoding="utf-8")))
    assert persisted.days[0].scripture.approval_status == SectionApprovalStatus.REJECTED


def test_apply_decisions_raises_for_missing_day(tmp_path: Path) -> None:
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    _write_book(book_path, _book_one_day())
    _write_decisions(
        decisions_path,
        [
            {
                "day": 99,
                "section": "scripture",
                "decision": "approved",
                "reviewed_by": "Victor",
                "reviewed_at_utc": "2026-03-11T00:00:00+00:00",
            }
        ],
    )

    with pytest.raises(ValueError, match="missing day 99"):
        _MODULE.run_apply_decisions_and_export(
            book_json_path=book_path,
            decisions_json_path=decisions_path,
        )


def test_apply_decisions_honors_out_pdf_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    explicit_pdf = tmp_path / "custom-output.pdf"
    _write_book(book_path, _book_one_day())
    _write_decisions(
        decisions_path,
        [
            _approved_record(1, "timeless_wisdom"),
            _approved_record(1, "scripture"),
            _approved_record(1, "exposition"),
            _approved_record(1, "be_still"),
            _approved_record(1, "action_steps"),
            _approved_record(1, "prayer"),
        ],
    )
    monkeypatch.setattr(_MODULE, "export_pdf", lambda document, output_mode="publish-ready": b"%PDF-1.4\nmock")

    pdf_path, blocked_reason, applied, skipped, ignored = _MODULE.run_apply_decisions_and_export(
        book_json_path=book_path,
        decisions_json_path=decisions_path,
        out_pdf_path=explicit_pdf,
    )

    assert blocked_reason is None
    assert applied == 6
    assert skipped == 0
    assert ignored == 0
    assert pdf_path == explicit_pdf
    assert explicit_pdf.exists()


def test_apply_decisions_uses_review_store_content_before_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVG_SQLITE_PATH", str(tmp_path / "review.sqlite3"))
    book_path = tmp_path / "sample__book.json"
    decisions_path = tmp_path / "sample__approval-decisions.json"
    book = _book_one_day()
    _write_book(book_path, book)
    _write_decisions(
        decisions_path,
        [
            _approved_record(1, "timeless_wisdom"),
            _approved_record(1, "scripture"),
            _approved_record(1, "exposition"),
            _approved_record(1, "be_still"),
            _approved_record(1, "action_steps"),
            _approved_record(1, "prayer"),
        ],
    )
    review_socket = build_review_socket()
    run_slug = infer_run_slug(book_path)
    save_decision(
        socket=review_socket,
        run_slug=run_slug,
        day_number=1,
        section_name="exposition",
        approval_decision="approved",
        operator_note="looks good",
        reviewed_by="Victor",
        decision_source=None,
        reviewed_at_utc="2026-03-11T00:00:00+00:00",
        approved_payload={
            "text": "Reviewed exposition text.",
            "word_count": 3,
            "grounding_map_id": book.days[0].exposition.grounding_map_id,
            "approval_status": "approved",
        },
        approved_preview="Reviewed exposition text.",
    )
    monkeypatch.setattr(_MODULE, "export_pdf", lambda document, output_mode="publish-ready": b"%PDF-1.4\nmock")

    pdf_path, blocked_reason, applied, skipped, ignored = _MODULE.run_apply_decisions_and_export(
        book_json_path=book_path,
        decisions_json_path=decisions_path,
    )

    assert blocked_reason is None
    assert pdf_path is not None
    persisted = DevotionalBook.model_validate(json.loads(book_path.read_text(encoding="utf-8")))
    assert persisted.days[0].exposition.text == "Reviewed exposition text."
