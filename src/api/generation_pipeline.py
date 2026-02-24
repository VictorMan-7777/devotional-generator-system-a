"""generation_pipeline.py — Phase 004.D generation orchestration entry point.

Drives mock section generation, validates via Phase 004 validators, retries
on AUTO_REWRITE signal, records to registry, renders, and exports PDF.

No LLM calls. No real RAG. Deterministic mocks only.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from src.api.export_gate import ExportGate
from src.api.pdf_export import export_pdf
from src.generation.generators import MockSectionGenerator, SectionGeneratorInterface
from src.models.devotional import DevotionalBook, DevotionalInput, OutputMode
from src.models.pipeline import (
    PipelineResult,
    RewriteEvent,
    ValidationSummary,
)
from src.registry.registry import SeriesRegistry
from src.rendering.engine import DocumentRenderer
from src.validation.orchestrator import validate_daily_devotional


def generate_devotional(
    topic: str,
    num_days: int,
    scripture_reference: Optional[str] = None,
    output_mode: OutputMode = OutputMode.PERSONAL,
    generator: Optional[SectionGeneratorInterface] = None,
    registry: Optional[SeriesRegistry] = None,
    series_id: Optional[str] = None,
) -> PipelineResult:
    """Generate a validated devotional book and return PDF bytes + metadata.

    Args:
        topic: Theme for the devotional series.
        num_days: Number of days to generate (1–7).
        scripture_reference: Optional anchor scripture; passed from caller.
            Mock generators ignore this parameter.
        output_mode: PERSONAL allows PENDING sections with warnings;
            PUBLISH_READY blocks export if any section is PENDING.
        generator: Section generator; defaults to MockSectionGenerator().
        registry: Series registry; defaults to in-memory SeriesRegistry.
        series_id: Series identifier; auto-generated UUID if not provided.

    Returns:
        PipelineResult containing the DevotionalBook, PDF bytes (or b"" if
        blocked), ValidationSummary with rewrite events, ExportabilityResult,
        and the registry volume ID.
    """
    if generator is None:
        generator = MockSectionGenerator()
    if registry is None:
        registry = SeriesRegistry(db_path=Path(":memory:"))
    if series_id is None:
        series_id = str(uuid.uuid4())

    volume_id = str(uuid.uuid4())

    registry.create_series(series_id, title=topic)
    registry.create_volume(volume_id, series_id, volume_number=1, title=topic)

    days = []
    all_assessments = []
    rewrite_events: list[RewriteEvent] = []

    for day_num in range(1, num_days + 1):
        final_day = None
        final_assessments = None

        for attempt in range(1, 3):  # attempts 1 and 2; max 2 per day
            day = generator.generate_day(topic, day_num, attempt_number=attempt)
            assessments = validate_daily_devotional(
                day, grounding_map=None, prayer_trace_map=None
            )
            failures = [a for a in assessments if a.result == "fail"]

            if not failures:
                final_day = day
                final_assessments = assessments
                break

            # Record the rewrite signal for this failed attempt.
            signal = "auto_rewrite" if attempt == 1 else "human_review"
            rewrite_events.append(
                RewriteEvent(
                    day_number=day_num,
                    attempt_number=attempt,
                    signal=signal,
                    failed_check_ids=[a.check_id for a in failures],
                )
            )

            if attempt == 2:
                # Accept day as-is after second failure.
                final_day = day
                final_assessments = assessments

        assert final_day is not None, f"Day {day_num}: generator loop did not set final_day"
        assert final_assessments is not None

        # Record usage in registry from the accepted day.
        tw = final_day.timeless_wisdom
        registry.record_quote_use(
            volume_id=volume_id,
            series_id=series_id,
            quote_text=tw.quote_text,
            author=tw.author,
            source_title=tw.source_title,
            publication_year=tw.publication_year,
        )
        registry.record_scripture_use(
            volume_id=volume_id,
            reference=final_day.scripture.reference,
            translation=final_day.scripture.translation,
        )

        all_assessments.extend(final_assessments)
        days.append(final_day)

    book = DevotionalBook(
        id=str(uuid.uuid4()),
        input=DevotionalInput(
            topic=topic,
            num_days=num_days,
            output_mode=output_mode,
        ),
        days=days,
        series_id=series_id,
        volume_number=1,
    )

    export_gate_result = ExportGate().check_exportability(book, output_mode)

    if export_gate_result.exportable:
        doc = DocumentRenderer().render(book, output_mode)
        pdf_bytes = export_pdf(doc, output_mode.value)
    else:
        pdf_bytes = b""

    total = len(all_assessments)
    passed = sum(1 for a in all_assessments if a.result == "pass")
    failed = sum(1 for a in all_assessments if a.result == "fail")

    return PipelineResult(
        book=book,
        pdf_bytes=pdf_bytes,
        validation_summary=ValidationSummary(
            total_checks=total,
            passed=passed,
            failed=failed,
            rewrite_events=rewrite_events,
        ),
        export_gate_result=export_gate_result,
        registry_volume_id=volume_id,
    )
