from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import pydantic  # noqa: F401
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing runtime dependencies (pydantic not found). "
        "Use the project virtualenv, e.g. .venv/bin/python3."
    ) from exc

from src.api.full_run_assets import (  # noqa: E402
    CsvRunInput,
    build_agent_validation_report,
    build_approval_gate_report,
    load_competition_outline_from_csv,
    load_run_input_from_csv,
)
from src.api.generation_pipeline import generate_devotional  # noqa: E402
from src.generation.generators import MockSectionGenerator  # noqa: E402
from src.generation.real_section_generator import DeterministicRealSectionGenerator  # noqa: E402
from src.grounding_store.store import GroundingMapStore  # noqa: E402
from src.models.devotional import OutputMode  # noqa: E402
from src.persistence.config import PersistenceConfig  # noqa: E402
from src.persistence.factory import create_socket  # noqa: E402
from src.persistence.paths import default_registry_db_path  # noqa: E402
from src.prayer_trace_store.store import PrayerTraceMapStore  # noqa: E402
from src.scripture.planner import plan_scripture_day_references  # noqa: E402
from src.scripture.planner import select_daily_key_verses_reference  # noqa: E402
from src.scripture.planner import suggest_study_window_size  # noqa: E402
from src.validation.failure_remedies import remedy_suggestions  # noqa: E402
from src.validation.language_tool import collect_book_advisories  # noqa: E402
from src.validation.readability import section_readability_report  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _slugify_stage(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return text.strip("-") or "stage"


def _build_second_eyes_review_packet(
    *,
    run_slug: str,
    topic: str,
    validation_summary: dict[str, Any],
    editorial_build_payload: dict[str, Any],
    book_payload: dict[str, Any],
) -> str:
    rewrite_events = validation_summary.get("rewrite_events")
    if not isinstance(rewrite_events, list):
        return ""
    human_events = [
        event for event in rewrite_events
        if isinstance(event, dict) and str(event.get("signal", "")).strip().lower() == "human_review"
    ]
    if not human_events:
        return ""

    day_briefs = editorial_build_payload.get("day_briefs")
    if not isinstance(day_briefs, list):
        day_briefs = []
    days = book_payload.get("days")
    if not isinstance(days, list):
        days = []

    affected_days: list[int] = []
    for event in human_events:
        for day_number in event.get("target_day_numbers", []):
            if isinstance(day_number, int) and day_number > 0 and day_number not in affected_days:
                affected_days.append(day_number)

    lines: list[str] = [
        "# DevG Second-Eyes Review Packet",
        "",
        f"- Run slug: `{run_slug}`",
        f"- Topic: `{topic}`",
        f"- Total checks: `{validation_summary.get('total_checks', '')}`",
        f"- Passed: `{validation_summary.get('passed', '')}`",
        f"- Failed: `{validation_summary.get('failed', '')}`",
        "",
        "## Human-Review Escalations",
    ]
    attempted_remedies = validation_summary.get("attempted_remedies")
    if not isinstance(attempted_remedies, list):
        attempted_remedies = []
    failed_union: list[str] = []
    for event in human_events:
        for check_id in event.get("failed_check_ids", []):
            if check_id not in failed_union:
                failed_union.append(check_id)
        lines.append(
            f"- Scope: `{event.get('scope', '')}` | "
            f"Attempt: `{event.get('attempt_number', '')}` | "
            f"Failed checks: `{', '.join(event.get('failed_check_ids', []))}` | "
            f"Target days: `{', '.join(str(x) for x in event.get('target_day_numbers', []))}`"
        )

    remedies = remedy_suggestions(failed_union, attempted_remedies=attempted_remedies)
    if remedies["attempted_remedies"]:
        lines.extend(["", "## Attempted Remedies"])
        for item in remedies["attempted_remedies"]:
            lines.append(f"- {item}")
    if remedies["suggested_remedies"]:
        lines.extend(["", "## Suggested Next Remedies"])
        for item in remedies["suggested_remedies"]:
            lines.append(f"- {item}")

    lines.extend(["", "## Affected Day Briefs"])
    for day_number in affected_days:
        brief = day_briefs[day_number - 1] if 0 < day_number <= len(day_briefs) else {}
        day = days[day_number - 1] if 0 < day_number <= len(days) else {}
        scripture = day.get("scripture", {}) if isinstance(day, dict) else {}
        exposition = day.get("exposition", {}) if isinstance(day, dict) else {}
        action_steps = day.get("action_steps", {}) if isinstance(day, dict) else {}
        prayer = day.get("prayer", {}) if isinstance(day, dict) else {}
        lines.extend(
            [
                "",
                f"### Day {day_number}",
                f"- Passage: `{brief.get('scripture_reference') or scripture.get('reference', '')}`",
                f"- Focus clause: `{brief.get('focus_clause', '')}`",
                f"- Pastoral burden: `{brief.get('pastoral_burden', '')}`",
                f"- Theological lane: `{brief.get('theological_lane', '')}`",
                f"- Application lane: `{brief.get('application_lane', '')}`",
                f"- Forbidden drifts: `{'; '.join(brief.get('forbidden_drifts', []))}`",
                f"- Day focus label: `{day.get('day_focus', '') if isinstance(day, dict) else ''}`",
                "",
                "Exposition excerpt:",
                "",
                f"> {str(exposition.get('text', '')).strip()[:1200]}",
                "",
                "Action steps:",
                "",
                f"> {' | '.join(action_steps.get('items', [])) if isinstance(action_steps, dict) else ''}",
                "",
                "Prayer excerpt:",
                "",
                f"> {str(prayer.get('text', '')).strip()[:500]}",
            ]
        )

    lines.extend(
        [
            "",
            "## Reviewer Task",
            "",
            "Use this packet with `docs/system/second_eyes_review_prompt.md`.",
            "Diagnose whether the primary issue is structural, interpretive, theological, research-depth related, validator-threshold related, or mixed.",
            "Recommend the smallest defensible repair path.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _norm_scripture_ref(reference: str) -> str:
    return " ".join(str(reference or "").strip().lower().split())


def _week_by_day_from_plan(plan_rows: list[dict[str, Any]]) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for row in plan_rows:
        day_number = int(row.get("day_number", 0) or 0)
        week_number = int(row.get("week_number", 0) or 0)
        if day_number > 0 and week_number > 0:
            mapping[day_number] = week_number
    return mapping


def _week_assignments(num_days: int, num_weeks: int) -> list[int]:
    if num_days <= 0 or num_weeks <= 0:
        raise ValueError("num_days and num_weeks must be > 0")
    if num_weeks > num_days:
        raise ValueError("num_weeks cannot exceed num_days")

    sizes = [1 for _ in range(num_weeks)]
    remaining = num_days - num_weeks
    idx = 0
    while remaining > 0:
        sizes[idx] += 1
        remaining -= 1
        idx = (idx + 1) % num_weeks

    assignments: list[int] = []
    for week_number, size in enumerate(sizes, start=1):
        assignments.extend([week_number] * size)
    return assignments


def _build_standard_day_plan(
    *,
    reference: str,
    num_days: int,
    num_weeks: int,
    topic: str,
    scripture_import: Path | None = None,
) -> list[dict[str, str]]:
    references = plan_scripture_day_references(
        reference=reference,
        num_days=num_days,
        max_verses_per_day=suggest_study_window_size(
            reference=reference,
            num_days=num_days,
            operator_import=scripture_import,
        ),
        operator_import=scripture_import,
    )
    weeks = _week_assignments(num_days, num_weeks)
    return [
        {
            "day_number": str(index),
            "week_number": str(weeks[index - 1]),
            "topic": topic,
            "scripture_reference": select_daily_key_verses_reference(reference=day_reference, max_key_verses=2),
            "study_window_reference": day_reference,
        }
        for index, day_reference in enumerate(references, start=1)
    ]


def _build_child_scripture_plan(
    *,
    reference_seed: str,
    num_days: int,
    week_by_day: dict[int, int],
    parent_week_refs: dict[int, set[str]],
) -> list[dict[str, str]]:
    oversampled_days = max(num_days * 4, num_days + 8)
    candidates = plan_scripture_day_references(
        reference=reference_seed,
        num_days=oversampled_days,
        max_verses_per_day=suggest_study_window_size(
            reference=reference_seed,
            num_days=oversampled_days,
        ),
    )
    candidate_pool: list[str] = []
    seen: set[str] = set()
    for ref in candidates:
        norm = _norm_scripture_ref(ref)
        if norm in seen:
            continue
        seen.add(norm)
        candidate_pool.append(ref)

    selected: list[dict[str, str]] = []
    used_norm: set[str] = set()
    for day in range(1, num_days + 1):
        week = int(week_by_day.get(day, 0) or 0)
        if week <= 0:
            raise ValueError(f"Missing week mapping for child day {day}.")
        week_forbidden = {
            _norm_scripture_ref(x)
            for x in parent_week_refs.get(week, set())
            if str(x or "").strip()
        }
        picked: str | None = None
        for ref in candidate_pool:
            norm = _norm_scripture_ref(ref)
            if norm in used_norm:
                continue
            if norm in week_forbidden:
                continue
            picked = ref
            break
        if not picked:
            raise ValueError(
                f"Unable to plan child volume day {day}: not enough non-duplicate scriptures "
                f"for parent week {week}."
            )
        used_norm.add(_norm_scripture_ref(picked))
        selected.append(
            {
                "day_number": str(day),
                "week_number": str(week),
                "topic": "Devotional Focus",
                "scripture_reference": select_daily_key_verses_reference(reference=picked, max_key_verses=2),
                "study_window_reference": picked,
            }
        )
    return selected


def _build_audit_linkage_bundle(
    *,
    run_slug: str,
    book_payload: dict,
    agent_validation: dict,
    generated_at_utc: str,
) -> dict[str, Any]:
    days = book_payload.get("days")
    by_day = agent_validation.get("by_day") if isinstance(agent_validation, dict) else {}
    bundle: list[dict[str, Any]] = []
    if not isinstance(days, list):
        days = []
    if not isinstance(by_day, dict):
        by_day = {}
    for day in days:
        if not isinstance(day, dict):
            continue
        day_num = int(day.get("day_number", 0) or 0)
        day_validation = by_day.get(str(day_num), {}) if isinstance(by_day, dict) else {}
        for section_name in (
            "timeless_wisdom",
            "scripture",
            "exposition",
            "be_still",
            "action_steps",
            "prayer",
            "sending_prompt",
            "day7",
        ):
            sec = day.get(section_name)
            if not isinstance(sec, dict):
                continue
            sec_validation = (
                day_validation.get(section_name)
                if isinstance(day_validation, dict) and isinstance(day_validation.get(section_name), dict)
                else {}
            )
            section_key = f"day-{day_num}:{section_name}"
            bundle.append(
                {
                    "section_key": section_key,
                    "day_number": day_num,
                    "section": section_name,
                    "approval_status": str(sec.get("approval_status", "")),
                    "verification_status": str(sec.get("verification_status", "")),
                    "validation_agent": str(sec.get("validation_agent", "")),
                    "retrieval_source": str(sec.get("retrieval_source", "")),
                    "retrieval_reference": str(sec.get("retrieval_reference", "")),
                    "retrieved_at_utc": str(sec.get("retrieved_at_utc", "")),
                    "validator_source": str(sec_validation.get("validator_source", "")),
                    "validator_status": str(sec_validation.get("status", "")),
                    "validator_discrepancy": (
                        bool(sec_validation.get("discrepancy"))
                        if "discrepancy" in sec_validation
                        else None
                    ),
                    "grounding_map_id": str(sec.get("grounding_map_id", "")),
                    "prayer_trace_map_id": str(sec.get("prayer_trace_map_id", "")),
                }
            )
    return {
        "run_slug": run_slug,
        "generated_at_utc": generated_at_utc,
        "source_book_id": str(book_payload.get("id", "")),
        "entries": bundle,
    }


def _attach_audit_meta_to_approval_report(approval_report: dict[str, Any], audit_bundle: dict[str, Any]) -> None:
    section_meta = approval_report.get("section_meta_by_key")
    if not isinstance(section_meta, dict):
        section_meta = {}
        approval_report["section_meta_by_key"] = section_meta
    entries = audit_bundle.get("entries")
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        day = int(entry.get("day_number", 0) or 0)
        section = str(entry.get("section", "")).strip()
        if day <= 0 or not section:
            continue
        key = f"{day}:{section}"
        bucket = section_meta.get(key)
        if not isinstance(bucket, dict):
            bucket = {}
            section_meta[key] = bucket
        bucket["section_key"] = str(entry.get("section_key", ""))
        bucket["validator_source"] = str(entry.get("validator_source", ""))
        bucket["validator_status"] = str(entry.get("validator_status", ""))
        bucket["validator_discrepancy"] = entry.get("validator_discrepancy")
        bucket["retrieval_reference"] = str(entry.get("retrieval_reference", ""))
        bucket["retrieved_at_utc"] = str(entry.get("retrieved_at_utc", ""))
        bucket["grounding_map_id"] = str(entry.get("grounding_map_id", ""))
        bucket["prayer_trace_map_id"] = str(entry.get("prayer_trace_map_id", ""))


def _build_registry_socket(*, db_path: Path, standalone_volume: bool):
    if standalone_volume:
        return create_socket(PersistenceConfig.sqlite_memory(), component="registry")
    config = PersistenceConfig(default_provider="sqlite", sqlite_path=db_path)
    return create_socket(config, component="registry")


def _persist_day_plan(
    *,
    socket: Any,
    volume_id: str,
    series_id: str,
    volume_number: int,
    book_payload: dict,
    explicit_week_by_day: dict[int, int] | None,
    fallback_week_by_day: dict[int, int] | None,
) -> None:
    days = book_payload.get("days")
    if not isinstance(days, list):
        return
    for day in days:
        if not isinstance(day, dict):
            continue
        day_number = int(day.get("day_number", 0) or 0)
        if day_number <= 0:
            continue
        week_number = 0
        if explicit_week_by_day:
            week_number = int(explicit_week_by_day.get(day_number, 0) or 0)
        if week_number <= 0 and fallback_week_by_day:
            week_number = int(fallback_week_by_day.get(day_number, 0) or 0)
        if week_number <= 0:
            week_number = ((day_number - 1) // 7) + 1
        scripture_ref = str(((day.get("scripture") or {}).get("reference") or "")).strip()
        topic = str(day.get("theme") or day.get("focus") or "").strip() or "Devotional Focus"
        tw = day.get("timeless_wisdom") or {}
        quote_text = str(tw.get("quote_text", "")).strip()
        quote_author = str(tw.get("author", "")).strip()
        quote_source = str(tw.get("source_title", "")).strip()
        socket.record_volume_day_plan(
            volume_id=volume_id,
            series_id=series_id,
            volume_number=volume_number,
            day_number=day_number,
            week_number=week_number,
            topic=topic,
            scripture_reference=scripture_ref,
        )
        if quote_text:
            socket.record_volume_day_quote(
                volume_id=volume_id,
                series_id=series_id,
                volume_number=volume_number,
                day_number=day_number,
                week_number=week_number,
                quote_text=quote_text,
                author=quote_author or "Unknown",
                source_title=quote_source or "Unknown",
            )


def _enforce_child_week_scripture_exclusions(
    *,
    book_payload: dict,
    child_week_by_day: dict[int, int],
    parent_week_refs: dict[int, set[str]],
) -> None:
    days = book_payload.get("days")
    if not isinstance(days, list):
        return
    for day in days:
        if not isinstance(day, dict):
            continue
        day_number = int(day.get("day_number", 0) or 0)
        week_number = int(child_week_by_day.get(day_number, 0) or 0)
        if week_number <= 0:
            raise SystemExit(
                f"Volume 2+ week mapping missing for day {day_number}; cannot enforce series dedup."
            )
        scripture_ref = _norm_scripture_ref(str(((day.get("scripture") or {}).get("reference") or "")))
        forbidden = {_norm_scripture_ref(ref) for ref in parent_week_refs.get(week_number, set())}
        if scripture_ref and scripture_ref in forbidden:
            raise SystemExit(
                f"Day {day_number}: scripture '{((day.get('scripture') or {}).get('reference') or '').strip()}' "
                f"reuses parent week {week_number} scripture; blocked by series de-dup invariant."
            )


def _enforce_child_week_quote_exclusions(
    *,
    book_payload: dict,
    child_week_by_day: dict[int, int],
    parent_week_quotes: dict[int, set[str]],
) -> None:
    days = book_payload.get("days")
    if not isinstance(days, list):
        return
    for day in days:
        if not isinstance(day, dict):
            continue
        day_number = int(day.get("day_number", 0) or 0)
        week_number = int(child_week_by_day.get(day_number, 0) or 0)
        if week_number <= 0:
            raise SystemExit(
                f"Volume 2+ week mapping missing for day {day_number}; cannot enforce quote dedup."
            )
        quote_text = str(((day.get("timeless_wisdom") or {}).get("quote_text") or "")).strip()
        quote_norm = " ".join(quote_text.lower().split())
        forbidden = {" ".join(str(q).strip().lower().split()) for q in parent_week_quotes.get(week_number, set())}
        if quote_norm and quote_norm in forbidden:
            raise SystemExit(
                f"Day {day_number}: quote repeats parent week {week_number} content; "
                "blocked by series child-volume de-dup rule."
            )


def _mark_agent_validated_sections(book_payload: dict, agent_validation: dict) -> None:
    if not bool(agent_validation.get("overall_passed")):
        return
    days = book_payload.get("days")
    if not isinstance(days, list):
        return
    by_day = agent_validation.get("by_day") or {}
    for idx, day in enumerate(days):
        if not isinstance(day, dict):
            continue
        day_number = int(day.get("day_number", idx + 1))
        day_validation = by_day.get(str(day_number)) if isinstance(by_day, dict) else {}
        # Per operator requirement: day 1 remains human-only for validation display.
        if idx == 0:
            continue
        for section_name in ("timeless_wisdom", "scripture"):
            sec = day.get(section_name)
            if isinstance(sec, dict):
                section_validation = (
                    day_validation.get(section_name) if isinstance(day_validation, dict) else {}
                )
                discrepancy = (
                    bool(section_validation.get("discrepancy"))
                    if isinstance(section_validation, dict)
                    else False
                )
                validator_text = (
                    str(section_validation.get("validator_text", "")).strip()
                    if isinstance(section_validation, dict)
                    else ""
                )
                if discrepancy:
                    sec["verification_status"] = "human_review_required"
                    sec["validation_agent"] = ""
                    continue
                if section_name == "scripture" and not validator_text:
                    # No independent scripture comparison text available:
                    # keep manual review requirement (e.g., Logos reconciliation path).
                    sec["verification_status"] = "human_review_required"
                    sec["validation_agent"] = ""
                    continue
                sec["verification_status"] = "agent_validated"
                sec["validation_agent"] = "agent:validator-bundle"


def _remove_day_one_agent_validations(book_payload: dict) -> None:
    days = book_payload.get("days")
    if not isinstance(days, list) or not days:
        return
    day1 = days[0]
    if not isinstance(day1, dict):
        return
    for section_name in (
        "timeless_wisdom",
        "scripture",
        "exposition",
        "be_still",
        "action_steps",
        "prayer",
        "sending_prompt",
        "day7",
    ):
        sec = day1.get(section_name)
        if not isinstance(sec, dict):
            continue
        if str(sec.get("verification_status", "")).strip().lower() == "agent_validated":
            # Revert to neutral human-review state for day 1.
            sec["verification_status"] = "human_review_required"
            sec["validation_agent"] = ""


def _fail_closed_quality_checks(book_payload: dict) -> None:
    days = book_payload.get("days")
    if not isinstance(days, list) or not days:
        raise SystemExit("Generated book payload is missing days.")

    for day in days:
        if not isinstance(day, dict):
            raise SystemExit("Generated day payload is invalid.")
        day_num = int(day.get("day_number", 0) or 0)

        scripture = day.get("scripture") or {}
        scripture_text = str(scripture.get("text", "")).strip()
        scripture_ref = str(scripture.get("reference", "")).strip()
        scripture_source = str(scripture.get("retrieval_source", "")).strip()
        if not scripture_text:
            raise SystemExit(f"Day {day_num}: scripture text is empty.")
        if scripture_text.lower().startswith("selected passage for day"):
            raise SystemExit(
                f"Day {day_num}: placeholder scripture text detected; aborting publish pipeline."
            )
        if not re.search(r"\d+:\d+", scripture_ref):
            raise SystemExit(
                f"Day {day_num}: scripture reference lacks verse precision ({scripture_ref!r})."
            )
        if not scripture_source:
            raise SystemExit(f"Day {day_num}: scripture retrieval_source missing.")
        if (
            str(scripture.get("verification_status", "")).strip().lower() == "agent_validated"
            and not str(scripture.get("validation_agent", "")).strip()
        ):
            raise SystemExit(f"Day {day_num}: scripture validation_agent missing.")

        timeless = day.get("timeless_wisdom") or {}
        timeless_verification = str(timeless.get("verification_status", "")).strip().lower()
        if not str(timeless.get("retrieval_source", "")).strip():
            raise SystemExit(f"Day {day_num}: timeless_wisdom retrieval_source missing.")
        if not str(timeless.get("retrieved_at_utc", "")).strip():
            raise SystemExit(f"Day {day_num}: timeless_wisdom retrieved_at_utc missing.")
        if timeless_verification == "agent_validated" and not str(
            timeless.get("validation_agent", "")
        ).strip():
            raise SystemExit(f"Day {day_num}: timeless_wisdom validation_agent missing.")

        exposition = day.get("exposition") or {}
        exposition_text = str(exposition.get("text", "")).strip()
        grounding_map_id = str(exposition.get("grounding_map_id", "")).strip()
        if not exposition_text:
            raise SystemExit(f"Day {day_num}: exposition text is empty.")
        words = [w for w in exposition_text.split() if w]
        unique_ratio = (len(set(w.lower() for w in words)) / len(words)) if words else 0.0
        if len(words) < 500:
            raise SystemExit(
                f"Day {day_num}: exposition too short ({len(words)} words)."
            )
        if unique_ratio < 0.08:
            raise SystemExit(
                f"Day {day_num}: exposition appears placeholder-like "
                f"(unique_ratio={unique_ratio:.3f})."
            )
        if not grounding_map_id:
            raise SystemExit(f"Day {day_num}: exposition grounding_map_id missing.")
        if not GroundingMapStore(root_dir=GroundingMapStore.DEFAULT_ROOT).exists(grounding_map_id):
            raise SystemExit(
                f"Day {day_num}: grounding map artifact missing for id={grounding_map_id}."
            )
        gm = GroundingMapStore(root_dir=GroundingMapStore.DEFAULT_ROOT).load(grounding_map_id)
        unique_sources = set()
        for entry in gm.entries:
            for source in entry.sources_retrieved:
                if str(source).strip():
                    unique_sources.add(str(source).strip())
        if len(unique_sources) < 2:
            raise SystemExit(
                f"Day {day_num}: exposition grounding uses only {len(unique_sources)} unique source(s); "
                "at least 2 required."
            )

        prayer = day.get("prayer") or {}
        prayer_trace_map_id = str(prayer.get("prayer_trace_map_id", "")).strip()
        if not prayer_trace_map_id:
            raise SystemExit(f"Day {day_num}: prayer_trace_map_id missing.")
        if not PrayerTraceMapStore(root_dir=PrayerTraceMapStore.DEFAULT_ROOT).exists(
            prayer_trace_map_id
        ):
            raise SystemExit(
                f"Day {day_num}: prayer trace map artifact missing for id={prayer_trace_map_id}."
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run full devotional pipeline from CSV or direct input: generation, DB writes, "
            "agent validation artifact, approval gate artifact, and preview PDF."
        )
    )
    parser.add_argument("--csv", help="Path to Series/Volume CSV input")
    parser.add_argument("--row", type=int, default=1, help="1-based row number in CSV")
    parser.add_argument("--topic", help="Direct-input devotional topic/title")
    parser.add_argument("--scripture-reference", help="Direct-input scripture range")
    parser.add_argument("--num-days", type=int, help="Direct-input devotional length in days")
    parser.add_argument("--num-weeks", type=int, help="Direct-input devotional length in weeks")
    parser.add_argument("--title", help="Optional direct-input title override")
    parser.add_argument("--output-dir", default="outputs/devotionals", help="Output artifact directory")
    parser.add_argument("--db-path", default=None, help="SQLite DB path")
    parser.add_argument(
        "--scripture-import",
        help="Optional operator scripture import CSV for retrieval fallback.",
    )
    parser.add_argument("--generator", choices=["mock", "real"], default="real")
    parser.add_argument(
        "--allow-nonprod-generator",
        action="store_true",
        help="Allow non-production generator choices (debug only).",
    )
    parser.add_argument("--series-id", help="Override series_id from CSV")
    parser.add_argument("--volume-number", type=int, help="Override volume_number from CSV")
    parser.add_argument("--volume-id", help="Override volume_id from CSV")
    parser.add_argument(
        "--validator-agent",
        action="append",
        dest="validator_agents",
        help="Independent validator agent id (repeatable). Default: agent:validator-1, agent:validator-2",
    )
    parser.add_argument(
        "--reviewed-by",
        default="Victor",
        help="Default reviewer identity embedded in follow-up command hints.",
    )
    args = parser.parse_args(argv)

    day_plan_payload: list[dict[str, str]] | None = None
    explicit_week_by_day: dict[int, int] = {}
    scripture_import_path = Path(args.scripture_import) if args.scripture_import else None
    if args.csv:
        csv_path = Path(args.csv)
        if csv_path.suffix.lower() == ".csv":
            try:
                run_input, outline = load_competition_outline_from_csv(
                    csv_path,
                    series_id=args.series_id,
                    volume_number=args.volume_number or 1,
                )
                day_plan_payload = [
                    {
                        "day_number": str(entry.day_number),
                        "week_number": str(entry.week),
                        "topic": entry.topic,
                        "scripture_reference": entry.scripture_reference,
                    }
                    for entry in outline
                ]
                explicit_week_by_day = {
                    int(entry.day_number): int(entry.week)
                    for entry in outline
                }
            except ValueError:
                run_input = load_run_input_from_csv(csv_path, row_number=args.row)
        else:
            run_input = load_run_input_from_csv(csv_path, row_number=args.row)
    else:
        missing = [
            name
            for name, value in (
                ("--topic", args.topic),
                ("--scripture-reference", args.scripture_reference),
                ("--num-days", args.num_days),
                ("--num-weeks", args.num_weeks),
            )
            if value in (None, "")
        ]
        if missing:
            raise SystemExit(
                "Direct-input mode requires "
                + ", ".join(missing)
                + " when --csv is not provided."
            )
        run_input = CsvRunInput(
            topic=str(args.topic).strip(),
            num_days=int(args.num_days),
            scripture_reference=str(args.scripture_reference).strip(),
            title=str(args.title).strip() if args.title else None,
            series_id=args.series_id,
            volume_number=args.volume_number or 1,
            volume_id=args.volume_id,
            parent_volume_id=None,
        )
        day_plan_payload = _build_standard_day_plan(
            reference=run_input.scripture_reference or run_input.topic,
            num_days=run_input.num_days,
            num_weeks=int(args.num_weeks),
            topic=run_input.topic,
            scripture_import=scripture_import_path,
        )
        explicit_week_by_day = _week_by_day_from_plan(day_plan_payload)
    volume_number = args.volume_number or run_input.volume_number
    volume_id = args.volume_id or run_input.volume_id or f"vol-{uuid.uuid4().hex[:8]}"
    explicit_series_id = args.series_id or run_input.series_id
    standalone_volume = not bool(str(explicit_series_id or "").strip())
    series_id = str(explicit_series_id).strip() if explicit_series_id else None

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d__%H%M%S")
    slug_topic = run_input.topic.lower().replace(" ", "-").replace("/", "-")
    run_slug = f"{stamp}__{slug_topic}__{run_input.num_days}-day__vol-{volume_number}"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(args.db_path) if args.db_path else default_registry_db_path()
    os.environ["DEVG_DB_PATH"] = str(db_path)
    os.environ["DEVG_REQUIRE_DB_CATALOG"] = "1"

    book_path = output_dir / f"{run_slug}__book.json"
    meta_path = output_dir / f"{run_slug}__meta.json"
    editorial_build_path = output_dir / f"{run_slug}__editorial-build.json"
    audit_linkage_path = output_dir / f"{run_slug}__audit-linkage.json"
    approval_report_path = output_dir / f"{run_slug}__approval-gate-report.json"
    decisions_path = output_dir / f"{run_slug}__approval-decisions.json"
    validator_report_path = output_dir / f"{run_slug}__agent-validation-report.json"
    language_tool_report_path = output_dir / f"{run_slug}__language-tool-report.json"
    readability_report_path = output_dir / f"{run_slug}__readability-report.json"
    second_eyes_packet_path = output_dir / f"{run_slug}__second-eyes-review-packet.md"
    checkpoint_dir = output_dir / f"{run_slug}__checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    socket = _build_registry_socket(
        db_path=db_path,
        standalone_volume=standalone_volume,
    )
    parent_week_by_day: dict[int, int] = {}
    parent_week_refs: dict[int, set[str]] = {}
    parent_week_quotes: dict[int, set[str]] = {}
    quote_exclusions_by_day: dict[int, set[str]] = {}

    if args.generator == "mock" and not args.allow_nonprod_generator:
        raise SystemExit(
            "Refusing non-production generator in full pipeline run. "
            "Use --generator real (default), or pass --allow-nonprod-generator for debug-only runs."
        )

    if args.generator == "real":
        generator = DeterministicRealSectionGenerator(
            operator_scripture_import=scripture_import_path
        )
    else:
        generator = MockSectionGenerator()

    if not standalone_volume and volume_number > 1:
        assert series_id is not None
        parent_volume = socket.get_volume_by_number(series_id=series_id, volume_number=1)
        if parent_volume is None:
            raise SystemExit(
                f"Series '{series_id}' has no canonical volume 1 in registry; "
                "cannot auto-resolve child volume context."
            )
        parent_plan = socket.get_volume_day_plan(parent_volume.id)
        if not parent_plan:
            raise SystemExit(
                f"Series '{series_id}' volume 1 has no stored day/week plan; "
                "cannot auto-resolve child volume context."
            )
        parent_week_by_day = {int(r.day_number): int(r.week_number) for r in parent_plan}
        expected_days = len(parent_plan)
        if run_input.num_days != expected_days:
            raise SystemExit(
                f"Volume {volume_number} day count mismatch for series '{series_id}': "
                f"expected {expected_days} (from volume 1), got {run_input.num_days}."
            )
        parent_week_refs = socket.get_week_scripture_map_for_volume(parent_volume.id)
        parent_week_quotes = socket.get_week_quote_map_for_volume(parent_volume.id)
        if not parent_week_quotes:
            raise SystemExit(
                f"Series '{series_id}' volume 1 has no stored day/week quote map; "
                "cannot enforce child quote de-dup."
            )
        all_prior_quotes: set[str] = set()
        for prev_volume_number in range(1, volume_number):
            prev_volume = socket.get_volume_by_number(series_id=series_id, volume_number=prev_volume_number)
            if prev_volume is None:
                continue
            prev_week_quotes = socket.get_week_quote_map_for_volume(prev_volume.id)
            for quotes in prev_week_quotes.values():
                all_prior_quotes.update(quotes)
        for day_number, week_number in parent_week_by_day.items():
            quote_exclusions_by_day[day_number] = set(parent_week_quotes.get(week_number, set()))
            quote_exclusions_by_day[day_number].update(all_prior_quotes)
        if day_plan_payload is None:
            # Auto-context mode: week mapping is inherited from canonical volume 1.
            explicit_week_by_day = dict(parent_week_by_day)
            reference_seed = str((run_input.scripture_reference or run_input.topic or "")).strip()
            if not reference_seed:
                raise SystemExit(
                    f"Series '{series_id}' volume {volume_number} requires scripture_reference or topic "
                    "to auto-plan non-duplicate child scriptures."
                )
            try:
                day_plan_payload = _build_child_scripture_plan(
                    reference_seed=reference_seed,
                    num_days=run_input.num_days,
                    week_by_day=explicit_week_by_day,
                    parent_week_refs=parent_week_refs,
                )
            except ValueError as exc:
                raise SystemExit(
                    f"Unable to auto-plan child scripture set for series '{series_id}' volume {volume_number}: {exc}"
                ) from exc

    meta = {
        "run_slug": run_slug,
        "topic": run_input.topic,
        "days": run_input.num_days,
        "series_id": None if standalone_volume else series_id,
        "standalone_volume": standalone_volume,
        "volume_number": volume_number,
        "volume_id": volume_id,
        "db_path": str(db_path),
        "generator": args.generator,
        "run_state": "planning_started",
        "preview_pdf_path": None,
        "editorial_build_path": str(editorial_build_path),
        "book_json_path": str(book_path),
        "approval_report_path": str(approval_report_path),
        "approval_decisions_path": str(decisions_path),
        "agent_validation_report_path": str(validator_report_path),
        "audit_linkage_path": str(audit_linkage_path),
        "language_tool_report_path": str(language_tool_report_path),
        "readability_report_path": str(readability_report_path),
        "checkpoint_dir": str(checkpoint_dir),
        "second_eyes_review_prompt_path": "docs/system/second_eyes_review_prompt.md",
        "second_eyes_review_packet_path": None,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(meta_path, meta)

    checkpoint_counter = 0

    def _checkpoint_writer(stage: str, payload: dict[str, Any]) -> None:
        nonlocal checkpoint_counter
        checkpoint_counter += 1
        checkpoint_path = checkpoint_dir / f"{checkpoint_counter:03d}__{_slugify_stage(stage)}.json"
        _write_json(
            checkpoint_path,
            {
                "run_slug": run_slug,
                "stage": stage,
                "sequence": checkpoint_counter,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            },
        )

    result = generate_devotional(
        topic=run_input.topic,
        num_days=run_input.num_days,
        scripture_reference=run_input.scripture_reference,
        day_plan=day_plan_payload,
        output_mode=OutputMode.PERSONAL,
        generator=generator,
        registry=socket,
        series_id=series_id,
        volume_number=volume_number,
        volume_id=volume_id,
        quote_exclusions_by_day=quote_exclusions_by_day or None,
        require_planned_scripture=True,
        checkpoint_callback=_checkpoint_writer,
    )
    actual_volume_id = result.registry_volume_id

    # Build full generated devotional payload for review parity and downstream checks.
    book_payload = result.book.model_dump(mode="json")
    book_payload["series_id"] = None if standalone_volume else series_id
    book_payload["volume_number"] = volume_number
    book_payload["volume_id"] = actual_volume_id
    if run_input.title:
        book_payload.setdefault("input", {})["title"] = run_input.title

    review_cmd = (
        f"python3 scripts/review/run_review.py --backend web --report {approval_report_path} "
        f"--out {decisions_path} --reviewed-by \"{args.reviewed_by}\""
    )
    studio_cmd = (
        f"python3 scripts/review/run_review_studio.py --report {approval_report_path} "
        f"--out {decisions_path} --book-json {book_path} --reviewed-by \"{args.reviewed_by}\""
    )
    publish_cmd = (
        f"python3 scripts/apply_decisions_and_export.py --book-json {book_path} "
        f"--decisions-json {decisions_path}"
    )

    editorial_build_payload = result.editorial_build.model_dump(mode="json")
    _write_json(editorial_build_path, editorial_build_payload)
    _write_json(book_path, book_payload)

    second_eyes_packet = _build_second_eyes_review_packet(
        run_slug=run_slug,
        topic=run_input.topic,
        validation_summary=result.validation_summary.model_dump(mode="json"),
        editorial_build_payload=editorial_build_payload,
        book_payload=book_payload,
    )
    if second_eyes_packet:
        _write_text(second_eyes_packet_path, second_eyes_packet)

    language_tool_advisories = [
        {
            "day_number": item.day_number,
            "section": item.section,
            "rule_id": item.rule_id,
            "message": item.message,
            "category": item.category,
            "context": item.context,
            "replacements": list(item.replacements),
        }
        for item in collect_book_advisories(
            book_payload,
            editorial_build_payload=editorial_build_payload,
        )
    ]
    _write_json(
        language_tool_report_path,
        {
            "mode": "advisory",
            "enabled": True,
            "advisory_count": len(language_tool_advisories),
            "advisories": language_tool_advisories,
        },
    )

    readability_days: list[dict[str, Any]] = []
    exposition_grades: list[float] = []
    exposition_ease: list[float] = []
    for day in book_payload.get("days", []):
        if not isinstance(day, dict):
            continue
        day_number = int(day.get("day_number", 0) or 0)
        exposition = day.get("exposition") if isinstance(day.get("exposition"), dict) else {}
        exposition_text = str(exposition.get("text", "")).strip()
        if not exposition_text:
            continue
        report = section_readability_report(exposition_text)
        exposition_grades.append(float(report["flesch_kincaid_grade"]))
        exposition_ease.append(float(report["flesch_reading_ease"]))
        readability_days.append(
            {
                "day_number": day_number,
                "section": "exposition",
                **report,
            }
        )

    readability_summary = {
        "exposition_days_scored": len(readability_days),
        "target_max_grade": 8.0,
        "average_flesch_kincaid_grade": round(sum(exposition_grades) / len(exposition_grades), 2)
        if exposition_grades
        else None,
        "average_flesch_reading_ease": round(sum(exposition_ease) / len(exposition_ease), 2)
        if exposition_ease
        else None,
        "days_above_target_grade": [
            item["day_number"]
            for item in readability_days
            if float(item["flesch_kincaid_grade"]) > 8.0
        ],
    }
    _write_json(
        readability_report_path,
        {
            "target_max_grade": 8.0,
            "summary": readability_summary,
            "days": readability_days,
        },
    )

    meta.update(
        {
            "volume_id": actual_volume_id,
            "run_state": "generated_unvalidated",
            "second_eyes_review_packet_path": (
                str(second_eyes_packet_path) if second_eyes_packet else None
            ),
            "remedy_suggestions": remedy_suggestions(
                [
                    check_id
                    for event in result.validation_summary.model_dump(mode="json").get("rewrite_events", [])
                    for check_id in event.get("failed_check_ids", [])
                ],
                attempted_remedies=result.validation_summary.model_dump(mode="json").get("attempted_remedies", []),
            ),
            "language_tool": {
                "mode": "advisory",
                "advisory_count": len(language_tool_advisories),
            },
            "readability": readability_summary,
            "validation_summary": result.validation_summary.model_dump(mode="json"),
            "agent_validation_overall_passed": None,
            "review_web_command": review_cmd,
            "review_studio_command": studio_cmd,
            "publish_ready_command": publish_cmd,
        }
    )
    _write_json(meta_path, meta)

    agents = args.validator_agents or ["agent:validator-1", "agent:validator-2"]
    agent_validation = build_agent_validation_report(
        result.book,
        validator_agents=agents,
        scripture_validator_import=(
            scripture_import_path
        ),
    )
    _write_json(validator_report_path, agent_validation)
    meta["agent_validation_overall_passed"] = agent_validation["overall_passed"]
    meta["agent_validation_overall_status"] = agent_validation.get("overall_status")
    meta["blocking_issues"] = agent_validation.get("blocking_issues")
    if not agent_validation["overall_passed"]:
        meta["run_state"] = "validation_failed"
        _write_json(meta_path, meta)
        if str(agent_validation.get("overall_status", "")).strip().lower() == "blocked_config":
            blocking_issues = agent_validation.get("blocking_issues") or []
            issue_text = (
                "; ".join(str(item).strip() for item in blocking_issues if str(item).strip())
                or "Independent scripture validator configuration missing."
            )
            raise SystemExit(
                f"Independent validator unavailable: {issue_text}"
            )
        raise SystemExit("Independent validator agents reported failures; aborting run.")

    _mark_agent_validated_sections(book_payload, agent_validation)
    _remove_day_one_agent_validations(book_payload)
    _fail_closed_quality_checks(book_payload)
    if not standalone_volume and volume_number > 1:
        _enforce_child_week_scripture_exclusions(
            book_payload=book_payload,
            child_week_by_day=explicit_week_by_day or parent_week_by_day,
            parent_week_refs=parent_week_refs,
        )
        _enforce_child_week_quote_exclusions(
            book_payload=book_payload,
            child_week_by_day=explicit_week_by_day or parent_week_by_day,
            parent_week_quotes=parent_week_quotes,
        )
    if not standalone_volume:
        _persist_day_plan(
            socket=socket,
            volume_id=actual_volume_id,
            series_id=series_id,
            volume_number=volume_number,
            book_payload=book_payload,
            explicit_week_by_day=explicit_week_by_day,
            fallback_week_by_day=parent_week_by_day,
        )

    # Keep model object aligned with artifact payload for downstream report generation.
    result.book = result.book.model_validate(book_payload)
    _write_json(book_path, book_payload)

    audit_linkage = _build_audit_linkage_bundle(
        run_slug=run_slug,
        book_payload=book_payload,
        agent_validation=agent_validation,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    _write_json(audit_linkage_path, audit_linkage)

    approval_gate = build_approval_gate_report(result.book, source_book_json=book_path)
    _attach_audit_meta_to_approval_report(approval_gate, audit_linkage)
    _write_json(approval_report_path, approval_gate)
    meta["run_state"] = "validated_pass"
    _write_json(meta_path, meta)

    print(f"RUN_SLUG={run_slug}")
    print(f"BOOK_JSON={book_path}")
    print(f"EDITORIAL_BUILD={editorial_build_path}")
    print(f"APPROVAL_REPORT={approval_report_path}")
    print(f"AGENT_VALIDATION={validator_report_path}")
    print(f"AUDIT_LINKAGE={audit_linkage_path}")
    print(f"META={meta_path}")
    print(f"REVIEW_WEB={review_cmd}")
    print(f"REVIEW_STUDIO={studio_cmd}")
    print(f"PUBLISH_READY={publish_cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
