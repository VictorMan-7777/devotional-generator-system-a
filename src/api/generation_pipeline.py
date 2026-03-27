"""generation_pipeline.py — Phase 004.D generation orchestration entry point.

Drives mock section generation, validates via Phase 004 validators, retries
on AUTO_REWRITE signal, records to registry, renders, and exports PDF.

No LLM calls. No real RAG. Deterministic mocks only.
"""
from __future__ import annotations

import inspect
import uuid
from typing import Callable, Optional

from src.api.export_gate import ExportGate
from src.generation.editorial import (
    differentiate_day_briefs,
    EditorialDayBrief,
    build_editorial_artifact,
    build_editorial_day_brief,
)
from src.generation.generators import MockSectionGenerator, SectionGeneratorInterface
from src.models.devotional import DevotionalBook, DevotionalInput, OutputMode
from src.models.pipeline import (
    PassageResourceBundle,
    PipelineResult,
    RewriteEvent,
    ValidationSummary,
)
from src.persistence.config import PersistenceConfig
from src.persistence.factory import create_socket
from src.persistence.paths import default_registry_db_path
from src.persistence.socket import DatabaseSocket
from src.rag.research_librarian import prepare_passage_resource_bundle
from src.scripture.planner import (
    plan_scripture_day_references,
    select_daily_key_verses_reference,
    suggest_study_window_size,
)
from src.validation.book_quality import validate_devotional_book
from src.validation.orchestrator import validate_daily_devotional


def _auto_day_plan(
    *,
    topic: str,
    scripture_reference: str | None,
    num_days: int,
) -> list[dict[str, str]] | None:
    reference = (scripture_reference or "").strip() or topic.strip()
    if not reference:
        return None
    refs = plan_scripture_day_references(
        reference=reference,
        num_days=num_days,
        max_verses_per_day=suggest_study_window_size(
            reference=reference,
            num_days=num_days,
        ),
    )
    return [
        {
            "topic": topic,
            "scripture_reference": select_daily_key_verses_reference(reference=ref, max_key_verses=2),
            "study_window_reference": ref,
        }
        for ref in refs
    ]


def _generator_build_editorial_brief(
    *,
    generator: SectionGeneratorInterface,
    topic: str,
    day_number: int,
    scripture_reference: str | None,
    study_window_reference: str | None = None,
    passage_resources: PassageResourceBundle | None = None,
) -> EditorialDayBrief:
    builder = getattr(generator, "build_editorial_brief", None)
    if callable(builder):
        sig = inspect.signature(builder)
        kwargs = {
            "scripture_reference": scripture_reference,
        }
        if "study_window_reference" in sig.parameters:
            kwargs["study_window_reference"] = study_window_reference
        if "passage_resources" in sig.parameters:
            kwargs["passage_resources"] = passage_resources
        return builder(topic, day_number, **kwargs)
    ref = (scripture_reference or topic).strip() or f"Day {day_number}"
    study_ref = (study_window_reference or ref).strip() or ref
    return build_editorial_day_brief(
        day_number=day_number,
        scripture_reference=ref,
        scripture_text=study_ref,
        study_window_reference=study_ref,
        passage_resources=passage_resources,
    )


def _generator_generate_day(
    *,
    generator: SectionGeneratorInterface,
    topic: str,
    day_number: int,
    attempt_number: int,
    scripture_reference: str | None,
    forbidden_quote_texts: set[str],
    editorial_brief: EditorialDayBrief,
    passage_resources: PassageResourceBundle | None = None,
):
    sig = inspect.signature(generator.generate_day)
    kwargs = {
        "topic": topic,
        "day_number": day_number,
        "attempt_number": attempt_number,
        "scripture_reference": scripture_reference,
        "forbidden_quote_texts": forbidden_quote_texts,
    }
    if "editorial_brief" in sig.parameters:
        kwargs["editorial_brief"] = editorial_brief
    if "passage_resources" in sig.parameters:
        kwargs["passage_resources"] = passage_resources
    return generator.generate_day(**kwargs)


