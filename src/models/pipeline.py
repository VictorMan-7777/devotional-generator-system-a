"""pipeline.py — Phase 004.D pipeline result types.

Pydantic models for generation orchestration layer results.
No business logic; data containers only.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from src.models.devotional import DevotionalBook


class ExportabilityResult(BaseModel):
    exportable: bool
    blocked_reason: Optional[str] = None
    warnings: list[str] = []


class RewriteEvent(BaseModel):
    day_number: Optional[int] = None
    attempt_number: int       # attempt that produced the signal
    signal: str               # "auto_rewrite" | "human_review"
    failed_check_ids: list[str]
    scope: str = "day"        # "day" | "book"
    target_day_numbers: list[int] = []


class ValidationSummary(BaseModel):
    total_checks: int
    passed: int
    failed: int
    rewrite_events: list[RewriteEvent] = []
    attempted_remedies: list[str] = []


class EditorialDayPlanRow(BaseModel):
    day_number: int
    week_number: int
    topic: str
    scripture_reference: str
    study_window_reference: str = ""


class EditorialDayBriefRecord(BaseModel):
    day_number: int
    week_number: int
    scripture_reference: str
    study_window_reference: str = ""
    key_verse_reference: str = ""
    day_title: str
    focus_clause: str
    pastoral_burden: str
    genre: str
    scene_summary: str
    theological_lane: str
    application_lane: str
    forbidden_drifts: list[str] = []
    key_terms: list[str] = []


class EditorialWeekPlan(BaseModel):
    week_number: int
    title: str
    days: list[int]
    movement_summary: str


class PassageResourceRecord(BaseModel):
    purpose: str = "shared"
    role_targets: list[str] = []
    source_title: str
    author: str = ""
    source_type: str = ""
    excerpt_text: str = ""
    note: str = ""
    relevance_score: float = 0.0


class PassageResourceBundle(BaseModel):
    topic: str
    scripture_reference: str
    prepared_at_utc: str
    shared_resources: list[PassageResourceRecord] = []
    outliner_resources: list[PassageResourceRecord] = []
    exposition_resources: list[PassageResourceRecord] = []
    # Per-day exposition packages: key is 1-based day number.
    # When populated, the exposition writer uses these day-specific resources
    # instead of the flat exposition_resources list.  The outliner always uses
    # outliner_resources which cover the full study arc.
    exposition_resources_by_day: dict[int, list[PassageResourceRecord]] = {}


class EditorialBuildArtifact(BaseModel):
    topic: str
    num_days: int
    source_reference: str | None = None
    week_count: int
    passage_resources: PassageResourceBundle | None = None
    day_plan: list[EditorialDayPlanRow]
    day_briefs: list[EditorialDayBriefRecord]
    week_plans: list[EditorialWeekPlan]


class PipelineResult(BaseModel):
    book: DevotionalBook
    pdf_bytes: bytes          # b"" when export was blocked
    validation_summary: ValidationSummary
    export_gate_result: ExportabilityResult
    registry_volume_id: str
    editorial_build: EditorialBuildArtifact
