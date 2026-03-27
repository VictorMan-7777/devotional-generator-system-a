from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.models.devotional import DevotionalBook, SectionApprovalStatus
from src.models.registry import ReviewSectionRecord
from src.persistence.config import PersistenceConfig
from src.persistence.factory import create_socket
from src.persistence.paths import default_registry_db_path
from src.persistence.socket import DatabaseSocket

REVIEWABLE_SECTIONS = (
    "timeless_wisdom",
    "scripture",
    "exposition",
    "be_still",
    "action_steps",
    "prayer",
    "sending_prompt",
    "day7",
)


def build_review_socket() -> DatabaseSocket:
    cfg = PersistenceConfig.from_env()
    if not str(os.getenv("DEVG_SQLITE_PATH", "")).strip():
        cfg = PersistenceConfig(
            default_provider=cfg.default_provider,
            sqlite_path=default_registry_db_path(),
            component_providers=cfg.component_providers,
        )
    return create_socket(
        cfg,
        component="registry",
    )


def infer_run_slug(path: Path) -> str:
    name = path.name
    for suffix in (
        "__book.json",
        "__approval-gate-report.json",
        "__approval-decisions.json",
        "__review-edits.json",
        "__meta.json",
    ):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def seed_review_sections(
    *,
    socket: DatabaseSocket,
    run_slug: str,
    book_data: dict[str, Any] | None,
    section_previews: dict[str, str] | None = None,
) -> None:
    if not book_data:
        return
    previews = section_previews or {}
    days = book_data.get("days")
    if not isinstance(days, list):
        return
    for raw_day in days:
        if not isinstance(raw_day, dict):
            continue
        day_number = int(raw_day.get("day_number", -1))
        if day_number <= 0:
            continue
        for section_name in REVIEWABLE_SECTIONS:
            payload = raw_day.get(section_name)
            if payload is None:
                continue
            socket.seed_review_section(
                run_slug=run_slug,
                day_number=day_number,
                section_name=section_name,
                original_payload_json=json.dumps(payload, ensure_ascii=True),
                original_preview=str(previews.get(f"{day_number}:{section_name}", "") or ""),
            )


def load_review_records(*, socket: DatabaseSocket, run_slug: str) -> list[ReviewSectionRecord]:
    return socket.list_review_sections(run_slug)


def load_edits_map(*, socket: DatabaseSocket, run_slug: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in socket.list_review_sections(run_slug):
        if not (row.edited_plain or row.edit_note or row.edited_html):
            continue
        result[f"{row.day_number}:{row.section_name}"] = {
            "day": row.day_number,
            "section": row.section_name,
            "editor_html": row.edited_html,
            "editor_plain": row.edited_plain,
            "note": row.edit_note,
            "updated_at_utc": row.edited_at_utc,
        }
    return result


def load_decision_map(*, socket: DatabaseSocket, run_slug: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in socket.list_review_sections(run_slug):
        if row.approval_decision not in {"approved", "rejected", "skipped"}:
            continue
        record: dict[str, Any] = {
            "day": row.day_number,
            "section": row.section_name,
            "decision": row.approval_decision,
            "reviewed_by": row.reviewed_by or "",
        }
        if row.reviewed_at_utc:
            record["reviewed_at_utc"] = row.reviewed_at_utc
        if row.operator_note:
            record["operator_note"] = row.operator_note
        if row.decision_source:
            record["decision_source"] = row.decision_source
        result[f"{row.day_number}:{row.section_name}"] = record
    return result


def save_edit(
    *,
    socket: DatabaseSocket,
    run_slug: str,
    day_number: int,
    section_name: str,
    edited_payload: Any,
    editor_html: str,
    editor_plain: str,
    note: str,
    edited_at_utc: str,
) -> None:
    socket.save_review_edit(
        run_slug=run_slug,
        day_number=day_number,
        section_name=section_name,
        edited_payload_json=json.dumps(edited_payload, ensure_ascii=True) if edited_payload is not None else "",
        edited_html=editor_html,
        edited_plain=editor_plain,
        edit_note=note,
        edited_at_utc=edited_at_utc,
    )


def save_decision(
    *,
    socket: DatabaseSocket,
    run_slug: str,
    day_number: int,
    section_name: str,
    approval_decision: str,
    operator_note: str,
    reviewed_by: str,
    decision_source: str | None,
    reviewed_at_utc: str,
    approved_payload: Any,
    approved_preview: str,
) -> None:
    socket.save_review_decision(
        run_slug=run_slug,
        day_number=day_number,
        section_name=section_name,
        approval_decision=approval_decision,
        operator_note=operator_note,
        reviewed_by=reviewed_by,
        decision_source=decision_source,
        reviewed_at_utc=reviewed_at_utc,
        approved_payload_json=json.dumps(approved_payload, ensure_ascii=True) if approved_payload is not None else "",
        approved_preview=approved_preview,
    )


def apply_review_state_to_book(
    *,
    socket: DatabaseSocket,
    run_slug: str,
    book: DevotionalBook,
) -> tuple[int, int]:
    records = socket.list_review_sections(run_slug)
    applied_content = 0
    applied_decisions = 0
    day_map = {int(day.day_number): day for day in book.days}
    for row in records:
        day = day_map.get(int(row.day_number))
        if day is None:
            continue
        section = getattr(day, row.section_name, None)
        if section is None:
            continue
        payload_text = row.approved_payload_json or row.edited_payload_json
        if payload_text:
            updated = type(section).model_validate(json.loads(payload_text))
            setattr(day, row.section_name, updated)
            section = updated
            applied_content += 1
        if row.approval_decision in {"approved", "rejected"}:
            section.approval_status = (
                SectionApprovalStatus.APPROVED
                if row.approval_decision == "approved"
                else SectionApprovalStatus.REJECTED
            )
            applied_decisions += 1
    return applied_content, applied_decisions
