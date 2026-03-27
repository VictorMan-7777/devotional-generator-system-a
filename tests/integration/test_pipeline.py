"""Integration tests for src/api/generation_pipeline.py — generate_devotional().

Standard generation now stops at review and does not emit PDFs directly.
These tests assert the review-stage contract rather than legacy PDF bytes.
"""
from __future__ import annotations

import pytest

from src.api.generation_pipeline import generate_devotional
from src.generation.generators import FailFirstMockGenerator, MockSectionGenerator
from src.models.devotional import OutputMode
from src.registry.registry import SeriesRegistry

# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def personal_1_day():
    """One-day PERSONAL generation — stops at review stage."""
    return generate_devotional("grace", 1, output_mode=OutputMode.PERSONAL)


@pytest.fixture(scope="module")
def personal_3_day():
    """Three-day PERSONAL generation — stops at review stage."""
    return generate_devotional("faith", 3, output_mode=OutputMode.PERSONAL)


# ---------------------------------------------------------------------------
# End-to-end PERSONAL mode
# ---------------------------------------------------------------------------


class TestEndToEndPersonalMode:
    def test_personal_mode_stops_before_pdf_export(self, personal_1_day):
        assert personal_1_day.pdf_bytes == b""

    def test_no_validation_failures(self, personal_1_day):
        assert personal_1_day.validation_summary.failed == 0

    def test_export_gate_exportable(self, personal_1_day):
        assert personal_1_day.export_gate_result.exportable is True

    def test_registry_volume_id_non_empty(self, personal_1_day):
        assert personal_1_day.registry_volume_id != ""

    def test_editorial_build_present(self, personal_1_day):
        assert personal_1_day.editorial_build.num_days == 1
        assert len(personal_1_day.editorial_build.day_briefs) == 1
        assert personal_1_day.editorial_build.week_plans[0].days == [1]


# ---------------------------------------------------------------------------
# Retry path (PUBLISH_READY to avoid subprocess)
# ---------------------------------------------------------------------------


class TestRetryPath:
    def test_auto_rewrite_event_recorded(self):
        result = generate_devotional(
            "grace",
            1,
            generator=FailFirstMockGenerator(),
            output_mode=OutputMode.PUBLISH_READY,
        )
        assert len(result.validation_summary.rewrite_events) == 1
        event = result.validation_summary.rewrite_events[0]
        assert event.signal == "auto_rewrite"
        assert event.attempt_number == 1

    def test_final_validation_passes_after_retry(self):
        result = generate_devotional(
            "grace",
            1,
            generator=FailFirstMockGenerator(),
            output_mode=OutputMode.PUBLISH_READY,
        )
        assert result.validation_summary.failed == 0

    def test_failed_check_ids_populated_in_rewrite_event(self):
        result = generate_devotional(
            "grace",
            1,
            generator=FailFirstMockGenerator(),
            output_mode=OutputMode.PUBLISH_READY,
        )
        assert (
            "EXPOSITION_WORD_COUNT"
            in result.validation_summary.rewrite_events[0].failed_check_ids
        )

    def test_book_quality_auto_rewrite_event_recorded(self):
        class BookQualityFailFirstGenerator:
            def generate_day(
                self,
                topic,
                day_number,
                attempt_number=1,
                scripture_reference=None,
                forbidden_quote_texts=None,
            ):
                day = MockSectionGenerator().generate_day(
                    topic,
                    day_number,
                    attempt_number=attempt_number,
                    scripture_reference=scripture_reference,
                    forbidden_quote_texts=forbidden_quote_texts,
                )
                if day_number == 2 and attempt_number < 3:
                    prior = MockSectionGenerator().generate_day(
                        topic,
                        1,
                        attempt_number=attempt_number,
                        scripture_reference=scripture_reference,
                        forbidden_quote_texts=forbidden_quote_texts,
                    )
                    day.exposition = prior.exposition.model_copy(deep=True)
                    day.be_still = prior.be_still.model_copy(deep=True)
                    day.action_steps = prior.action_steps.model_copy(deep=True)
                    day.prayer = prior.prayer.model_copy(deep=True)
                return day

        result = generate_devotional(
            "grace",
            2,
            generator=BookQualityFailFirstGenerator(),
            output_mode=OutputMode.PUBLISH_READY,
        )

        book_events = [
            event for event in result.validation_summary.rewrite_events if event.scope == "book"
        ]
        assert len(book_events) == 1
        assert book_events[0].signal == "auto_rewrite"
        assert 2 in book_events[0].target_day_numbers
        assert result.validation_summary.failed == 0


# ---------------------------------------------------------------------------
# Registry writes (PUBLISH_READY to avoid subprocess)
# ---------------------------------------------------------------------------


class TestRegistryWrites:
    def test_author_distribution_non_empty(self, tmp_path):
        registry = SeriesRegistry(db_path=tmp_path / "r.db")
        result = generate_devotional(
            "grace", 1, registry=registry, output_mode=OutputMode.PUBLISH_READY
        )
        dist = registry.get_author_distribution(result.registry_volume_id)
        assert len(dist) > 0

    def test_volume_id_corresponds_to_real_volume(self, tmp_path):
        registry = SeriesRegistry(db_path=tmp_path / "r2.db")
        result = generate_devotional(
            "grace", 1, registry=registry, output_mode=OutputMode.PUBLISH_READY
        )
        dist = registry.get_author_distribution(result.registry_volume_id)
        assert isinstance(dist, dict)


# ---------------------------------------------------------------------------
# Export gate block
# ---------------------------------------------------------------------------


class TestExportGateBlock:
    def test_publish_ready_with_pending_sections_blocked(self):
        result = generate_devotional("grace", 1, output_mode=OutputMode.PUBLISH_READY)
        assert result.pdf_bytes == b""
        assert result.export_gate_result.exportable is False
        assert result.export_gate_result.blocked_reason is not None


# ---------------------------------------------------------------------------
# Multi-day
# ---------------------------------------------------------------------------


class TestMultiDay:
    def test_three_day_book_has_three_days(self):
        result = generate_devotional("faith", 3, output_mode=OutputMode.PUBLISH_READY)
        assert len(result.book.days) == 3

    def test_three_day_personal_mode_stops_before_pdf_export(self, personal_3_day):
        assert personal_3_day.pdf_bytes == b""
