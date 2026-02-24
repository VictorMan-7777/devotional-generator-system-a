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
    day_number: int
    attempt_number: int       # attempt that produced the signal
    signal: str               # "auto_rewrite" | "human_review"
    failed_check_ids: list[str]


class ValidationSummary(BaseModel):
    total_checks: int
    passed: int
    failed: int
    rewrite_events: list[RewriteEvent] = []


class PipelineResult(BaseModel):
    book: DevotionalBook
    pdf_bytes: bytes          # b"" when export was blocked
    validation_summary: ValidationSummary
    export_gate_result: ExportabilityResult
    registry_volume_id: str
