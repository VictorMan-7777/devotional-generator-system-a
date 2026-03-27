from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.citations.quote_citations import (
    has_strong_quote_citation,
    merge_quote_citation_fields,
    quote_attribution_line,
    quote_footnote,
)
from src.api.export_gate import ExportGate
from src.interfaces.rag import QuoteCandidate
from src.models.devotional import DevotionalBook, OutputMode
from src.rag.catalog import QuoteCatalog
from src.scripture.retrieval import ScriptureResult, ScriptureRetriever
from src.scripture.source_policy import ScriptureSourcePolicy, scripture_exact_text_compatible
from src.validation.orchestrator import validate_daily_devotional


@dataclass(frozen=True)
class CsvRunInput:
    topic: str
    num_days: int
    scripture_reference: str | None
    title: str | None
    series_id: str | None
    volume_number: int
    volume_id: str | None
    parent_volume_id: str | None


@dataclass(frozen=True)
class DayPlanEntry:
    day_number: int
    week: int
    topic: str
    scripture_reference: str
    notes: str | None = None


def _pick(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        if key in row and str(row[key]).strip():
            return str(row[key]).strip()
    return None


def load_run_input_from_csv(csv_path: Path, row_number: int = 1) -> CsvRunInput:
    if row_number <= 0:
        raise ValueError("row_number must be >= 1")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        raise ValueError(f"No rows found in CSV: {csv_path}")
    if row_number > len(rows):
        raise ValueError(f"Requested row {row_number} but CSV has {len(rows)} rows")

    row = {str(k).strip(): str(v).strip() for k, v in rows[row_number - 1].items() if k is not None}
    topic = _pick(row, "topic", "Theme", "theme")
    if not topic:
        raise ValueError("CSV row must include topic")

    num_days_raw = _pick(row, "num_days", "days", "day_count", "length_days") or "6"
    num_days = int(num_days_raw)
    if num_days <= 0:
        raise ValueError("num_days must be > 0")

    volume_number = int(_pick(row, "volume_number", "volume", "vol_number") or "1")
    if volume_number <= 0:
        raise ValueError("volume_number must be > 0")

    return CsvRunInput(
        topic=topic,
        num_days=num_days,
        scripture_reference=_pick(row, "scripture_reference", "scripture", "anchor_scripture"),
        title=_pick(row, "title", "book_title"),
        series_id=_pick(row, "series_id", "series"),
        volume_number=volume_number,
        volume_id=_pick(row, "volume_id"),
        parent_volume_id=_pick(row, "parent_volume_id", "parent_volume"),
    )


def load_competition_outline_from_csv(
    csv_path: Path,
    *,
    series_id: str | None = None,
    volume_number: int = 1,
) -> tuple[CsvRunInput, list[DayPlanEntry]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        raise ValueError(f"No rows found in competition outline CSV: {csv_path}")

    required = {"Day", "Week", "Attribute", "Scripture", "Theme/Focus"}
    missing = [k for k in required if k not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"Competition outline missing required columns: {missing}")

    day_plan: list[DayPlanEntry] = []
    for row in rows:
        day_raw = str(row.get("Day") or "").strip()
        week_raw = str(row.get("Week") or "").strip()
        scripture = str(row.get("Scripture") or "").strip()
        if not day_raw or not week_raw or not scripture:
            continue
        day_num = int(day_raw)
        week_num = int(week_raw)
        attribute = str(row.get("Attribute") or "").strip()
        focus = str(row.get("Theme/Focus") or "").strip()
        topic = f"{attribute} | {focus}".strip(" |")
        day_plan.append(
            DayPlanEntry(
                day_number=day_num,
                week=week_num,
                topic=topic or "Devotional Focus",
                scripture_reference=scripture,
                notes=str(row.get("Notes") or "").strip() or None,
            )
        )

    day_plan.sort(key=lambda d: d.day_number)
    if not day_plan:
        raise ValueError("Competition outline yielded no usable day rows.")

    input_row = CsvRunInput(
        topic=f"Competition Volume {volume_number}",
        num_days=len(day_plan),
        scripture_reference=None,
        title=csv_path.stem,
        series_id=series_id,
        volume_number=volume_number,
        volume_id=None,
        parent_volume_id=None,
    )
    return input_row, day_plan


def _section_preview(day: Any, section_name: str) -> str:
    section = getattr(day, section_name, None)
    if section is None:
        return ""
    if section_name == "timeless_wisdom":
        quote = getattr(section, "quote_text", "")
        author = getattr(section, "author", "")
        source = getattr(section, "source_title", "")
        footnote = quote_footnote(
            author=author,
            source_title=source,
            publication_year=getattr(section, "publication_year", None),
            citation_locator=(
                getattr(section, "citation_locator", "") or getattr(section, "page_or_url", "")
            ),
            publisher=getattr(section, "publisher", ""),
            publication_city=getattr(section, "publication_city", ""),
        )
        if getattr(section, "language_modernized", False) and getattr(section, "modernization_label", ""):
            footnote = f"{footnote} ({getattr(section, 'modernization_label')})"
        citation_ready = has_strong_quote_citation(
            citation_locator=(
                getattr(section, "citation_locator", "") or getattr(section, "page_or_url", "")
            ),
            publisher=getattr(section, "publisher", ""),
            publication_city=getattr(section, "publication_city", ""),
        )
        parts = [f"\"{quote}\"" if quote else ""]
        attribution = quote_attribution_line(author, source).replace("- ", "", 1)
        if attribution:
            parts.append(f"- {attribution}")
        if getattr(section, "language_modernized", False):
            original_quote = str(getattr(section, "original_quote_text", "")).strip()
            if original_quote and original_quote != str(quote).strip():
                parts.append(f"Original wording: \"{original_quote}\"")
        if source:
            label = (
                "Turabian Footnote"
                if citation_ready
                else "Competition blocker (incomplete Turabian footnote)"
            )
            parts.append(f"{label}: {footnote}")
        return "\n".join(p for p in parts if p)
    if section_name == "scripture":
        ref = getattr(section, "reference", "")
        text = getattr(section, "text", "")
        return "\n\n".join(p for p in [ref, text] if p)
    if section_name in {"exposition", "prayer", "sending_prompt"}:
        return str(getattr(section, "text", "")).strip()
    if section_name == "be_still":
        return "\n".join(f"- {str(p).strip()}" for p in getattr(section, "prompts", []) if str(p).strip())
    if section_name == "action_steps":
        connector = str(getattr(section, "connector_phrase", "")).strip()
        items = "\n".join(f"- {str(i).strip()}" for i in getattr(section, "items", []) if str(i).strip())
        return "\n".join(part for part in [connector, items] if part)
    if section_name == "day7":
        before = str(getattr(section, "before_service", "")).strip()
        track_a = "\n".join(f"- {str(i).strip()}" for i in getattr(section, "after_service_track_a", []))
        track_b = "\n".join(f"- {str(i).strip()}" for i in getattr(section, "after_service_track_b", []))
        return "\n\n".join(p for p in [before, "Track A", track_a, "Track B", track_b] if p)
    return ""


def build_pending_sections_and_previews(
    book: DevotionalBook,
    *,
    include_agent_validated: bool = False,
) -> tuple[list[str], dict[str, str], dict[str, dict[str, str]]]:
    pending: list[str] = []
    previews: dict[str, str] = {}
    section_meta: dict[str, dict[str, str]] = {}
    section_names = [
        "timeless_wisdom",
        "scripture",
        "exposition",
        "be_still",
        "action_steps",
        "prayer",
        "sending_prompt",
        "day7",
    ]
    for day in book.days:
        for section_name in section_names:
            section = getattr(day, section_name, None)
            if section is None:
                continue
            status = str(getattr(section, "approval_status", "")).lower()
            if status == "approved":
                continue
            verification_status = str(getattr(section, "verification_status", "")).strip().lower()
            if not include_agent_validated and verification_status == "agent_validated":
                continue
            pending_item = f"day {day.day_number} — {section_name}"
            pending.append(pending_item)
            key = f"{day.day_number}:{section_name}"
            previews[key] = _section_preview(day, section_name)
            section_meta[key] = {
                "verification_status": str(getattr(section, "verification_status", "")),
                "retrieval_source": str(getattr(section, "retrieval_source", "")),
                "approval_status": str(getattr(section, "approval_status", "")),
                "grounding_map_id": str(getattr(section, "grounding_map_id", "")),
                "prayer_trace_map_id": str(getattr(section, "prayer_trace_map_id", "")),
                "retrieval_reference": str(getattr(section, "retrieval_reference", "")),
                "retrieved_at_utc": str(getattr(section, "retrieved_at_utc", "")),
                "copyright_notice": str(getattr(section, "copyright_notice", "")),
                "source_access_policy": str(getattr(section, "source_access_policy", "")),
                "text_cache_status": str(getattr(section, "text_cache_status", "")),
                "cache_expires_at_utc": str(getattr(section, "cache_expires_at_utc", "")),
            }
    return pending, previews, section_meta


def build_agent_validation_report(
    book: DevotionalBook,
    *,
    validator_agents: list[str],
    scripture_validator_import: Path | None = None,
) -> dict[str, Any]:
    source_policy = ScriptureSourcePolicy.from_env()

    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()

    def _norm_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip().lower()

    def _scripture_tokens(value: Any) -> list[str]:
        text = str(value or "")
        text = re.sub(r"[“”‘’]", "'", text)
        text = re.sub(r"\[[^\]]+\]", lambda m: f" {m.group(0)[1:-1]} ", text)
        lines = []
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split()).strip()
            if not line:
                continue
            if (
                len(line.split()) <= 8
                and not re.search(r"[.!?;,:\"']", line)
                and line == line.title()
            ):
                continue
            lines.append(line)
        cleaned = " ".join(lines).lower()
        cleaned = re.sub(r"\blord\b", "lord", cleaned)
        cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
        return [token for token in cleaned.split() if token]

    def _is_subsequence(shorter: list[str], longer: list[str]) -> bool:
        if not shorter:
            return False
        idx = 0
        for token in longer:
            if idx < len(shorter) and token == shorter[idx]:
                idx += 1
                if idx == len(shorter):
                    return True
        return idx == len(shorter)

    def _scripture_text_match(left: Any, right: Any) -> bool:
        left_tokens = _scripture_tokens(left)
        right_tokens = _scripture_tokens(right)
        return left_tokens == right_tokens or _is_subsequence(left_tokens, right_tokens) or _is_subsequence(right_tokens, left_tokens)

    def _scripture_validation(day: Any) -> dict[str, Any]:
        original = str(getattr(day.scripture, "retrieval_source", "") or "").strip()
        original_text = str(getattr(day.scripture, "text", "") or "").strip()
        reference = str(getattr(day.scripture, "reference", "") or "").strip()
        translation = str(getattr(day.scripture, "translation", "") or "NASB").strip() or "NASB"
        original_norm = _norm(original)
        known_sources = {"bolls_life", "api_bible", "operator_import"}
        if original_norm not in known_sources:
            return {
                "status": "failed",
                "original_source": original,
                "validator_source": "unknown",
                "separate_source": False,
                "comparison_mode": "unavailable",
                "exact_text_compatible": False,
                "generated_text": original_text,
                "validator_text": "",
                "reference": reference,
                "translation": translation,
                "text_match": None,
                "discrepancy": None,
            }
        retriever = ScriptureRetriever(
            api_bible_key=os.getenv("API_BIBLE_KEY"),
            api_bible_bible_id=os.getenv("API_BIBLE_BIBLE_ID"),
            source_policy=source_policy,
        )
        available_sources: list[str] = ["bolls_life"]
        if os.getenv("API_BIBLE_KEY"):
            available_sources.append("api_bible")
        if scripture_validator_import is not None:
            available_sources.append("operator_import")
        validator = source_policy.choose_validator_source(
            original_source=original_norm,
            available_sources=available_sources,
        )
        if not validator:
            # Unknown or missing source means we cannot prove independent validation.
            return {
                "status": "blocked_config",
                "original_source": original,
                "validator_source": "unavailable",
                "separate_source": False,
                "comparison_mode": "unavailable",
                "exact_text_compatible": False,
                "generated_text": original_text,
                "validator_text": "",
                "reference": reference,
                "translation": translation,
                "text_match": None,
                "discrepancy": None,
                "details": (
                    f"No independent validator source available for original source '{original or 'unknown'}'. "
                    "Adjust DEVG scripture source policy or provide validator credentials/import."
                ),
            }
        result: ScriptureResult | None = None
        if validator == "api_bible":
            result = retriever._try_api_bible(reference=reference, translation=translation)
        elif validator == "bolls_life":
            try:
                parsed = retriever._parse_reference(reference)
                result = retriever._try_bolls_life(parsed=parsed, translation=translation)
            except Exception:
                result = None
        elif validator == "operator_import" and scripture_validator_import is not None:
            result = retriever._load_operator_import(
                reference=reference,
                translation=translation,
                path=scripture_validator_import,
            )

        if not isinstance(result, ScriptureResult) or _norm(result.retrieval_source) != _norm(validator):
            if validator == "api_bible" and not os.getenv("API_BIBLE_KEY"):
                return {
                    "status": "blocked_config",
                    "original_source": original,
                    "validator_source": "api_bible",
                    "separate_source": True,
                    "comparison_mode": "unavailable",
                    "exact_text_compatible": False,
                    "generated_text": original_text,
                    "validator_text": "",
                    "reference": reference,
                    "translation": translation,
                    "text_match": None,
                    "discrepancy": None,
                    "details": "API_BIBLE_KEY not configured; provide API.Bible credentials or --scripture-import for independent scripture validation.",
                }
            return {
                "status": "manual_required" if validator == "api_bible" else "failed",
                "original_source": original,
                "validator_source": validator if validator != "api_bible" else "logos_manual",
                "separate_source": True,
                "comparison_mode": "unavailable",
                "exact_text_compatible": False,
                "generated_text": original_text,
                "validator_text": "",
                "reference": reference,
                "translation": translation,
                "text_match": None,
                "discrepancy": None,
            }
        validator_text = result.text
        text_match = _scripture_text_match(original_text, validator_text)
        exact_text_compatible = scripture_exact_text_compatible(
            original_source=original,
            validator_source=validator,
            translation=translation,
        )
        return {
            "status": "passed" if _norm(original) != _norm(validator) else "failed",
            "original_source": original,
            "validator_source": validator,
            "separate_source": _norm(original) != _norm(validator),
            "comparison_mode": "exact_text" if exact_text_compatible else "independent_variant",
            "exact_text_compatible": exact_text_compatible,
            "generated_text": original_text,
            "validator_text": validator_text,
            "reference": reference,
            "translation": translation,
            "text_match": text_match if exact_text_compatible else None,
            "discrepancy": (not text_match) if exact_text_compatible else None,
        }

    def _pick_quote_candidate(candidates: list[QuoteCandidate], day: Any) -> QuoteCandidate | None:
        quote_text = str(getattr(day.timeless_wisdom, "quote_text", "") or "").strip()
        original_quote_text = str(
            getattr(day.timeless_wisdom, "original_quote_text", "") or ""
        ).strip()
        author = str(getattr(day.timeless_wisdom, "author", "") or "").strip().lower()
        source_title = str(getattr(day.timeless_wisdom, "source_title", "") or "").strip().lower()
        matched: list[QuoteCandidate] = []
        for candidate in candidates:
            candidate_original = str(getattr(candidate, "original_quote_text", "") or "").strip()
            if (
                _norm_text(candidate.quote_text) == _norm_text(quote_text)
                or (original_quote_text and _norm_text(candidate.quote_text) == _norm_text(original_quote_text))
                or (candidate_original and _norm_text(candidate_original) == _norm_text(quote_text))
                or (
                    original_quote_text
                    and candidate_original
                    and _norm_text(candidate_original) == _norm_text(original_quote_text)
                )
            ):
                matched.append(candidate)
        if not matched:
            for candidate in candidates:
                if (
                    candidate.author.strip().lower() == author
                    and candidate.source_title.strip().lower() == source_title
                ):
                    matched.append(candidate)
        if matched:
            if len(matched) == 1:
                return matched[0]
            merged = merge_quote_citation_fields(*(candidate.model_dump() for candidate in matched))
            return QuoteCandidate(**merged)
        return None

    def _quote_validation(day: Any) -> dict[str, Any]:
        original_source = str(getattr(day.timeless_wisdom, "source_title", "") or "").strip()
        generated_text = str(getattr(day.timeless_wisdom, "quote_text", "") or "").strip()
        generated_original = str(getattr(day.timeless_wisdom, "original_quote_text", "") or "").strip()
        citation_locator = str(getattr(day.timeless_wisdom, "citation_locator", "") or "").strip()
        publisher = str(getattr(day.timeless_wisdom, "publisher", "") or "").strip()
        publication_city = str(getattr(day.timeless_wisdom, "publication_city", "") or "").strip()
        topic = str(book.input.topic or "").strip()
        scripture_reference = str(getattr(day.scripture, "reference", "") or "").strip()
        try:
            candidates = QuoteCatalog().retrieve_quotes(
                topic=topic,
                scripture_reference=scripture_reference,
                top_k=500,
            )
        except Exception:
            candidates = []
        candidate = _pick_quote_candidate(candidates, day)
        if candidate is None:
            return {
                "status": "failed",
                "original_source": original_source,
                "validator_source": "quote_catalog",
                "separate_source": bool(_norm(original_source)),
                "comparison_mode": "unavailable",
                "exact_text_compatible": False,
                "generated_text": generated_text,
                "validator_text": "",
                "text_match": None,
                "discrepancy": None,
            }
        validator_text = candidate.quote_text
        validator_original = str(getattr(candidate, "original_quote_text", "") or "").strip()
        text_match = (
            _norm_text(generated_text) == _norm_text(validator_text)
            or (generated_original and _norm_text(generated_original) == _norm_text(validator_text))
            or (validator_original and _norm_text(generated_text) == _norm_text(validator_original))
            or (
                generated_original
                and validator_original
                and _norm_text(generated_original) == _norm_text(validator_original)
            )
        )
        exact_text_compatible = has_strong_quote_citation(
            citation_locator=citation_locator,
            publisher=publisher,
            publication_city=publication_city,
        )
        if not exact_text_compatible:
            return {
                "status": "failed",
                "original_source": original_source,
                "validator_source": "quote_catalog",
                "separate_source": True,
                "comparison_mode": "unavailable",
                "exact_text_compatible": False,
                "generated_text": generated_text,
                "validator_text": "",
                "text_match": None,
                "discrepancy": None,
                "details": "Incomplete Turabian citation for timeless wisdom quote.",
            }
        return {
            "status": "passed",
            "original_source": original_source,
            "validator_source": "quote_catalog",
            "separate_source": True,
            "comparison_mode": "exact_text" if exact_text_compatible else "agent_variant",
            "exact_text_compatible": exact_text_compatible,
            "generated_text": generated_text,
            "validator_text": validator_text,
            "text_match": text_match if exact_text_compatible else None,
            "discrepancy": (not text_match) if exact_text_compatible else None,
        }

    agents_payload: list[dict[str, Any]] = []
    overall_pass = True
    by_day: dict[str, dict[str, Any]] = {}
    discrepancies: list[dict[str, Any]] = []
    blocking_issues: list[str] = []

    for agent in validator_agents:
        day_results: list[dict[str, Any]] = []
        failures = 0
        checks = 0
        for day in book.days:
            assessments = validate_daily_devotional(day, grounding_map=None, prayer_trace_map=None)
            day_failed = [a for a in assessments if a.result == "fail"]
            scripture_validation = _scripture_validation(day)
            quote_validation = _quote_validation(day)
            policy_failed: list[str] = []
            manual_review_flags: list[str] = []
            if not bool(scripture_validation.get("separate_source")):
                policy_failed.append("SCRIPTURE_VALIDATOR_SOURCE_NOT_SEPARATE")
            if not bool(quote_validation.get("separate_source")):
                policy_failed.append("QUOTE_VALIDATOR_SOURCE_NOT_SEPARATE")
            scripture_status = str(scripture_validation.get("status", "")).strip().lower()
            if scripture_status == "blocked_config":
                policy_failed.append("SCRIPTURE_VALIDATOR_CONFIG_MISSING")
                details = str(scripture_validation.get("details", "")).strip()
                if details and details not in blocking_issues:
                    blocking_issues.append(details)
            elif scripture_status == "manual_required":
                policy_failed.append("SCRIPTURE_VALIDATION_UNRESOLVED")
            elif scripture_status != "passed":
                policy_failed.append("SCRIPTURE_VALIDATION_FAILED")
            if scripture_validation.get("discrepancy") is True:
                # Scripture accuracy is fail-closed: mismatch is not review-only.
                policy_failed.append("SCRIPTURE_TEXT_DISCREPANCY")
                manual_review_flags.append("SCRIPTURE_TEXT_DISCREPANCY")
            elif scripture_validation.get("comparison_mode") == "independent_variant":
                manual_review_flags.append("SCRIPTURE_TEXT_VARIANT")
            quote_status = str(quote_validation.get("status", "")).strip().lower()
            if quote_status != "passed":
                policy_failed.append("QUOTE_CITATION_INCOMPLETE")
            if quote_validation.get("discrepancy") is True:
                manual_review_flags.append("QUOTE_TEXT_DISCREPANCY")
            if scripture_validation.get("discrepancy") is True:
                discrepancies.append(
                    {
                        "day_number": day.day_number,
                        "section": "scripture",
                        "original_source": scripture_validation.get("original_source"),
                        "validator_source": scripture_validation.get("validator_source"),
                        "generated_text": scripture_validation.get("generated_text"),
                        "validator_text": scripture_validation.get("validator_text"),
                        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )
            if quote_validation.get("discrepancy") is True:
                discrepancies.append(
                    {
                        "day_number": day.day_number,
                        "section": "timeless_wisdom",
                        "original_source": quote_validation.get("original_source"),
                        "validator_source": quote_validation.get("validator_source"),
                        "generated_text": quote_validation.get("generated_text"),
                        "validator_text": quote_validation.get("validator_text"),
                        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )
            if scripture_validation.get("discrepancy") is not True:
                scripture_validation["generated_text"] = ""
                scripture_validation["validator_text"] = ""
            if quote_validation.get("discrepancy") is not True:
                quote_validation["generated_text"] = ""
                quote_validation["validator_text"] = ""
            checks += len(assessments)
            failures += len(day_failed) + len(policy_failed)
            day_results.append(
                {
                    "day_number": day.day_number,
                    "failed_count": len(day_failed) + len(policy_failed),
                    "failed_check_ids": [a.check_id for a in day_failed] + policy_failed,
                    "manual_review_flags": manual_review_flags,
                    "scripture": scripture_validation,
                    "timeless_wisdom": quote_validation,
                }
            )
            day_key = str(day.day_number)
            by_day[day_key] = {
                "scripture": scripture_validation,
                "timeless_wisdom": quote_validation,
                "failed_count": len(day_failed) + len(policy_failed),
                "failed_check_ids": [a.check_id for a in day_failed] + policy_failed,
                "manual_review_flags": manual_review_flags,
            }
        passed = failures == 0
        overall_pass = overall_pass and passed
        agents_payload.append(
            {
                "agent": agent,
                "decision_source": "independent_validator_bundle",
                "passed": passed,
                "total_checks": checks,
                "failed_checks": failures,
                "days": day_results,
                "validated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_passed": overall_pass,
        "overall_status": (
            "passed"
            if overall_pass
            else "blocked_config"
            if blocking_issues
            else "failed"
        ),
        "discrepancies": discrepancies,
        "blocking_issues": blocking_issues,
        "by_day": by_day,
        "agents": agents_payload,
    }


def build_approval_gate_report(
    book: DevotionalBook,
    *,
    source_book_json: Path,
) -> dict[str, Any]:
    publish_gate = ExportGate().check_exportability(book, OutputMode.PUBLISH_READY)
    pending_sections, previews, section_meta = build_pending_sections_and_previews(
        book, include_agent_validated=True
    )
    return {
        "topic": book.input.topic,
        "days": len(book.days),
        "mode": "publish-ready",
        "exportable": publish_gate.exportable,
        "blocked_reason": publish_gate.blocked_reason,
        "pending_section_count": len(pending_sections),
        "pending_sections": pending_sections,
        "section_previews_by_key": previews,
        "section_meta_by_key": section_meta,
        "source_book_json": str(source_book_json),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "next_step": "Approve required sections, then run publish-ready export.",
    }
