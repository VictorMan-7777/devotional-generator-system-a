"""Integration tests for src/api/generation_pipeline.py — generate_devotional().

Tests that call export_pdf() (spawning the TypeScript subprocess) are gated
behind module-scoped fixtures that skip when npx is unavailable, and reuse
a single PipelineResult per fixture to minimise subprocess invocations.

All other tests use OutputMode.PUBLISH_READY — sections default to PENDING,
so the export gate blocks and export_pdf() is never called.
"""
from __future__ import annotations

import shutil

import pytest

from src.api.generation_pipeline import generate_devotional
from src.generation.generators import FailFirstMockGenerator
from src.models.devotional import OutputMode
from src.registry.registry import SeriesRegistry

# ---------------------------------------------------------------------------
# npx availability check
# ---------------------------------------------------------------------------

_NPX_AVAILABLE = shutil.which("npx") is not None


# ---------------------------------------------------------------------------
# Module-scoped fixtures (PDF-producing; skipped when npx unavailable)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def personal_1_day():
    """One-day PERSONAL generation — calls export_pdf() once for the module."""
    if not _NPX_AVAILABLE:
        pytest.skip("npx not available")
    return generate_devotional("grace", 1, output_mode=OutputMode.PERSONAL)


@pytest.fixture(scope="module")
def personal_3_day():
    """Three-day PERSONAL generation — calls export_pdf() once for the module."""
    if not _NPX_AVAILABLE:
        pytest.skip("npx not available")
    return generate_devotional("faith", 3, output_mode=OutputMode.PERSONAL)


# ---------------------------------------------------------------------------
# End-to-end PERSONAL mode
# ---------------------------------------------------------------------------


class TestEndToEndPersonalMode:
    def test_pdf_bytes_start_with_pdf_magic(self, personal_1_day):
        assert personal_1_day.pdf_bytes[:4] == b"%PDF"

    def test_no_validation_failures(self, personal_1_day):
        assert personal_1_day.validation_summary.failed == 0

    def test_export_gate_exportable(self, personal_1_day):
        assert personal_1_day.export_gate_result.exportable is True

    def test_registry_volume_id_non_empty(self, personal_1_day):
        assert personal_1_day.registry_volume_id != ""


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

    def test_three_day_pdf_valid(self, personal_3_day):
        assert personal_3_day.pdf_bytes[:4] == b"%PDF"
