"""SQLite-backed socket adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

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
from src.persistence.socket import DatabaseSocket
from src.registry.registry import SeriesRegistry


class SQLiteRegistrySocket(DatabaseSocket):
    """Adapter that delegates socket operations to existing SeriesRegistry."""

    def __init__(self, db_path: Path) -> None:
        self._registry = SeriesRegistry(db_path=db_path)

    def create_series(self, series_id: str, title: Optional[str] = None) -> None:
        self._registry.create_series(series_id, title=title)

    def create_volume(
        self,
        volume_id: str,
        series_id: str,
        volume_number: int,
        title: Optional[str] = None,
        parent_volume_id: Optional[str] = None,
    ) -> VolumeRecord:
        return self._registry.create_volume(
            volume_id=volume_id,
            series_id=series_id,
            volume_number=volume_number,
            title=title,
            parent_volume_id=parent_volume_id,
        )

    def get_volume_by_number(self, series_id: str, volume_number: int) -> Optional[VolumeRecord]:
        return self._registry.get_volume_by_number(series_id=series_id, volume_number=volume_number)

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
        return self._registry.record_quote_use(
            volume_id=volume_id,
            series_id=series_id,
            quote_text=quote_text,
            author=author,
            source_title=source_title,
            publication_year=publication_year,
            override_reason=override_reason,
        )

    def record_scripture_use(
        self,
        volume_id: str,
        reference: str,
        translation: str,
    ) -> ScriptureRecord:
        # Socket contract returns the stored record. Duplicate warning metadata
        # remains available through direct SeriesRegistry APIs.
        return self._registry.record_scripture_use(
            volume_id=volume_id,
            reference=reference,
            translation=translation,
        ).record

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
        return self._registry.record_volume_day_plan(
            volume_id=volume_id,
            series_id=series_id,
            volume_number=volume_number,
            day_number=day_number,
            week_number=week_number,
            topic=topic,
            scripture_reference=scripture_reference,
        )

    def get_volume_day_plan(self, volume_id: str) -> list[VolumeDayPlanRecord]:
        return self._registry.get_volume_day_plan(volume_id)

    def get_week_scripture_map_for_volume(self, volume_id: str) -> dict[int, set[str]]:
        return self._registry.get_week_scripture_map_for_volume(volume_id)

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
        return self._registry.record_volume_day_quote(
            volume_id=volume_id,
            series_id=series_id,
            volume_number=volume_number,
            day_number=day_number,
            week_number=week_number,
            quote_text=quote_text,
            author=author,
            source_title=source_title,
        )

    def get_week_quote_map_for_volume(self, volume_id: str) -> dict[int, set[str]]:
        return self._registry.get_week_quote_map_for_volume(volume_id)

    def delete_volume(self, volume_id: str, *, delete_series_if_orphan: bool = False) -> bool:
        return self._registry.delete_volume(
            volume_id=volume_id,
            delete_series_if_orphan=delete_series_if_orphan,
        )

    def seed_review_section(
        self,
        *,
        run_slug: str,
        day_number: int,
        section_name: str,
        original_payload_json: str,
        original_preview: str,
    ) -> ReviewSectionRecord:
        return self._registry.seed_review_section(
            run_slug=run_slug,
            day_number=day_number,
            section_name=section_name,
            original_payload_json=original_payload_json,
            original_preview=original_preview,
        )

    def list_review_sections(self, run_slug: str) -> list[ReviewSectionRecord]:
        return self._registry.list_review_sections(run_slug)

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
        return self._registry.save_review_edit(
            run_slug=run_slug,
            day_number=day_number,
            section_name=section_name,
            edited_payload_json=edited_payload_json,
            edited_html=edited_html,
            edited_plain=edited_plain,
            edit_note=edit_note,
            edited_at_utc=edited_at_utc,
        )

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
        return self._registry.save_review_decision(
            run_slug=run_slug,
            day_number=day_number,
            section_name=section_name,
            approval_decision=approval_decision,
            operator_note=operator_note,
            reviewed_by=reviewed_by,
            decision_source=decision_source,
            reviewed_at_utc=reviewed_at_utc,
            approved_payload_json=approved_payload_json,
            approved_preview=approved_preview,
        )

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
        return self._registry.log_autoresearch_experiment(
            experiment_id=experiment_id,
            worker_name=worker_name,
            benchmark_name=benchmark_name,
            benchmark_reference=benchmark_reference,
            run_slug=run_slug,
            status=status,
            attempted_change=attempted_change,
            metrics_json=metrics_json,
            learning_note=learning_note,
            keep_decision=keep_decision,
            created_at_utc=created_at_utc,
            completed_at_utc=completed_at_utc,
        )

    def list_autoresearch_experiments(
        self,
        *,
        worker_name: Optional[str] = None,
        benchmark_name: Optional[str] = None,
    ) -> list[AutoresearchExperimentRecord]:
        return self._registry.list_autoresearch_experiments(
            worker_name=worker_name,
            benchmark_name=benchmark_name,
        )

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
        return self._registry.request_resource_acquisition(
            request_id=request_id,
            requested_by=requested_by,
            scripture_reference=scripture_reference,
            topic=topic,
            worker_name=worker_name,
            reason=reason,
            requested_resource_kinds=requested_resource_kinds,
            status=status,
            notes=notes,
            created_at_utc=created_at_utc,
            completed_at_utc=completed_at_utc,
        )

    def list_resource_acquisition_requests(
        self,
        *,
        requested_by: Optional[str] = None,
        worker_name: Optional[str] = None,
        scripture_reference: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[ResourceAcquisitionRequestRecord]:
        return self._registry.list_resource_acquisition_requests(
            requested_by=requested_by,
            worker_name=worker_name,
            scripture_reference=scripture_reference,
            status=status,
        )

    def update_resource_acquisition_request(
        self,
        *,
        request_id: str,
        status: str,
        notes: str,
        completed_at_utc: str,
    ) -> ResourceAcquisitionRequestRecord:
        return self._registry.update_resource_acquisition_request(
            request_id=request_id,
            status=status,
            notes=notes,
            completed_at_utc=completed_at_utc,
        )

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
        return self._registry.record_trainer_recommendation(
            recommendation_id=recommendation_id,
            trainer_name=trainer_name,
            worker_name=worker_name,
            scripture_reference=scripture_reference,
            passage_slug=passage_slug,
            priority=priority,
            rationale=rationale,
            selection_stage=selection_stage,
            status=status,
            created_at_utc=created_at_utc,
            consumed_at_utc=consumed_at_utc,
        )

    def list_trainer_recommendations(
        self,
        *,
        trainer_name: Optional[str] = None,
        worker_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[TrainerRecommendationRecord]:
        return self._registry.list_trainer_recommendations(
            trainer_name=trainer_name,
            worker_name=worker_name,
            status=status,
        )

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
        return self._registry.record_outliner_system_comparison(
            comparison_id=comparison_id,
            scripture_reference=scripture_reference,
            passage_slug=passage_slug,
            range_label=range_label,
            assignment_payload_json=assignment_payload_json,
            interaction_log_json=interaction_log_json,
            packet_snapshot_json=packet_snapshot_json,
            reviewer_guidance_json=reviewer_guidance_json,
            artifact_paths_json=artifact_paths_json,
            legacy_system_name=legacy_system_name,
            legacy_system_reference=legacy_system_reference,
            legacy_status=legacy_status,
            legacy_score=legacy_score,
            legacy_summary=legacy_summary,
            legacy_metrics_json=legacy_metrics_json,
            redesigned_system_name=redesigned_system_name,
            redesigned_system_reference=redesigned_system_reference,
            redesigned_status=redesigned_status,
            redesigned_score=redesigned_score,
            redesigned_summary=redesigned_summary,
            redesigned_metrics_json=redesigned_metrics_json,
            winner=winner,
            decision_status=decision_status,
            decision_rationale=decision_rationale,
            comparison_notes=comparison_notes,
            reviewed_by=reviewed_by,
            created_at_utc=created_at_utc,
            completed_at_utc=completed_at_utc,
        )

    def list_outliner_system_comparisons(
        self,
        *,
        scripture_reference: Optional[str] = None,
        passage_slug: Optional[str] = None,
        decision_status: Optional[str] = None,
    ) -> list[OutlinerSystemComparisonRecord]:
        return self._registry.list_outliner_system_comparisons(
            scripture_reference=scripture_reference,
            passage_slug=passage_slug,
            decision_status=decision_status,
        )
