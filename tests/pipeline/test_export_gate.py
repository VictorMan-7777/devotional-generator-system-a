"""Tests for src/api/export_gate.py — ExportGate.check_exportability()."""
from __future__ import annotations

from src.api.export_gate import ExportGate
from src.generation.generators import MockSectionGenerator
from src.models.devotional import (
    DevotionalBook,
    DevotionalInput,
    OutputMode,
    SectionApprovalStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(*days) -> DevotionalBook:
    return DevotionalBook(
        id="test-book-001",
        input=DevotionalInput(topic="grace"),
        days=list(days),
    )


def _pending_day(day_number: int = 1):
    """Day with all sections at SectionApprovalStatus.PENDING (model default)."""
    return MockSectionGenerator().generate_day("grace", day_number)


def _approved_day(day_number: int = 1):
    """Day with all six core sections set to SectionApprovalStatus.APPROVED."""
    day = MockSectionGenerator().generate_day("grace", day_number)
    for attr in ("timeless_wisdom", "scripture", "exposition", "be_still", "action_steps", "prayer"):
        section = getattr(day, attr)
        approved = section.model_copy(update={"approval_status": SectionApprovalStatus.APPROVED})
        object.__setattr__(day, attr, approved)
    return day


# ---------------------------------------------------------------------------
# PERSONAL mode
# ---------------------------------------------------------------------------


class TestPersonalMode:
    def test_pending_sections_are_exportable_with_warnings(self):
        book = _make_book(_pending_day())
        result = ExportGate().check_exportability(book, OutputMode.PERSONAL)
        assert result.exportable is True
        assert len(result.warnings) > 0

    def test_all_approved_sections_exportable_no_warnings(self):
        book = _make_book(_approved_day())
        result = ExportGate().check_exportability(book, OutputMode.PERSONAL)
        assert result.exportable is True
        assert result.warnings == []

    def test_warnings_reference_pending_sections(self):
        book = _make_book(_pending_day())
        result = ExportGate().check_exportability(book, OutputMode.PERSONAL)
        assert any("exposition" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# PUBLISH_READY mode
# ---------------------------------------------------------------------------


class TestPublishReadyMode:
    def test_pending_sections_block_export(self):
        book = _make_book(_pending_day())
        result = ExportGate().check_exportability(book, OutputMode.PUBLISH_READY)
        assert result.exportable is False
        assert result.blocked_reason is not None
        assert len(result.blocked_reason) > 0

    def test_all_approved_sections_exportable(self):
        book = _make_book(_approved_day())
        result = ExportGate().check_exportability(book, OutputMode.PUBLISH_READY)
        assert result.exportable is True

    def test_multi_day_one_pending_day_blocks(self):
        book = _make_book(_approved_day(1), _pending_day(2))
        result = ExportGate().check_exportability(book, OutputMode.PUBLISH_READY)
        assert result.exportable is False

    def test_blocked_reason_absent_when_all_approved(self):
        book = _make_book(_approved_day())
        result = ExportGate().check_exportability(book, OutputMode.PUBLISH_READY)
        assert result.blocked_reason is None


# ---------------------------------------------------------------------------
# Non-mutation
# ---------------------------------------------------------------------------


class TestNonMutation:
    def test_export_gate_does_not_mutate_book(self):
        book = _make_book(_pending_day())
        original_status = book.days[0].exposition.approval_status
        ExportGate().check_exportability(book, OutputMode.PUBLISH_READY)
        assert book.days[0].exposition.approval_status == original_status
