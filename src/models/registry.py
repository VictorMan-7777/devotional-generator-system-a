from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QuoteRecord(BaseModel):
    id: str  # UUID
    volume_id: str
    series_id: str
    quote_text: str
    author: str
    source_title: str
    publication_year: Optional[int] = None
    added_at: datetime


class ScriptureRecord(BaseModel):
    id: str  # UUID
    volume_id: str
    reference: str  # e.g. "Romans 8:15"
    translation: str
    added_at: datetime


class VolumeRecord(BaseModel):
    id: str  # UUID
    series_id: str
    volume_number: int
    title: Optional[str] = None
    parent_volume_id: Optional[str] = None
    created_at: datetime


class VolumeDayPlanRecord(BaseModel):
    id: str  # UUID
    volume_id: str
    series_id: str
    volume_number: int
    day_number: int
    week_number: int
    topic: str
    scripture_reference: str
    created_at: datetime


class VolumeDayQuoteRecord(BaseModel):
    id: str  # UUID
    volume_id: str
    series_id: str
    volume_number: int
    day_number: int
    week_number: int
    quote_text: str
    author: str
    source_title: str
    created_at: datetime


class ReviewSectionRecord(BaseModel):
    run_slug: str
    day_number: int
    section_name: str
    original_payload_json: str = "{}"
    original_preview: str = ""
    edited_payload_json: str = ""
    edited_html: str = ""
    edited_plain: str = ""
    edit_note: str = ""
    edited_at_utc: str = ""
    approval_decision: str = ""
    operator_note: str = ""
    reviewed_by: str = ""
    decision_source: str = ""
    reviewed_at_utc: str = ""
    approved_payload_json: str = ""
    approved_preview: str = ""


class AutoresearchExperimentRecord(BaseModel):
    experiment_id: str
    worker_name: str
    benchmark_name: str
    benchmark_reference: str = ""
    run_slug: str = ""
    status: str = ""
    attempted_change: str = ""
    metrics_json: str = "{}"
    learning_note: str = ""
    keep_decision: str = ""
    created_at_utc: str = ""
    completed_at_utc: str = ""


class ResourceAcquisitionRequestRecord(BaseModel):
    request_id: str
    requested_by: str
    scripture_reference: str
    topic: str = ""
    worker_name: str = ""
    reason: str = ""
    requested_resource_kinds: list[str] = []
    status: str = ""
    notes: str = ""
    created_at_utc: str = ""
    completed_at_utc: str = ""


class TrainerRecommendationRecord(BaseModel):
    recommendation_id: str
    trainer_name: str
    worker_name: str
    scripture_reference: str
    passage_slug: str = ""
    priority: int = 0
    rationale: str = ""
    selection_stage: str = ""
    status: str = ""
    created_at_utc: str = ""
    consumed_at_utc: str = ""


class OutlinerSystemComparisonRecord(BaseModel):
    comparison_id: str
    scripture_reference: str
    passage_slug: str = ""
    range_label: str = ""
    assignment_payload_json: str = "{}"
    interaction_log_json: str = "{}"
    packet_snapshot_json: str = "{}"
    reviewer_guidance_json: str = "{}"
    artifact_paths_json: str = "{}"
    legacy_system_name: str = ""
    legacy_system_reference: str = ""
    legacy_status: str = ""
    legacy_score: Optional[float] = None
    legacy_summary: str = ""
    legacy_metrics_json: str = "{}"
    redesigned_system_name: str = ""
    redesigned_system_reference: str = ""
    redesigned_status: str = ""
    redesigned_score: Optional[float] = None
    redesigned_summary: str = ""
    redesigned_metrics_json: str = "{}"
    winner: str = ""
    decision_status: str = ""
    decision_rationale: str = ""
    comparison_notes: str = ""
    reviewed_by: str = ""
    created_at_utc: str = ""
    completed_at_utc: str = ""
