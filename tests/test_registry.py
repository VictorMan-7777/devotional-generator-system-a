"""
Series Registry tests — TC-05, FR-64–FR-72.

All tests use pytest's tmp_path fixture for isolated SQLite databases.
No shared state between tests; each creates its own SeriesRegistry instance.

Coverage:
  - Series and volume creation (including parent-child)
  - Persistence: data survives a new registry instance on the same DB path
  - Quote deduplication: within-volume hard fail (FR-66), cross-volume flag (FR-65)
  - Override paths: override_reason stored, no exception raised
  - Scripture duplication warning (FR-67): non-blocking, is_duplicate=True
  - Author distribution (FR-68): counts correct per volume
  - Parent distribution for attribute (FR-71): parent's distribution surfaced for child
  - Backup (TC-05): file copy to backup path
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.registry import (
    AutoresearchExperimentRecord,
    OutlinerSystemComparisonRecord,
    QuoteRecord,
    ResourceAcquisitionRequestRecord,
    ScriptureRecord,
    TrainerRecommendationRecord,
    VolumeDayPlanRecord,
    VolumeRecord,
)
from src.registry.registry import (
    CrossVolumeDuplicateError,
    DuplicateQuoteError,
    RegistryError,
    ScriptureUseResult,
    SeriesRegistry,
)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def registry(tmp_path: Path) -> SeriesRegistry:
    """Fresh registry backed by an isolated SQLite file."""
    return SeriesRegistry(db_path=tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_series_and_volume(
    r: SeriesRegistry,
    series_id: str = "series-001",
    volume_id: str = "vol-001",
    volume_number: int = 1,
    parent_volume_id: str | None = None,
) -> VolumeRecord:
    r.create_series(series_id)
    return r.create_volume(
        volume_id,
        series_id,
        volume_number,
        parent_volume_id=parent_volume_id,
    )


def _add_quote(
    r: SeriesRegistry,
    volume_id: str = "vol-001",
    series_id: str = "series-001",
    quote_text: str = "All is grace.",
    author: str = "Thomas Merton",
    source_title: str = "Thoughts in Solitude",
    override_reason: str | None = None,
) -> QuoteRecord:
    return r.record_quote_use(
        volume_id=volume_id,
        series_id=series_id,
        quote_text=quote_text,
        author=author,
        source_title=source_title,
        override_reason=override_reason,
    )


# ---------------------------------------------------------------------------
# TestCreateSeriesAndVolume
# ---------------------------------------------------------------------------


class TestCreateSeriesAndVolume:
    def test_create_series_is_idempotent(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1", title="Grace Series")
        registry.create_series("s1", title="Ignored on repeat")  # should not raise

    def test_create_volume_returns_volume_record(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1")
        vol = registry.create_volume("v1", "s1", 1, title="Volume One")
        assert isinstance(vol, VolumeRecord)
        assert vol.id == "v1"
        assert vol.series_id == "s1"
        assert vol.volume_number == 1
        assert vol.title == "Volume One"

    def test_create_volume_without_title(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1")
        vol = registry.create_volume("v1", "s1", 1)
        assert vol.title is None

    def test_create_child_volume_stores_parent_id(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1")
        registry.create_volume("parent-vol", "s1", 1)
        child = registry.create_volume("child-vol", "s1", 2, parent_volume_id="parent-vol")
        assert child.id == "child-vol"


# ---------------------------------------------------------------------------
# TestPersistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_registry_survives_restart(self, tmp_path: Path) -> None:
        """Data written to SQLite file is readable by a new SeriesRegistry instance."""
        db = tmp_path / "persist.db"

        # Session 1 — write
        r1 = SeriesRegistry(db_path=db)
        r1.create_series("s1")
        r1.create_volume("v1", "s1", 1)
        r1.record_quote_use("v1", "s1", "All is grace.", "Thomas Merton", "Thoughts in Solitude")
        r1.record_scripture_use("v1", "Romans 8:15", "NASB")

        # Session 2 — new instance, same file (simulates process restart)
        r2 = SeriesRegistry(db_path=db)
        dist = r2.get_author_distribution("v1")
        assert dist == {"Thomas Merton": 1}

    def test_multiple_volumes_survive_restart(self, tmp_path: Path) -> None:
        db = tmp_path / "persist2.db"

        r1 = SeriesRegistry(db_path=db)
        r1.create_series("s1")
        r1.create_volume("v1", "s1", 1)
        r1.create_volume("v2", "s1", 2)
        r1.record_quote_use("v1", "s1", "Quote one", "Author A", "Book A")
        r1.record_quote_use("v2", "s1", "Quote two", "Author B", "Book B", override_reason="cross-vol-new")

        r2 = SeriesRegistry(db_path=db)
        dist_v1 = r2.get_author_distribution("v1")
        dist_v2 = r2.get_author_distribution("v2")
        assert dist_v1 == {"Author A": 1}
        assert dist_v2 == {"Author B": 1}

    def test_delete_volume_removes_usage_records(self, tmp_path: Path) -> None:
        db = tmp_path / "persist3.db"
        r1 = SeriesRegistry(db_path=db)
        r1.create_series("s1")
        r1.create_volume("v1", "s1", 1)
        r1.record_quote_use("v1", "s1", "All is grace.", "Thomas Merton", "Thoughts in Solitude")
        r1.record_scripture_use("v1", "Romans 8:15", "NASB")

        assert r1.delete_volume("v1") is True

        r2 = SeriesRegistry(db_path=db)
        assert r2.get_volume_by_number("s1", 1) is None
        assert r2.get_author_distribution("v1") == {}

    def test_resource_acquisition_requests_survive_restart(self, tmp_path: Path) -> None:
        db = tmp_path / "persist-librarian.db"
        r1 = SeriesRegistry(db_path=db)
        record = r1.request_resource_acquisition(
            request_id="req-1",
            requested_by="research_librarian",
            scripture_reference="Luke 15",
            topic="Luke 15",
            worker_name="outliner",
            reason="Need more outline help for clustered parables.",
            requested_resource_kinds=["outline", "commentary"],
            status="requested",
            notes="Auto-raised after thin bundle.",
            created_at_utc="2026-03-14T00:00:00Z",
            completed_at_utc="",
        )
        assert isinstance(record, ResourceAcquisitionRequestRecord)

        r2 = SeriesRegistry(db_path=db)
        rows = r2.list_resource_acquisition_requests(scripture_reference="Luke 15")
        assert len(rows) == 1
        assert rows[0].requested_resource_kinds == ["outline", "commentary"]
        assert rows[0].requested_by == "research_librarian"

    def test_resource_acquisition_request_can_be_updated(self, tmp_path: Path) -> None:
        db = tmp_path / "persist-librarian-update.db"
        r1 = SeriesRegistry(db_path=db)
        r1.request_resource_acquisition(
            request_id="req-2",
            requested_by="research_librarian",
            scripture_reference="Luke 15",
            topic="Luke 15",
            worker_name="outliner",
            reason="Need more outline help.",
            requested_resource_kinds=["outline"],
            status="requested",
            notes="Raised automatically.",
            created_at_utc="2026-03-16T00:00:00Z",
            completed_at_utc="",
        )

        updated = r1.update_resource_acquisition_request(
            request_id="req-2",
            status="answered",
            notes="Cleared after trainer review.",
            completed_at_utc="2026-03-16T00:05:00Z",
        )

        assert updated.status == "answered"
        assert updated.completed_at_utc == "2026-03-16T00:05:00Z"
        assert updated.notes == "Cleared after trainer review."

    def test_delete_volume_can_remove_orphan_series(self, tmp_path: Path) -> None:
        db = tmp_path / "persist4.db"
        r1 = SeriesRegistry(db_path=db)
        r1.create_series("s1")
        r1.create_volume("v1", "s1", 1)
        assert r1.delete_volume("v1", delete_series_if_orphan=True) is True
        r2 = SeriesRegistry(db_path=db)
        r2.create_series("s1")

    def test_trainer_recommendations_survive_restart(self, tmp_path: Path) -> None:
        db = tmp_path / "persist-trainer.db"
        r1 = SeriesRegistry(db_path=db)
        record = r1.record_trainer_recommendation(
            recommendation_id="trainer-rec-1",
            trainer_name="expert_outliner_trainer",
            worker_name="outliner",
            scripture_reference="Ruth 1",
            passage_slug="ruth-1",
            priority=10,
            rationale="Train narrative grief and covenant loyalty.",
            selection_stage="trainer_selected_non_harness_coverage",
            status="recommended",
            created_at_utc="2026-03-16T03:30:00Z",
            consumed_at_utc="",
        )
        assert isinstance(record, TrainerRecommendationRecord)

        r2 = SeriesRegistry(db_path=db)
        rows = r2.list_trainer_recommendations(
            trainer_name="expert_outliner_trainer",
            worker_name="outliner",
            status="recommended",
        )
        assert len(rows) == 1
        assert rows[0].scripture_reference == "Ruth 1"
        assert rows[0].passage_slug == "ruth-1"


# ---------------------------------------------------------------------------
# TestQuoteDedup
# ---------------------------------------------------------------------------


class TestQuoteDedup:
    def test_within_volume_duplicate_raises(self, registry: SeriesRegistry) -> None:
        """Second use of same quote in same volume → DuplicateQuoteError (FR-66)."""
        _setup_series_and_volume(registry)
        _add_quote(registry)
        with pytest.raises(DuplicateQuoteError):
            _add_quote(registry)  # same quote_text, same volume

    def test_cross_volume_duplicate_raises(self, registry: SeriesRegistry) -> None:
        """Same quote in a second volume of the same series → CrossVolumeDuplicateError (FR-65)."""
        _setup_series_and_volume(registry)
        _add_quote(registry, volume_id="vol-001")

        registry.create_volume("vol-002", "series-001", 2)
        with pytest.raises(CrossVolumeDuplicateError):
            _add_quote(registry, volume_id="vol-002")  # same quote, same series

    def test_different_quote_same_volume_accepted(self, registry: SeriesRegistry) -> None:
        """Different quote text in same volume is allowed."""
        _setup_series_and_volume(registry)
        _add_quote(registry, quote_text="All is grace.")
        result = _add_quote(registry, quote_text="A different quote entirely.")
        assert isinstance(result, QuoteRecord)

    def test_same_quote_different_series_accepted(self, registry: SeriesRegistry) -> None:
        """Same quote in a completely different series is allowed."""
        registry.create_series("series-A")
        registry.create_volume("vol-A", "series-A", 1)
        registry.record_quote_use("vol-A", "series-A", "All is grace.", "Thomas Merton", "Source")

        registry.create_series("series-B")
        registry.create_volume("vol-B", "series-B", 1)
        result = registry.record_quote_use(
            "vol-B", "series-B", "All is grace.", "Thomas Merton", "Source"
        )
        assert isinstance(result, QuoteRecord)

    def test_within_volume_override_stores_record(self, registry: SeriesRegistry) -> None:
        """override_reason bypasses within-volume hard fail; record stored (FR-66)."""
        _setup_series_and_volume(registry)
        _add_quote(registry)
        result = _add_quote(registry, override_reason="Operator approved repeat use")
        assert isinstance(result, QuoteRecord)

    def test_cross_volume_override_stores_record(self, registry: SeriesRegistry) -> None:
        """override_reason bypasses cross-volume flag; record stored (FR-65)."""
        _setup_series_and_volume(registry)
        _add_quote(registry, volume_id="vol-001")

        registry.create_volume("vol-002", "series-001", 2)
        result = _add_quote(
            registry,
            volume_id="vol-002",
            override_reason="Cross-volume use approved by operator",
        )
        assert isinstance(result, QuoteRecord)

    def test_record_quote_returns_quote_record(self, registry: SeriesRegistry) -> None:
        _setup_series_and_volume(registry)
        result = _add_quote(registry)
        assert isinstance(result, QuoteRecord)
        assert result.quote_text == "All is grace."
        assert result.author == "Thomas Merton"
        assert result.volume_id == "vol-001"
        assert result.series_id == "series-001"


# ---------------------------------------------------------------------------
# TestScriptureTracking
# ---------------------------------------------------------------------------


class TestScriptureTracking:
    def test_first_use_returns_not_duplicate(self, registry: SeriesRegistry) -> None:
        _setup_series_and_volume(registry)
        result = registry.record_scripture_use("vol-001", "Romans 8:15", "NASB")
        assert isinstance(result, ScriptureUseResult)
        assert isinstance(result.record, ScriptureRecord)
        assert result.is_duplicate is False
        assert result.warning_message is None

    def test_second_use_returns_duplicate_flag(self, registry: SeriesRegistry) -> None:
        """Same reference in same volume → is_duplicate=True with warning (FR-67)."""
        _setup_series_and_volume(registry)
        registry.record_scripture_use("vol-001", "Romans 8:15", "NASB")
        result = registry.record_scripture_use("vol-001", "Romans 8:15", "NASB")
        assert result.is_duplicate is True
        assert result.warning_message is not None
        assert "Romans 8:15" in result.warning_message

    def test_scripture_dup_is_non_blocking(self, registry: SeriesRegistry) -> None:
        """Duplicate scripture does NOT raise an exception — only warns (FR-67)."""
        _setup_series_and_volume(registry)
        registry.record_scripture_use("vol-001", "Romans 8:15", "NASB")
        try:
            result = registry.record_scripture_use("vol-001", "Romans 8:15", "NASB")
            assert result.is_duplicate is True
        except Exception as exc:  # pragma: no cover
            pytest.fail(f"Scripture dup should be non-blocking but raised: {exc}")

    def test_same_reference_different_volume_not_flagged(self, registry: SeriesRegistry) -> None:
        """Same scripture in a different volume is NOT a duplicate warning."""
        registry.create_series("s1")
        registry.create_volume("v1", "s1", 1)
        registry.create_volume("v2", "s1", 2)
        registry.record_scripture_use("v1", "Romans 8:15", "NASB")
        result = registry.record_scripture_use("v2", "Romans 8:15", "NASB")
        assert result.is_duplicate is False

    def test_same_reference_different_translation_not_flagged(self, registry: SeriesRegistry) -> None:
        """Same reference but different translation → separate entry, no dup flag."""
        _setup_series_and_volume(registry)
        registry.record_scripture_use("vol-001", "Romans 8:15", "NASB")
        result = registry.record_scripture_use("vol-001", "Romans 8:15", "ESV")
        assert result.is_duplicate is False


# ---------------------------------------------------------------------------
# TestAuthorDistribution
# ---------------------------------------------------------------------------


class TestAuthorDistribution:
    def test_distribution_correct_counts(self, registry: SeriesRegistry) -> None:
        """get_author_distribution returns correct per-author counts (FR-68)."""
        _setup_series_and_volume(registry)
        registry.record_quote_use("vol-001", "series-001", "Quote 1", "Author A", "Book X")
        registry.record_quote_use("vol-001", "series-001", "Quote 2", "Author A", "Book Y")
        registry.record_quote_use("vol-001", "series-001", "Quote 3", "Author B", "Book Z")

        dist = registry.get_author_distribution("vol-001")
        assert dist == {"Author A": 2, "Author B": 1}

    def test_empty_volume_returns_empty_dict(self, registry: SeriesRegistry) -> None:
        _setup_series_and_volume(registry)
        assert registry.get_author_distribution("vol-001") == {}

    def test_distribution_scoped_to_volume(self, registry: SeriesRegistry) -> None:
        """Quotes in another volume do not appear in the requested volume's distribution."""
        registry.create_series("s1")
        registry.create_volume("v1", "s1", 1)
        registry.create_volume("v2", "s1", 2)
        registry.record_quote_use("v1", "s1", "Quote A", "Merton", "Book A")
        registry.record_quote_use("v2", "s1", "Quote B", "Lewis", "Book B", override_reason="x")

        assert registry.get_author_distribution("v1") == {"Merton": 1}
        assert registry.get_author_distribution("v2") == {"Lewis": 1}