def generate_devotional(
    topic: str,
    num_days: int,
    scripture_reference: Optional[str] = None,
    day_plan: Optional[list[dict[str, str]]] = None,
    output_mode: OutputMode = OutputMode.PERSONAL,
    generator: Optional[SectionGeneratorInterface] = None,
    registry: Optional[DatabaseSocket] = None,
    series_id: Optional[str] = None,
    volume_number: int = 1,
    volume_id: Optional[str] = None,
    quote_exclusions_by_day: Optional[dict[int, set[str]]] = None,
    require_planned_scripture: bool = False,
    checkpoint_callback: Optional[Callable[[str, dict], None]] = None,
) -> PipelineResult:
    """Generate a validated devotional book and return PDF bytes + metadata.

    Args:
        topic: Theme for the devotional series.
        num_days: Number of days to generate (1–366).
        scripture_reference: Optional anchor scripture; passed from caller.
            Mock generators ignore this parameter.
        output_mode: PERSONAL allows PENDING sections with warnings;
            PUBLISH_READY blocks export if any section is PENDING.
        generator: Section generator; defaults to MockSectionGenerator().
        registry: Persistence socket; defaults to in-memory sqlite-backed socket.
        series_id: Series identifier; auto-generated UUID if not provided.
        volume_number: Volume number for this run; does not imply series membership.
        require_planned_scripture: When True, fail fast unless scripture/day plan
            can provide all requested sections.

    Returns:
        PipelineResult containing the DevotionalBook, PDF bytes (or b"" if
        blocked), ValidationSummary with rewrite events, ExportabilityResult,
        and the registry volume ID.
    """
    if generator is None:
        generator = MockSectionGenerator()
    if registry is None:
        registry = create_socket(PersistenceConfig.sqlite_memory(), component="registry")
    if series_id is None:
        series_id = str(uuid.uuid4())
    if volume_number <= 0:
        raise ValueError("volume_number must be > 0")

    def _emit_checkpoint(stage: str, payload: dict) -> None:
        if checkpoint_callback is None:
            return
        checkpoint_callback(stage, payload)

    if day_plan:
        effective_day_plan = day_plan
    else:
        try:
            effective_day_plan = _auto_day_plan(
                topic=topic,
                scripture_reference=scripture_reference,
                num_days=num_days,
            )
        except ValueError as exc:
            if require_planned_scripture:
                source_label = (scripture_reference or topic or "").strip()
                if not (scripture_reference or "").strip():
                    raise ValueError(
                        f"Only 0 scriptures found for topic '{topic}', {num_days} needed."
                    ) from exc
                raise ValueError(
                    f"Scripture planning failed for '{source_label}': {exc}"
                ) from exc
            effective_day_plan = None

    if require_planned_scripture:
        if not effective_day_plan:
            raise ValueError(
                f"Only 0 scriptures found for topic '{topic}', {num_days} needed."
            )
        if len(effective_day_plan) < num_days:
            raise ValueError(
                f"Only {len(effective_day_plan)} scriptures found for topic '{topic}', "
                f"{num_days} needed."
            )

    resolved_volume_id = volume_id or str(uuid.uuid4())

    registry.create_series(series_id, title=topic)
    volume_record = registry.create_volume(
        resolved_volume_id,
        series_id,
        volume_number=volume_number,
        title=topic,
    )
    active_volume_id = volume_record.id

    def _day_config(day_num: int) -> tuple[str, str | None, str | None, set[str]]:
        day_cfg = (
            effective_day_plan[day_num - 1]
            if effective_day_plan and (day_num - 1) < len(effective_day_plan)
            else {}
        )
        day_topic = str(day_cfg.get("topic") or topic)
        day_scripture_reference = str(
            day_cfg.get("scripture_reference") or (scripture_reference or "")
        ).strip() or None
        study_window_reference = str(
            day_cfg.get("study_window_reference")
            or day_cfg.get("scripture_reference")
            or (scripture_reference or "")
        ).strip() or None
        day_quote_exclusions = (
            set(quote_exclusions_by_day.get(day_num, set()))
            if quote_exclusions_by_day
            else set()
        )
        day_quote_exclusions.update(
            set(day_cfg.get("forbidden_quote_texts", []))
            if isinstance(day_cfg.get("forbidden_quote_texts"), list)
            else set()
        )
        return day_topic, day_scripture_reference, study_window_reference, day_quote_exclusions

    shared_scripture_reference = (scripture_reference or "").strip() or None
    if shared_scripture_reference is None and effective_day_plan:
        for row in effective_day_plan:
            candidate = str(row.get("scripture_reference") or "").strip()
            if candidate:
                shared_scripture_reference = candidate
                break
    passage_resources: PassageResourceBundle | None = None
    if shared_scripture_reference:
        passage_resources = prepare_passage_resource_bundle(
            topic=topic,
            scripture_reference=shared_scripture_reference,
            db_path=default_registry_db_path(),
            num_days=num_days,
            day_plan=effective_day_plan,
        )

    editorial_briefs_by_day: dict[int, EditorialDayBrief] = {}
    editorial_day_plan_rows: list[dict[str, str]] = []
    for day_num in range(1, num_days + 1):
        day_topic, day_scripture_reference, day_study_window_reference, _ = _day_config(day_num)
        brief = _generator_build_editorial_brief(
            generator=generator,
            topic=day_topic,
            day_number=day_num,
            scripture_reference=day_scripture_reference,
            study_window_reference=day_study_window_reference,
            passage_resources=passage_resources,
        )
        editorial_briefs_by_day[day_num] = brief
        editorial_day_plan_rows.append(
            {
                "day_number": str(day_num),
                "week_number": str(brief.week_number),
                "topic": day_topic,
                "scripture_reference": brief.scripture_reference,
                "study_window_reference": brief.study_window_reference,
            }
        )

    differentiated_briefs = differentiate_day_briefs(
        [editorial_briefs_by_day[day_num] for day_num in range(1, num_days + 1)]
    )
    editorial_briefs_by_day = {brief.day_number: brief for brief in differentiated_briefs}

    editorial_build = build_editorial_artifact(
        topic=topic,
        num_days=num_days,
        source_reference=scripture_reference,
        day_plan_rows=editorial_day_plan_rows,
        day_briefs=differentiated_briefs,
        passage_resources=passage_resources,
    )
    _emit_checkpoint(
        "outline_ready",
        {
            "topic": topic,
            "num_days": num_days,
            "source_reference": scripture_reference,
            "editorial_build": editorial_build.model_dump(mode="json"),
        },
    )

    def _generate_validated_day(
        day_num: int,
        *,
        attempt_start: int = 1,
        max_attempts: int = 2,
        extra_forbidden_quotes: set[str] | None = None,
    ):
        day_topic, day_scripture_reference, _day_study_window_reference, day_quote_exclusions = _day_config(day_num)
        if extra_forbidden_quotes:
            day_quote_exclusions.update(extra_forbidden_quotes)
        final_day = None
        final_assessments = None

        for attempt in range(attempt_start, attempt_start + max_attempts):
            quote_state = None
            if hasattr(generator, "snapshot_quote_state"):
                quote_state = generator.snapshot_quote_state()
            day = _generator_generate_day(
                generator=generator,
                topic=day_topic,
                day_number=day_num,
                attempt_number=attempt,
                scripture_reference=day_scripture_reference,
                forbidden_quote_texts=day_quote_exclusions,
                editorial_brief=editorial_briefs_by_day[day_num],
                passage_resources=passage_resources,
            )
            assessments = validate_daily_devotional(
                day, grounding_map=None, prayer_trace_map=None
            )
            failures = [a for a in assessments if a.result == "fail"]

            if not failures:
                final_day = day
                final_assessments = assessments
                break

            if quote_state is not None and hasattr(generator, "restore_quote_state"):
                generator.restore_quote_state(quote_state)

            signal = "auto_rewrite" if attempt == attempt_start else "human_review"
            rewrite_events.append(
                RewriteEvent(
                    day_number=day_num,
                    attempt_number=attempt,
                    signal=signal,
                    failed_check_ids=[a.check_id for a in failures],
                    scope="day",
                    target_day_numbers=[day_num],
                )
            )

            if attempt == (attempt_start + max_attempts - 1):
                final_day = day
                final_assessments = assessments

        assert final_day is not None, f"Day {day_num}: generator loop did not set final_day"
        assert final_assessments is not None
        _emit_checkpoint(
            "day_complete",
            {
                "day_number": day_num,
                "attempt_start": attempt_start,
                "day": final_day.model_dump(mode="json"),
                "assessments": [assessment.model_dump(mode="json") for assessment in final_assessments],
            },
        )
        return final_day, final_assessments

    days = []
    day_assessments_by_day: dict[int, list] = {}
    rewrite_events: list[RewriteEvent] = []

    for day_num in range(1, num_days + 1):
        final_day, final_assessments = _generate_validated_day(day_num)
        day_assessments_by_day[day_num] = final_assessments
        days.append(final_day)
        partial_book = DevotionalBook(
            id=str(uuid.uuid4()),
            input=DevotionalInput(
                topic=topic,
                num_days=len(days),
                output_mode=output_mode,
            ),
            days=list(days),
            series_id=series_id,
            volume_number=volume_number,
        )
        partial_book_findings = validate_devotional_book(partial_book)
        _emit_checkpoint(
            "day_unification",
            {
                "day_number": day_num,
                "status": "passed" if not partial_book_findings else "failed",
                "findings": [
                    finding.model_dump(mode="json")
                    for finding in partial_book_findings
                    if day_num in finding.day_numbers
                ],
            },
        )
        current_week = editorial_briefs_by_day[day_num].week_number
        next_week = (
            editorial_briefs_by_day[day_num + 1].week_number
            if day_num < num_days
            else None
        )
        if next_week != current_week:
            week_days = [
                day.day_number
                for day in days
                if editorial_briefs_by_day[day.day_number].week_number == current_week
            ]
            week_findings = [
                finding.model_dump(mode="json")
                for finding in partial_book_findings
                if any(day in week_days for day in finding.day_numbers)
            ]
            _emit_checkpoint(
                "week_unification",
                {
                    "week_number": current_week,
                    "day_numbers": week_days,
                    "status": "passed" if not week_findings else "failed",
                    "findings": week_findings,
                },
            )

    book = DevotionalBook(
        id=str(uuid.uuid4()),
        input=DevotionalInput(
            topic=topic,
            num_days=num_days,
            output_mode=output_mode,
        ),
        days=days,
        series_id=series_id,
        volume_number=volume_number,
    )

    book_findings = validate_devotional_book(book)
    _emit_checkpoint(
        "book_unification",
        {
            "status": "passed" if not book_findings else "failed",
            "findings": [finding.model_dump(mode="json") for finding in book_findings],
        },
    )
    if book_findings:
        impacted_days = sorted(
            {
                day_number
                for finding in book_findings
                for day_number in finding.day_numbers
            }
        ) or [day.day_number for day in book.days]
        rewrite_events.append(
            RewriteEvent(
                attempt_number=1,
                signal="auto_rewrite",
                failed_check_ids=[finding.check_id for finding in book_findings],
                scope="book",
                target_day_numbers=impacted_days,
            )
        )
        for day_number in impacted_days:
            original_day = book.days[day_number - 1]
            if hasattr(generator, "release_quote"):
                generator.release_quote(
                    author=original_day.timeless_wisdom.author,
                    source_title=original_day.timeless_wisdom.source_title,
                    quote_text=original_day.timeless_wisdom.quote_text,
                )
            regenerated_day, regenerated_assessments = _generate_validated_day(
                day_number,
                attempt_start=3,
                max_attempts=1,
                extra_forbidden_quotes={original_day.timeless_wisdom.quote_text},
            )
            days[day_number - 1] = regenerated_day
            day_assessments_by_day[day_number] = regenerated_assessments

        book = book.model_copy(update={"days": days})
        book_findings = validate_devotional_book(book)
        if book_findings:
            rewrite_events.append(
                RewriteEvent(
                    attempt_number=2,
                    signal="human_review",
                    failed_check_ids=[finding.check_id for finding in book_findings],
                    scope="book",
                    target_day_numbers=sorted(
                        {
                            day_number
                            for finding in book_findings
                            for day_number in finding.day_numbers
                        }
                    ),
                )
            )

    seen_quote_keys: set[tuple[str, str, str]] = set()
    seen_quote_texts: set[str] = set()
    for idx, day in enumerate(days):
        quote_key = (
            str(day.timeless_wisdom.author or "").strip(),
            str(day.timeless_wisdom.source_title or "").strip(),
            str(day.timeless_wisdom.quote_text or "").strip(),
        )
        if quote_key in seen_quote_keys:
            regenerated_day = None
            regenerated_assessments = None
            forbidden_quotes = set(seen_quote_texts)
            forbidden_quotes.add(str(day.timeless_wisdom.quote_text or "").strip())
            for attempt in range(4, 6):
                candidate_day, candidate_assessments = _generate_validated_day(
                    day.day_number,
                    attempt_start=attempt,
                    max_attempts=1,
                    extra_forbidden_quotes=forbidden_quotes,
                )
                candidate_key = (
                    str(candidate_day.timeless_wisdom.author or "").strip(),
                    str(candidate_day.timeless_wisdom.source_title or "").strip(),
                    str(candidate_day.timeless_wisdom.quote_text or "").strip(),
                )
                if candidate_key not in seen_quote_keys:
                    regenerated_day = candidate_day
                    regenerated_assessments = candidate_assessments
                    break
                forbidden_quotes.add(str(candidate_day.timeless_wisdom.quote_text or "").strip())
            if regenerated_day is None or regenerated_assessments is None:
                raise RuntimeError(
                    f"Day {day.day_number}: unable to resolve duplicate quote within volume."
                )
            days[idx] = regenerated_day
            day_assessments_by_day[day.day_number] = regenerated_assessments
            day = regenerated_day
            quote_key = (
                str(day.timeless_wisdom.author or "").strip(),
                str(day.timeless_wisdom.source_title or "").strip(),
                str(day.timeless_wisdom.quote_text or "").strip(),
            )
        seen_quote_keys.add(quote_key)
        seen_quote_texts.add(str(day.timeless_wisdom.quote_text or "").strip())

    book = book.model_copy(update={"days": days})

    for day in book.days:
        tw = day.timeless_wisdom
        registry.record_quote_use(
            volume_id=active_volume_id,
            series_id=series_id,
            quote_text=tw.quote_text,
            author=tw.author,
            source_title=tw.source_title,
            publication_year=tw.publication_year,
        )
        registry.record_scripture_use(
            volume_id=active_volume_id,
            reference=day.scripture.reference,
            translation=day.scripture.translation,
        )

    all_assessments = [
        assessment
        for day_number in sorted(day_assessments_by_day)
        for assessment in day_assessments_by_day[day_number]
    ]
    all_assessments.extend(book_findings)

    export_gate_result = ExportGate().check_exportability(book, output_mode)

    # Standard generation now stops at review. Final PDFs are produced only
    # after review decisions are applied via apply_decisions_and_export.py.
    pdf_bytes = b""

    total = len(all_assessments)
    passed = sum(1 for a in all_assessments if a.result == "pass")
    failed = sum(1 for a in all_assessments if a.result == "fail")
    attempted_remedies: list[str] = []
    if rewrite_events:
        attempted_remedies.append("automatic targeted regeneration of affected days/clusters")

    return PipelineResult(
        book=book,
        pdf_bytes=pdf_bytes,
        validation_summary=ValidationSummary(
            total_checks=total,
            passed=passed,
            failed=failed,
            rewrite_events=rewrite_events,
            attempted_remedies=attempted_remedies,
        ),
        export_gate_result=export_gate_result,
        registry_volume_id=active_volume_id,
        editorial_build=editorial_build,
    )
