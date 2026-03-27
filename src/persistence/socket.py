"""Persistence socket contract for generator-facing storage operations."""

from __future__ import annotations

from typing import Protocol, Optional

from src.models.registry import (
    AutoresearchExperimentRecord,
    OutlinerSystemComparisonRecord,
    QuoteRecord,
    ResourceAcquisitionRequestRecord,
    ReviewSectionRecord,
    ScriptureRecord,
    TrainerRecommendationRecord,
    VolumeDayPlanRecord,
    VolumeDayQuoteRecord,
    VolumeRecord,
)


class DatabaseSocket(Protocol):
    """Minimal generator-facing persistence port.

    This is intentionally scoped to operations used by generation pipeline and
    current registry-backed flows. Additional migration/export methods can be
    added in follow-on phases without changing pipeline call sites.
    """

    def create_series(self, series_id: str, title: Optional[str] = None) -> None:
        ...

    def create_volume(
        self,
        volume_id: str,
        series_id: str,
        volume_number: int,
        title: Optional[str] = None,
        parent_volume_id: Optional[str] = None,
    ) -> VolumeRecord:
        ...

    def get_volume_by_number(self, series_id: str, volume_number: int) -> Optional[VolumeRecord]:
        ...

    def record_quote_use(
        self,
        volume_id: str,
        series_id: str,
        quote_text: str,
        author: str,
        source_title: str,
        publication_year: Optional[int] = None,
        override_reason: Optional[str] = None,
    ) -> QuoteRecord:
        ...

    def record_scripture_use(
        self,
        volume_id: str,
        reference: str,
        translation: str,
    ) -> ScriptureRecord:
        ...

    def record_volume_day_plan(
        self,
        *,
        volume_id: str,
        series_id: str,
        volume_number: int,
        day_number: int,
        week_number: int,
        topic: str,
        scripture_reference: str,
    ) -> VolumeDayPlanRecord:
        ...

    def get_volume_day_plan(self, volume_id: str) -> list[VolumeDayPlanRecord]:
        ...

    def get_week_scripture_map_for_volume(self, volume_id: str) -> dict[int, set[str]]:
        ...

    def record_volume_day_quote(
        self,
        *,
        volume_id: str,
        series_id: str,
        volume_number: int,
        day_number: int,
        week_number: int,
        quote_text: str,
        author: str,
        source_title: str,
    ) -> VolumeDayQuoteRecord:
        ...

    def get_week_quote_map_for_volume(self, volume_id: str) -> dict[int, set[str]]:
        ...

    def delete_volume(self, volume_id: str, *, delete_series_if_orphan: bool = False) -> bool:
        ...

    def seed_review_section(
        self,
        *,
        run_slug: str,
        day_number: int,
        section_name: str,
        original_payload_json: str,
        original_preview: str,
    ) -> ReviewSectionRecord:
        ...

    def list_review_sections(self, run_slug: str) -> list[ReviewSectionRecord]:
        ...

    def save_review_edit(
        self,
        *,
        run_slug: str,
        day_number: int,
        section_name: str,
        edited_payload_json: str,
        edited_html: str,
        edited_plain: str,
        edit_note: str,
        edited_at_utc: str,
    ) -> ReviewSectionRecord:
        ...

    def save_review_decision(
        self,
        *,
        run_slug: str,
        day_number: int,
        section_name: str,
        approval_decision: str,
        operator_note: str,
        reviewed_by: str,
        decision_source: Optional[str],
        reviewed_at_utc: str,
        approved_payload_json: str,
        approved_preview: str,
    ) -> ReviewSectionRecord:
        ...

    def log_autoresearch_experiment(
        self,
        *,
        experiment_id: str,
        worker_name: str,
        benchmark_name: str,
        benchmark_reference: str,
        run_slug: str,
        status: str,
        attempted_change: str,
        metrics_json: str,
        learning_note: str,
        keep_decision: str,
        created_at_utc: str,
        completed_at_utc: str,
    ) -> AutoresearchExperimentRecord:
        ...

    def list_autoresearch_experiments(
        self,
        *,
        worker_name: Optional[str] = None,
        benchmark_name: Optional[str] = None,
    ) -> list[AutoresearchExperimentRecord]:
        ...

    def request_resource_acquisition(
        self,
        *,
        request_id: str,
        requested_by: str,
        scripture_reference: str,
        topic: str,
        worker_name: str,
        reason: str,
        requested_resource_kinds: list[str],
        status: str,
        notes: str,
        created_at_utc: str,
        completed_at_utc: str,
    ) -> ResourceAcquisitionRequestRecord:
        ...

    def list_resource_acquisition_requests(
        self,
        *,
        requested_by: Optional[str] = None,
        worker_name: Optional[str] = None,
        scripture_reference: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[ResourceAcquisitionRequestRecord]:
        ...

    def update_resource_acquisition_request(
        self,
        *,
        request_id: str,
        status: str,
        notes: str,
        completed_at_utc: str,
    ) -> ResourceAcquisitionRequestRecord:
        ...

    def record_trainer_recommendation(
        self,
        *,
        recommendation_id: str,
        trainer_name: str,
        worker_name: str,
        scripture_reference: str,
        passage_slug: str,
        priority: int,
        rationale: str,
        selection_stage: str,
        status: str,
        created_at_utc: str,
        consumed_at_utc: str,
    ) -> TrainerRecommendationRecord:
        ...

    def list_trainer_recommendations(
        self,
        *,
        trainer_name: Optional[str] = None,
        worker_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[TrainerRecommendationRecord]:
        ...

    def record_outliner_system_comparison(
        self,
        *,
        comparison_id: str,
        scripture_reference: str,
        passage_slug: str,
        range_label: str,
        assignment_payload_json: str,
        interaction_log_json: str,
        packet_snapshot_json: str,
        reviewer_guidance_json: str,
        artifact_paths_json: str,
        legacy_system_name: str,
        legacy_system_reference: str,
        legacy_status: str,
        legacy_score: float | None,
        legacy_summary: str,
        legacy_metrics_json: str,
        redesigned_system_name: str,
        redesigned_system_reference: str,
        redesigned_status: str,
        redesigned_score: float | None,
        redesigned_summary: str,
        redesigned_metrics_json: str,
        winner: str,
        decision_status: str,
        decision_rationale: str,
        comparison_notes: str,
        reviewed_by: str,
        created_at_utc: str,
        completed_at_utc: str,
    ) -> OutlinerSystemComparisonRecord:
        ...

    def list_outliner_system_comparisons(
        self,
        *,
        scripture_reference: Optional[str] = None,
        passage_slug: Optional[str] = None,
        decision_status: Optional[str] = None,
    ) -> list[OutlinerSystemComparisonRecord]:
        ...