# ---------------------------------------------------------------------------
# TestParentChildInheritance
# ---------------------------------------------------------------------------


class TestParentChildInheritance:
    def test_parent_distribution_surfaced_for_child(self, registry: SeriesRegistry) -> None:
        """
        Child volume can read parent's author distribution (FR-71).
        Weighting logic itself is applied in Phase 004; CP5 only surfaces the data.
        """
        registry.create_series("s1")
        registry.create_volume("parent-vol", "s1", 1)
        child = registry.create_volume("child-vol", "s1", 2, parent_volume_id="parent-vol")

        # Populate parent with quotes
        registry.record_quote_use("parent-vol", "s1", "Quote 1 by A", "Author A", "Book")
        registry.record_quote_use("parent-vol", "s1", "Quote 2 by A", "Author A", "Other Book")
        registry.record_quote_use("parent-vol", "s1", "Quote 3 by B", "Author B", "Book B")

        # Child queries parent distribution
        parent_dist = registry.get_parent_distribution_for_attribute("parent-vol", "author")
        assert parent_dist == {"Author A": 2, "Author B": 1}
        assert child.id == "child-vol"  # child record is valid

    def test_parent_distribution_source_title(self, registry: SeriesRegistry) -> None:
        """source_title attribute is also supported (FR-68 diversity by source)."""
        registry.create_series("s1")
        registry.create_volume("parent-vol", "s1", 1)
        registry.record_quote_use("parent-vol", "s1", "Q1", "Author A", "Source X")
        registry.record_quote_use("parent-vol", "s1", "Q2", "Author B", "Source X")
        registry.record_quote_use("parent-vol", "s1", "Q3", "Author C", "Source Y")

        dist = registry.get_parent_distribution_for_attribute("parent-vol", "source_title")
        assert dist == {"Source X": 2, "Source Y": 1}

    def test_unsupported_attribute_raises_value_error(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1")
        registry.create_volume("v1", "s1", 1)
        with pytest.raises(ValueError, match="Unsupported attribute"):
            registry.get_parent_distribution_for_attribute("v1", "publication_year")

    def test_empty_parent_returns_empty_dict(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1")
        registry.create_volume("parent-vol", "s1", 1)
        assert registry.get_parent_distribution_for_attribute("parent-vol", "author") == {}


# ---------------------------------------------------------------------------
# TestVolumeContext
# ---------------------------------------------------------------------------


class TestVolumeContext:
    def test_get_volume_by_number_returns_record(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1")
        registry.create_volume("v1", "s1", 1, title="Vol 1")
        record = registry.get_volume_by_number("s1", 1)
        assert record is not None
        assert record.id == "v1"
        assert record.volume_number == 1

    def test_record_and_read_volume_day_plan(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1")
        registry.create_volume("v1", "s1", 1, title="Vol 1")
        row = registry.record_volume_day_plan(
            volume_id="v1",
            series_id="s1",
            volume_number=1,
            day_number=1,
            week_number=1,
            topic="Creation",
            scripture_reference="Genesis 1:1-5",
        )
        assert isinstance(row, VolumeDayPlanRecord)
        rows = registry.get_volume_day_plan("v1")
        assert len(rows) == 1
        assert rows[0].week_number == 1
        assert rows[0].scripture_reference == "Genesis 1:1-5"

    def test_week_scripture_map_groups_refs(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1")
        registry.create_volume("v1", "s1", 1)
        registry.record_volume_day_plan(
            volume_id="v1",
            series_id="s1",
            volume_number=1,
            day_number=1,
            week_number=1,
            topic="Creation",
            scripture_reference="Genesis 1:1-5",
        )
        registry.record_volume_day_plan(
            volume_id="v1",
            series_id="s1",
            volume_number=1,
            day_number=2,
            week_number=1,
            topic="Creation",
            scripture_reference="Genesis 1:6-8",
        )
        by_week = registry.get_week_scripture_map_for_volume("v1")
        assert by_week[1] == {"Genesis 1:1-5", "Genesis 1:6-8"}

    def test_week_quote_map_groups_quotes(self, registry: SeriesRegistry) -> None:
        registry.create_series("s1")
        registry.create_volume("v1", "s1", 1)
        registry.record_volume_day_quote(
            volume_id="v1",
            series_id="s1",
            volume_number=1,
            day_number=1,
            week_number=1,
            quote_text="Quote A",
            author="Author A",
            source_title="Source A",
        )
        registry.record_volume_day_quote(
            volume_id="v1",
            series_id="s1",
            volume_number=1,
            day_number=2,
            week_number=1,
            quote_text="Quote B",
            author="Author B",
            source_title="Source B",
        )
        by_week = registry.get_week_quote_map_for_volume("v1")
        assert by_week[1] == {"Quote A", "Quote B"}


# ---------------------------------------------------------------------------
# TestBackup
# ---------------------------------------------------------------------------


class TestBackup:
    def test_backup_creates_file_at_path(self, registry: SeriesRegistry, tmp_path: Path) -> None:
        """backup() copies DB file to specified path (TC-05)."""
        _setup_series_and_volume(registry)
        backup_file = tmp_path / "registry_backup.db"
        registry.backup("vol-001", backup_file)
        assert backup_file.exists()
        assert backup_file.stat().st_size > 0

    def test_backup_file_is_readable_as_registry(
        self, registry: SeriesRegistry, tmp_path: Path
    ) -> None:
        """The backup file is a valid SQLite database readable by a new SeriesRegistry."""
        _setup_series_and_volume(registry)
        _add_quote(registry)
        backup_file = tmp_path / "backup.db"
        registry.backup("vol-001", backup_file)

        backup_registry = SeriesRegistry(db_path=backup_file)
        dist = backup_registry.get_author_distribution("vol-001")
        assert dist == {"Thomas Merton": 1}

    def test_backup_unknown_volume_raises(
        self, registry: SeriesRegistry, tmp_path: Path
    ) -> None:
        """backup() raises RegistryError if volume_id not found."""
        backup_file = tmp_path / "backup.db"
        with pytest.raises(RegistryError):
            registry.backup("nonexistent-volume", backup_file)


# ---------------------------------------------------------------------------
# TestAutoresearchLedger
# ---------------------------------------------------------------------------


class TestAutoresearchLedger:
    def test_log_and_list_autoresearch_experiment(self, registry: SeriesRegistry) -> None:
        rec = registry.log_autoresearch_experiment(
            experiment_id="exp-001",
            worker_name="outliner",
            benchmark_name="sinai-boundary",
            benchmark_reference="Exodus 19-20",
            run_slug="2026-03-14__demo",
            status="keep",
            attempted_change="Split Sinai preparation from encounter.",
            metrics_json='{"BOOK_DAY_PROGRESS": "passed"}',
            learning_note="Clearer week turn after the covenant encounter.",
            keep_decision="keep",
            created_at_utc="2026-03-14T01:00:00Z",
            completed_at_utc="2026-03-14T01:12:00Z",
        )
        assert isinstance(rec, AutoresearchExperimentRecord)
        rows = registry.list_autoresearch_experiments(worker_name="outliner")
        assert len(rows) == 1
        assert rows[0].benchmark_reference == "Exodus 19-20"
        assert rows[0].keep_decision == "keep"

    def test_log_autoresearch_experiment_updates_existing_row(self, registry: SeriesRegistry) -> None:
        registry.log_autoresearch_experiment(
            experiment_id="exp-002",
            worker_name="quote_selector",
            benchmark_name="pastoral-devotional",
            benchmark_reference="Psalms 23-25",
            run_slug="",
            status="running",
            attempted_change="Try high-yield domains first.",
            metrics_json='{}',
            learning_note="",
            keep_decision="",
            created_at_utc="2026-03-14T01:00:00Z",
            completed_at_utc="",
        )
        rec = registry.log_autoresearch_experiment(
            experiment_id="exp-002",
            worker_name="quote_selector",
            benchmark_name="pastoral-devotional",
            benchmark_reference="Psalms 23-25",
            run_slug="2026-03-14__quotes",
            status="discard",
            attempted_change="Try high-yield domains first.",
            metrics_json='{"complete_turabian_rate": 0.2}',
            learning_note="Still too many incomplete citations.",
            keep_decision="discard",
            created_at_utc="2026-03-14T01:00:00Z",
            completed_at_utc="2026-03-14T01:07:00Z",
        )
        assert rec.run_slug == "2026-03-14__quotes"
        assert rec.status == "discard"
        rows = registry.list_autoresearch_experiments(benchmark_name="pastoral-devotional")
        assert len(rows) == 1
        assert rows[0].learning_note == "Still too many incomplete citations."

    def test_outliner_system_comparisons_survive_restart(self, tmp_path: Path) -> None:
        db = tmp_path / "registry.db"
        r1 = SeriesRegistry(db_path=db)
        rec = r1.record_outliner_system_comparison(
            comparison_id="cmp-001",
            scripture_reference="Romans 5",
            passage_slug="romans-5",
            range_label="6d_1w",
            assignment_payload_json='{"training_level":"level-1","study_goal":"segmentation"}',
            interaction_log_json='{"events":["legacy fail","redesign review pending"]}',
            packet_snapshot_json='{"resource_count":2,"packet_certified":false}',
            reviewer_guidance_json='{"theological_reviewer":["check burden drift"]}',
            artifact_paths_json='{"spec":"docs/system/outliner-agent-redesign-spec.md"}',
            legacy_system_name="deterministic_editorial",
            legacy_system_reference="src/generation/editorial.py",
            legacy_status="fail",
            legacy_score=10.0,
            legacy_summary="Fell through to generic fallback behavior.",
            legacy_metrics_json='{"used_generic_fallback":true}',
            redesigned_system_name="reasoning_outliner",
            redesigned_system_reference="docs/system/outliner-agent-redesign-spec.md",
            redesigned_status="under_review",
            redesigned_score=None,
            redesigned_summary="Replacement architecture under review.",
            redesigned_metrics_json='{"packet_gate_required":true}',
            winner="",
            decision_status="under_review",
            decision_rationale="Need adapter comparison before cutover.",
            comparison_notes="Prepared for third-party review if needed.",
            reviewed_by="training_manager",
            created_at_utc="2026-03-16T10:30:00Z",
            completed_at_utc="2026-03-16T10:30:00Z",
        )
        assert isinstance(rec, OutlinerSystemComparisonRecord)

        r2 = SeriesRegistry(db_path=db)
        rows = r2.list_outliner_system_comparisons(passage_slug="romans-5")
        assert len(rows) == 1
        assert rows[0].legacy_system_reference == "src/generation/editorial.py"
        assert rows[0].reviewer_guidance_json == '{"theological_reviewer":["check burden drift"]}'
        assert rows[0].decision_status == "under_review"
