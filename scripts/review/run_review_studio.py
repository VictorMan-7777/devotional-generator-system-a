from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.citations.quote_citations import (
    has_strong_quote_citation,
    quote_attribution_line,
    quote_footnote,
)
from src.grounding_store.store import GroundingMapStore
from src.prayer_trace_store.store import PrayerTraceMapStore
from src.review_store import (
    build_review_socket,
    infer_run_slug,
    load_decision_map as load_review_decision_map,
    load_edits_map as load_review_edits_map,
    save_decision as save_review_decision,
    save_edit as save_review_edit,
    seed_review_sections,
)

from scripts.review.run_pending_approvals import (
    _build_output_path,
    _decision_key,
    _ensure_decision_source_policy,
    _sorted_decisions,
    default_reviewed_by,
    format_section_label,
    load_existing_decisions,
    load_report,
    parse_pending_item,
    unresolved_items,
    write_decisions,
)


def _build_edits_path(report_path: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    base = report_path.name
    if base.endswith("__approval-gate-report.json"):
        base = base.replace("__approval-gate-report.json", "__review-edits.json")
    else:
        base = base.replace(".json", "") + "__review-edits.json"
    return report_path.parent / base


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_edits(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    edits = data.get("edits") or []
    result: dict[str, dict] = {}
    for raw in edits:
        day = int(raw.get("day"))
        section = str(raw.get("section") or "").strip()
        if day <= 0 or not section:
            continue
        result[_decision_key(day, section)] = {
            "day": day,
            "section": section,
            "editor_html": str(raw.get("editor_html") or ""),
            "editor_plain": str(raw.get("editor_plain") or ""),
            "note": str(raw.get("note") or ""),
            "updated_at_utc": str(raw.get("updated_at_utc") or ""),
        }
    return result


def _load_book_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Book JSON not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Book JSON must be a JSON object.")
    return data


def _section_payload_from_book(book_data: dict[str, Any] | None, day: int, section: str) -> Any:
    if not book_data:
        return None
    days = book_data.get("days")
    if not isinstance(days, list):
        return None
    for raw in days:
        if isinstance(raw, dict) and int(raw.get("day_number", -1)) == day:
            return raw.get(section)
    return None


def _default_agent_report_path(report_path: Path) -> Path:
    name = report_path.name
    if name.endswith("__approval-gate-report.json"):
        return report_path.with_name(name.replace("__approval-gate-report.json", "__agent-validation-report.json"))
    return report_path.with_name(name.replace(".json", "__agent-validation-report.json"))


def _load_agent_validation(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    by_day = data.get("by_day")
    if isinstance(by_day, dict):
        return by_day
    return {}


def _resolve_report_relative(path_value: str, report_path: Path) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    # Support both report-local paths and repo-relative paths recorded in report metadata.
    if candidate.exists():
        return candidate
    return report_path.parent / candidate


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


def _parse_list_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        out.append(line)
    return out


def _reader_heading_for_section(section: str) -> str:
    mapping = {
        "timeless_wisdom": "Timeless Wisdom",
        "scripture": "Scripture Reading",
        "exposition": "Reflection",
        "be_still": "Still Before God",
        "action_steps": "Walk It Out",
        "prayer": "Prayer",
        "sending_prompt": "Sending Prompt",
        "day7": "Day 7 Reflection",
    }
    return mapping.get(section, format_section_label(section))


def _apply_edit_to_book(book_data: dict[str, Any], day: int, section: str, editor_plain: str) -> bool:
    days = book_data.get("days")
    if not isinstance(days, list):
        return False
    target: dict[str, Any] | None = None
    for raw in days:
        if isinstance(raw, dict) and int(raw.get("day_number", -1)) == day:
            target = raw
            break
    if target is None:
        return False

    section_obj = target.get(section)
    if not isinstance(section_obj, dict):
        return False
    text = editor_plain.strip()
    if section in {"exposition", "prayer", "sending_prompt"}:
        section_obj["text"] = text
        if section in {"exposition", "prayer"}:
            section_obj["word_count"] = len([w for w in text.split() if w])
        return True
    if section == "timeless_wisdom":
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return False
        quote_line = lines[0]
        if quote_line.startswith('"') and quote_line.endswith('"') and len(quote_line) > 1:
            quote_line = quote_line[1:-1]
        section_obj["quote_text"] = quote_line
        for line in lines[1:]:
            if line.startswith("- "):
                attribution = line[2:].strip()
                if "," in attribution:
                    author, source_title = [part.strip() for part in attribution.split(",", 1)]
                    if author:
                        section_obj["author"] = author
                    if source_title:
                        section_obj["source_title"] = source_title
                else:
                    section_obj["author"] = attribution
        return True
    if section == "scripture":
        # Keep structured fields stable; editor primarily updates scripture text body.
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            section_obj["text"] = "\n".join(lines)
        return True
    if section == "be_still":
        items = _parse_list_lines(text)
        if items:
            section_obj["prompts"] = items
        return True
    if section == "action_steps":
        items = _parse_list_lines(text)
        if items:
            if len(items) >= 2 and not editor_plain.lstrip().startswith("- "):
                section_obj["connector_phrase"] = items[0]
                section_obj["items"] = items[1:]
            else:
                section_obj["items"] = items
        return True
    return False


def _context_snippet(text: str, needle: str, radius: int = 120) -> str:
    hay = text.strip()
    target = needle.strip()
    if not hay or not target:
        return ""
    idx = hay.lower().find(target.lower())
    if idx < 0:
        return ""
    start = max(0, idx - radius)
    end = min(len(hay), idx + len(target) + radius)
    return hay[start:end].strip()


def _exposition_grounding_evidence(book_data: dict[str, Any] | None, day: int) -> list[dict[str, Any]]:
    if not book_data:
        return []
    days = book_data.get("days")
    if not isinstance(days, list):
        return []
    target: dict[str, Any] | None = None
    for raw in days:
        if isinstance(raw, dict) and int(raw.get("day_number", -1)) == day:
            target = raw
            break
    if target is None:
        return []
    exposition = target.get("exposition")
    if not isinstance(exposition, dict):
        return []
    gm_id = str(exposition.get("grounding_map_id") or "").strip()
    if not gm_id:
        return []
    exposition_text = _coerce_text(exposition.get("text"))
    try:
        gm = GroundingMapStore(root_dir=GroundingMapStore.DEFAULT_ROOT).load(gm_id)
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for entry in gm.entries:
        excerpts = [str(x).strip() for x in entry.excerpts_used if str(x).strip()]
        original_excerpts = [
            str(x).strip() for x in getattr(entry, "original_excerpts_used", []) if str(x).strip()
        ]
        excerpt_flags = [bool(x) for x in getattr(entry, "excerpts_modernized", [])]
        excerpt = excerpts[0] if excerpts else ""
        context = _context_snippet(exposition_text, excerpt) if excerpt else ""
        out.append(
            {
                "paragraph_number": entry.paragraph_number,
                "paragraph_name": entry.paragraph_name,
                "source_titles": [str(x).strip() for x in entry.sources_retrieved if str(x).strip()],
                "source_ids": [str(x).strip() for x in entry.source_ids if str(x).strip()],
                "similarity_scores": [float(x) for x in entry.similarity_scores],
                "excerpts_used": excerpts,
                "original_excerpts_used": original_excerpts,
                "excerpts_modernized": excerpt_flags,
                "modernization_label": str(getattr(entry, "modernization_label", "") or "").strip(),
                "excerpt_used": excerpt,
                "context_snippet": context,
                "how_retrieval_informed_paragraph": str(
                    entry.how_retrieval_informed_paragraph or ""
                ).strip(),
            }
        )
    return out


def _prayer_trace_evidence(book_data: dict[str, Any] | None, day: int) -> list[dict[str, str]]:
    if not book_data:
        return []
    days = book_data.get("days")
    if not isinstance(days, list):
        return []
    target: dict[str, Any] | None = None
    for raw in days:
        if isinstance(raw, dict) and int(raw.get("day_number", -1)) == day:
            target = raw
            break
    if target is None:
        return []
    prayer = target.get("prayer")
    if not isinstance(prayer, dict):
        return []
    ptm_id = str(prayer.get("prayer_trace_map_id") or "").strip()
    if not ptm_id:
        return []
    try:
        ptm = PrayerTraceMapStore(root_dir=PrayerTraceMapStore.DEFAULT_ROOT).load(ptm_id)
    except Exception:
        return []
    return [
        {
            "element_text": str(e.element_text),
            "source_type": str(e.source_type),
            "source_reference": str(e.source_reference),
        }
        for e in ptm.entries
    ]


def _quote_distribution(book_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not book_data:
        return []
    days = book_data.get("days")
    if not isinstance(days, list):
        return []
    counts: dict[str, int] = {}
    for raw in days:
        if not isinstance(raw, dict):
            continue
        tw = raw.get("timeless_wisdom")
        if not isinstance(tw, dict):
            continue
        author = str(tw.get("author") or "").strip() or "Unknown"
        counts[author] = counts.get(author, 0) + 1
    return [
        {"author": author, "count": count}
        for author, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    ]


def _section_preview_from_book(book_data: dict[str, Any] | None, day: int, section: str) -> str:
    if not book_data:
        return ""
    days = book_data.get("days")
    if not isinstance(days, list):
        return ""
    target: dict[str, Any] | None = None
    for raw in days:
        if isinstance(raw, dict) and int(raw.get("day_number", -1)) == day:
            target = raw
            break
    if target is None:
        return ""

    sec = target.get(section)
    if isinstance(sec, dict):
        if section == "timeless_wisdom":
            quote = _coerce_text(sec.get("quote_text"))
            author = _coerce_text(sec.get("author"))
            source = _coerce_text(sec.get("source_title"))
            footnote = quote_footnote(
                author=author,
                source_title=source,
                publication_year=sec.get("publication_year"),
                citation_locator=_coerce_text(sec.get("citation_locator")) or _coerce_text(sec.get("page_or_url")),
                publisher=_coerce_text(sec.get("publisher")),
                publication_city=_coerce_text(sec.get("publication_city")),
            )
            citation_ready = has_strong_quote_citation(
                citation_locator=_coerce_text(sec.get("citation_locator")) or _coerce_text(sec.get("page_or_url")),
                publisher=_coerce_text(sec.get("publisher")),
                publication_city=_coerce_text(sec.get("publication_city")),
            )
            if bool(sec.get("language_modernized")) and _coerce_text(sec.get("modernization_label")):
                footnote = f"{footnote} ({_coerce_text(sec.get('modernization_label'))})"
            if quote:
                lines = [f"\"{quote}\""]
                attribution = quote_attribution_line(author, source).replace("- ", "", 1)
                if attribution:
                    lines.append(f"- {attribution}")
                if bool(sec.get("language_modernized")):
                    original_quote = _coerce_text(sec.get("original_quote_text"))
                    if original_quote and original_quote != quote:
                        lines.append(f"Original wording: \"{original_quote}\"")
                if source:
                    label = (
                        "Turabian Footnote"
                        if citation_ready
                        else "Competition blocker (incomplete Turabian footnote)"
                    )
                    lines.append(f"{label}: {footnote}")
                return "\n".join(lines)
        if section == "scripture":
            ref = _coerce_text(sec.get("reference"))
            text = _coerce_text(sec.get("text"))
            return "\n\n".join(part for part in [ref, text] if part)
        if section in {"exposition", "prayer", "sending_prompt"}:
            return _coerce_text(sec.get("text"))
        if section in {"be_still", "action_steps"}:
            key = "prompts" if section == "be_still" else "items"
            items = sec.get(key)
            if isinstance(items, list):
                lines: list[str] = []
                if section == "action_steps":
                    connector = _coerce_text(sec.get("connector_phrase"))
                    if connector:
                        lines.append(connector)
                lines.extend(f"- {str(item).strip()}" for item in items if str(item).strip())
                return "\n".join(lines)
        # Generic fallback for unknown section dict.
        preferred = ["title", "text", "quote_text", "before_service", "after_service_word_count"]
        for key in preferred:
            value = _coerce_text(sec.get(key))
            if value:
                return value
        return _coerce_text(sec)

    # Non-dict fallback (or custom section key).
    return _coerce_text(sec)


class StudioState:
    def __init__(
        self,
        report_path: Path,
        output_path: Path,
        edits_path: Path,
        book_json_path: Path | None,
        reviewed_by: str,
        decision_source: str | None,
        reset: bool = False,
    ) -> None:
        self.lock = threading.RLock()
        self.report_path = report_path
        self.report = load_report(report_path)
        self.report["source_report"] = str(report_path)
        self.section_previews = {
            str(k): str(v)
            for k, v in (self.report.get("section_previews_by_key") or {}).items()
            if isinstance(k, str)
        }
        self.section_meta = {
            str(k): dict(v)
            for k, v in (self.report.get("section_meta_by_key") or {}).items()
            if isinstance(k, str) and isinstance(v, dict)
        }
        self.items = [parse_pending_item(raw) for raw in self.report.get("pending_sections", [])]
        self.total_pending = len(self.items)
        self.output_path = output_path
        self.edits_path = edits_path
        if book_json_path is None:
            source_book = str(self.report.get("source_book_json") or "").strip()
            if source_book:
                book_json_path = _resolve_report_relative(source_book, report_path)
        self.book_json_path = book_json_path
        self.book_data = _load_book_json(book_json_path)
        self.run_slug = infer_run_slug(report_path)
        self.review_socket = build_review_socket()
        self.agent_validation_by_day = _load_agent_validation(_default_agent_report_path(report_path))
        self.reviewed_by = reviewed_by
        self.decision_source = decision_source
        _ensure_decision_source_policy(self.reviewed_by, self.decision_source)
        seed_review_sections(
            socket=self.review_socket,
            run_slug=self.run_slug,
            book_data=self.book_data,
            section_previews=self.section_previews,
        )
        self.decision_map = (
            {}
            if reset
            else (
                load_review_decision_map(socket=self.review_socket, run_slug=self.run_slug)
                or load_existing_decisions(output_path, expected_source_report=report_path)
            )
        )
        self.edits_map = (
            {}
            if reset
            else (load_review_edits_map(socket=self.review_socket, run_slug=self.run_slug) or _load_edits(edits_path))
        )
        self.current_index = 0
        self.filter_mode = "pending"
        self.persist_decisions()
        self.persist_edits()

    def persist_decisions(self) -> None:
        write_decisions(
            output_path=self.output_path,
            report=self.report,
            decision_map=self.decision_map,
            mode="studio-web",
            total_pending=self.total_pending,
        )

    def persist_edits(self) -> None:
        edits = sorted(self.edits_map.values(), key=lambda e: (int(e["day"]), str(e["section"]).lower()))
        payload = {
            "source_report": str(self.report_path),
            "topic": self.report.get("topic"),
            "days": self.report.get("days"),
            "reviewed_by": self.reviewed_by,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "edits": edits,
        }
        _atomic_write_json(self.edits_path, payload)

    def _remaining(self):
        return unresolved_items(self.items, self.decision_map)

    def _items_for_filter(self) -> list:
        if self.filter_mode == "all":
            return list(self.items)
        if self.filter_mode == "pending":
            return self._remaining()
        if self.filter_mode in {"approved", "rejected"}:
            filtered = []
            for item in self.items:
                decision = self.decision_map.get(_decision_key(item.day, item.section))
                if decision and decision.get("decision") == self.filter_mode:
                    filtered.append(item)
            return filtered
        return self._remaining()

    def _current_item(self):
        visible = self._items_for_filter()
        if not visible:
            return None, visible
        if self.current_index >= len(visible):
            self.current_index = len(visible) - 1
        return visible[self.current_index], visible

    def _timeline(self) -> list[dict]:
        rows: list[dict] = []
        for item in self.items:
            key = _decision_key(item.day, item.section)
            decision = self.decision_map.get(key)
            edit = self.edits_map.get(key)
            rows.append(
                {
                    "day": item.day,
                    "section": item.section,
                    "key": _decision_key(item.day, item.section),
                    "section_label": format_section_label(item.section),
                    "decision": None if not decision else decision.get("decision"),
                    "reviewed_at_utc": None if not decision else decision.get("reviewed_at_utc"),
                    "has_edit": bool(edit and (edit.get("editor_plain") or edit.get("note"))),
                }
            )
        return rows

    def state_payload(self) -> dict:
        with self.lock:
            current, remaining = self._current_item()
            resolved = len(_sorted_decisions(self.decision_map))
            payload = {
                "topic": self.report.get("topic"),
                "days": self.report.get("days"),
                "total_pending": self.total_pending,
                "resolved": resolved,
                "remaining_count": len(remaining),
                "filter_mode": self.filter_mode,
                "filter_count": len(remaining),
                "output_file": self.output_path.name,
                "edits_file": self.edits_path.name,
                "book_json_file": None if self.book_json_path is None else self.book_json_path.name,
                "reviewed_by": self.reviewed_by,
                "current": None,
                "done": current is None,
                "timeline": self._timeline(),
            }
            if current is not None:
                key = _decision_key(current.day, current.section)
                edit = self.edits_map.get(key) or {}
                day_validation = self.agent_validation_by_day.get(str(current.day), {})
                validation_compare = {}
                if current.section == "scripture":
                    validation_compare = day_validation.get("scripture") or {}
                elif current.section == "timeless_wisdom":
                    validation_compare = day_validation.get("timeless_wisdom") or {}
                payload["current"] = {
                    "day": current.day,
                    "section": current.section,
                    "section_label": format_section_label(current.section),
                    "reader_heading": _reader_heading_for_section(current.section),
                    "position": self.current_index + 1,
                    "total_remaining": len(remaining),
                    "source_preview": (
                        _section_preview_from_book(self.book_data, current.day, current.section)
                        or self.section_previews.get(_decision_key(current.day, current.section))
                    ),
                    "original_preview": (
                        self.section_previews.get(_decision_key(current.day, current.section))
                        or _section_preview_from_book(self.book_data, current.day, current.section)
                    ),
                    "section_meta": self.section_meta.get(
                        _decision_key(current.day, current.section), {}
                    ),
                    "day_focus": (
                        str(
                            (
                                (self.book_data or {}).get("days", [])[current.day - 1].get("day_focus", "")
                                if self.book_data and isinstance((self.book_data or {}).get("days"), list) and len((self.book_data or {}).get("days", [])) >= current.day and isinstance((self.book_data or {}).get("days", [])[current.day - 1], dict)
                                else ""
                            )
                        ).strip()
                    ),
                    "grounding_evidence": (
                        _exposition_grounding_evidence(self.book_data, current.day)
                        if current.section == "exposition"
                        else []
                    ),
                    "prayer_trace_evidence": (
                        _prayer_trace_evidence(self.book_data, current.day)
                        if current.section == "prayer"
                        else []
                    ),
                    "quote_distribution": (
                        _quote_distribution(self.book_data)
                        if current.section == "timeless_wisdom"
                        else []
                    ),
                    "validation_compare": validation_compare,
                    "editor_html": edit.get("editor_html", ""),
                    "editor_plain": edit.get("editor_plain", ""),
                    "note": edit.get("note", ""),
                    "decision": self.decision_map.get(key),
                    "edit_updated_at_utc": edit.get("updated_at_utc", ""),
                }
            return payload

    def _requires_resolution_note(self, item) -> bool:
        day_validation = self.agent_validation_by_day.get(str(item.day), {})
        sec_validation = {}
        if item.section == "scripture":
            sec_validation = day_validation.get("scripture") or {}
        elif item.section == "timeless_wisdom":
            sec_validation = day_validation.get("timeless_wisdom") or {}
        discrepancy = bool(sec_validation.get("discrepancy"))
        status = str(sec_validation.get("status", "")).strip().lower()
        return discrepancy or status == "manual_required"

    def _record(self, decision: str, operator_note: str = "") -> None:
        current, remaining = self._current_item()
        if current is None:
            return
        note = operator_note.strip()
        if decision in {"approved", "rejected"} and self._requires_resolution_note(current) and not note:
            raise ValueError(
                "Resolution note required for validator discrepancy/manual reconciliation items."
            )
        record = {
            "day": current.day,
            "section": current.section,
            "decision": decision,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": self.reviewed_by,
        }
        if note:
            record["operator_note"] = note
        if self.decision_source is not None:
            record["decision_source"] = self.decision_source
        self.decision_map[_decision_key(current.day, current.section)] = record
        approved_payload = _section_payload_from_book(self.book_data, current.day, current.section)
        approved_preview = (
            self.edits_map.get(_decision_key(current.day, current.section), {}).get("editor_plain")
            or self.section_previews.get(_decision_key(current.day, current.section))
            or _section_preview_from_book(self.book_data, current.day, current.section)
        )
        save_review_decision(
            socket=self.review_socket,
            run_slug=self.run_slug,
            day_number=current.day,
            section_name=current.section,
            approval_decision=decision,
            operator_note=note,
            reviewed_by=self.reviewed_by,
            decision_source=self.decision_source,
            reviewed_at_utc=record["reviewed_at_utc"],
            approved_payload=approved_payload,
            approved_preview=str(approved_preview or ""),
        )
        self.persist_decisions()
        remaining_after = self._remaining()
        if self.current_index >= len(remaining_after):
            self.current_index = max(len(remaining_after) - 1, 0)

    def set_filter(self, filter_mode: str) -> dict:
        with self.lock:
            candidate = filter_mode.strip().lower()
            if candidate not in {"pending", "all", "approved", "rejected"}:
                raise ValueError(f"Unknown filter: {filter_mode}")
            self.filter_mode = candidate
            self.current_index = 0
            return self.state_payload()

    def jump_to(self, key: str) -> dict:
        with self.lock:
            target = key.strip()
            if not target:
                return self.state_payload()
            visible = self._items_for_filter()
            for idx, item in enumerate(visible):
                if _decision_key(item.day, item.section) == target:
                    self.current_index = idx
                    break
            return self.state_payload()

    def save_edit(self, editor_html: str, editor_plain: str, note: str) -> dict:
        with self.lock:
            current, _remaining = self._current_item()
            if current is None:
                return self.state_payload()
            key = _decision_key(current.day, current.section)
            self.edits_map[_decision_key(current.day, current.section)] = {
                "day": current.day,
                "section": current.section,
                "editor_html": editor_html,
                "editor_plain": editor_plain,
                "note": note,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            if self.book_data is not None and self.book_json_path is not None:
                changed = _apply_edit_to_book(
                    self.book_data,
                    day=current.day,
                    section=current.section,
                    editor_plain=editor_plain,
                )
                if changed:
                    _atomic_write_json(self.book_json_path, self.book_data)
            edited_payload = _section_payload_from_book(self.book_data, current.day, current.section)
            # Keep preview aligned with latest edit for this key.
            if editor_plain.strip():
                self.section_previews[key] = editor_plain
            save_review_edit(
                socket=self.review_socket,
                run_slug=self.run_slug,
                day_number=current.day,
                section_name=current.section,
                edited_payload=edited_payload,
                editor_html=editor_html,
                editor_plain=editor_plain,
                note=note,
                edited_at_utc=self.edits_map[key]["updated_at_utc"],
            )
            self.persist_edits()
            return self.state_payload()

    def apply_action(self, action: str, note: str = "") -> dict:
        with self.lock:
            if action == "approve":
                self._record("approved", operator_note=note)
            elif action == "reject":
                self._record("rejected", operator_note=note)
            elif action in {"skip", "next"}:
                remaining = self._remaining()
                if remaining:
                    self.current_index = (self.current_index + 1) % len(remaining)
            elif action == "prev":
                remaining = self._remaining()
                if remaining:
                    self.current_index = (self.current_index - 1) % len(remaining)
            else:
                raise ValueError(f"Unknown action: {action}")
            return self.state_payload()


def _html_page() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>DevG Review Studio</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f4f6fb;
      --panel: #ffffff;
      --text: #111827;
      --muted: #5f6b7d;
      --accent: #0f766e;
      --accent-2: #1d4ed8;
      --border: #d9e0ec;
      --button: #e7edf7;
      --button-hover: #d9e4f5;
      --editor: #ffffff;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0c1118;
        --panel: #141c27;
        --text: #f5f7fb;
        --muted: #afbad0;
        --accent: #2dd4bf;
        --accent-2: #60a5fa;
        --border: #344357;
        --button: #223044;
        --button-hover: #2b3e57;
        --editor: #0f1723;
      }
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, Segoe UI, sans-serif; }
    .shell { display: grid; grid-template-columns: 2fr 1fr; gap: 14px; padding: 14px; min-height: 100vh; }
    .shell.timeline-hidden { grid-template-columns: 1fr; }
    .shell.timeline-hidden #timeline-panel { display: none; }
    .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 14px; }
    .title { font-size: 28px; margin: 0 0 10px 0; }
    .meta { color: var(--muted); font-size: 14px; margin-bottom: 12px; }
    .focus { font-size: 36px; line-height: 1.2; margin: 8px 0 8px 0; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
    button {
      font-size: 18px; padding: 10px 14px; border-radius: 10px; border: 1px solid var(--border);
      background: var(--button); color: var(--text); cursor: pointer;
    }
    button:hover { background: var(--button-hover); }
    .danger { border-color: #b91c1c; }
    .editor {
      width: 100%; min-height: 220px; border: 1px solid var(--border); border-radius: 10px;
      padding: 12px; background: var(--editor); color: var(--text); font-size: 19px; line-height: 1.6;
      outline: none;
    }
    .note {
      width: 100%; min-height: 80px; border: 1px solid var(--border); border-radius: 10px;
      padding: 10px; background: var(--editor); color: var(--text); font-size: 15px;
      margin-top: 10px;
    }
    .caption { color: var(--muted); font-size: 13px; margin-top: 6px; }
    .source-box {
      width: 100%; min-height: 170px; border: 1px solid var(--border); border-radius: 10px;
      padding: 12px; background: var(--editor); color: var(--text); font-size: 17px; line-height: 1.5;
      white-space: pre-wrap; margin-top: 12px; max-height: 360px; overflow: auto;
    }
    .compact-box { min-height: 90px; max-height: 260px; font-size: 14px; line-height: 1.3; }
    .list { max-height: calc(100vh - 80px); overflow: auto; }
    .day-group { border: 1px solid var(--border); border-radius: 8px; margin-bottom: 10px; overflow: hidden; }
    .day-summary { cursor: pointer; padding: 8px 10px; font-weight: 600; display: flex; justify-content: space-between; gap: 8px; align-items: center; }
    .day-summary.pending { background: rgba(180, 83, 9, 0.14); color: var(--text); }
    .day-summary.complete { background: rgba(21, 128, 61, 0.14); color: var(--text); }
    .day-count { color: var(--muted); font-size: 12px; font-weight: 500; }
    .row { padding: 9px; border-radius: 8px; border: 1px solid var(--border); margin-bottom: 8px; font-size: 14px; }
    .row.pending { border-left: 4px solid #b45309; }
    .row.approved { border-left: 4px solid #15803d; }
    .row.rejected { border-left: 4px solid #b91c1c; }
    .kbd { color: var(--accent-2); font-weight: 600; }
    .source-card { border: 1px solid var(--border); border-radius: 8px; padding: 6px; margin-bottom: 6px; }
    .source-title { font-weight: 700; margin-bottom: 4px; }
    .source-meta { color: var(--muted); font-size: 12px; margin-bottom: 2px; line-height: 1.2; }
    .source-list { margin: 4px 0 0 18px; padding: 0; }
    .source-list li { margin: 0 0 2px 0; }
    mark { background: #facc15; color: #111827; border-radius: 3px; padding: 0 2px; }
    .split { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .split-col { border: 1px solid var(--border); border-radius: 8px; padding: 8px; background: var(--editor); max-height: 340px; overflow: auto; }
    @media (max-width: 980px) { .shell { grid-template-columns: 1fr; } .focus { font-size: 30px; } }
  </style>
</head>
<body>
  <div class=\"shell\" id=\"shell\">
    <section class=\"panel\" id=\"main-panel\">
      <h1 class=\"title\">DevG Review Studio (Detached)</h1>
      <div class=\"meta\" id=\"meta\"></div>
      <div class=\"focus\" id=\"focus\"></div>
      <div class=\"meta\" id=\"position\"></div>
      <div class=\"source-box compact-box\" id=\"editor-scope\" style=\"min-height:64px;\"></div>
      <div class=\"caption\">The section heading is fixed; the editor below changes the section body only.</div>

      <div class=\"toolbar\">
        <button onclick=\"act('approve')\">Approve (<span class=\"kbd\">A</span>)</button>
        <button class=\"danger\" onclick=\"act('reject')\">Reject (<span class=\"kbd\">R</span>)</button>
        <button onclick=\"act('skip')\">Skip (<span class=\"kbd\">S</span>)</button>
        <button onclick=\"act('prev')\">Prev (<span class=\"kbd\">&larr;</span>)</button>
        <button onclick=\"act('next')\">Next (<span class=\"kbd\">&rarr;</span>)</button>
        <button onclick=\"saveEdit()\">Save Edit (<span class=\"kbd\">Ctrl/Cmd+S</span>)</button>
        <button onclick=\"exitStudio()\">Exit</button>
        <button onclick=\"toggleTimeline()\">Toggle Timeline</button>
        <select id=\"filter\" onchange=\"setFilter(this.value)\">
          <option value=\"pending\">Pending</option>
          <option value=\"all\">All</option>
          <option value=\"approved\">Approved</option>
          <option value=\"rejected\">Rejected</option>
        </select>
        <select id=\"jump\"></select>
        <button onclick=\"jumpToSelected()\">Jump</button>
      </div>

      <div id=\"editor\" class=\"editor\" contenteditable=\"true\"></div>
      <div class=\"toolbar\" style=\"margin-top:8px;\">
        <button onclick=\"setEditView('clean')\">Clean Edit</button>
        <button onclick=\"setEditView('markup')\">Markup View</button>
      </div>
      <div class=\"caption\">Edits are written to review edits JSON and applied to the loaded book JSON.</div>
      <div id=\"markup\" class=\"source-box\" style=\"display:none; min-height:140px;\"></div>
      <div id=\"source\" class=\"source-box compact-box\" style=\"display:none;\"></div>
      <div class=\"caption\" id=\"source-caption\" style=\"display:none;\">Source content preview from book JSON (read-only; optional).</div>
      <div id=\"compare\" class=\"source-box\" style=\"min-height:120px;\"></div>
      <div class=\"caption\">Validator comparison (shows generated and validator text when available).</div>
      <textarea id=\"note\" class=\"note\" placeholder=\"Operator notes (optional)\"></textarea>
      <div class=\"caption\" id=\"save-status\">Not saved yet.</div>
      <div id=\"audit\" class=\"source-box\" style=\"min-height:110px;\"></div>
      <div class=\"caption\">Audit details for this section (decision/edit timestamps in local time).</div>
    </section>

    <aside class=\"panel\" id=\"timeline-panel\">
      <h2 style=\"margin-top:0;\">Section Timeline</h2>
      <div class=\"list\" id=\"timeline\"></div>
    </aside>
  </div>

  <script>
    let currentState = null;
    let editViewMode = 'clean';

    function toLocal(ts) {
      if (!ts) return '';
      const d = new Date(ts);
      if (Number.isNaN(d.getTime())) return ts;
      return d.toLocaleString();
    }

    function plainTextFromHtml(html) {
      const div = document.createElement('div');
      div.innerHTML = html;
      return (div.textContent || '').trim();
    }

    function escapeHtml(text) {
      return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    function textToHtml(text) {
      return escapeHtml(text).replace(/\\n/g, '<br>');
    }

    function buildLineMarkup(base, edited) {
      const baseLines = String(base || '').split('\\n');
      const editedLines = String(edited || '').split('\\n');
      const maxLen = Math.max(baseLines.length, editedLines.length);
      const out = [];
      for (let i = 0; i < maxLen; i++) {
        const b = baseLines[i] ?? '';
        const e = editedLines[i] ?? '';
        if (b === e) {
          out.push(`<div>${escapeHtml(e)}</div>`);
        } else {
          if (b) out.push(`<div style=\"opacity:0.75;\"><s>${escapeHtml(b)}</s></div>`);
          if (e) out.push(`<div><mark>${escapeHtml(e)}</mark></div>`);
        }
      }
      return out.join('');
    }

    function setEditView(mode) {
      editViewMode = mode;
      const editor = document.getElementById('editor');
      const markup = document.getElementById('markup');
      if (mode === 'markup') {
        editor.style.display = 'none';
        markup.style.display = 'block';
        const baseline = (currentState?.current?.original_preview) || '';
        const edited = plainTextFromHtml(editor.innerHTML || '');
        markup.innerHTML = buildLineMarkup(baseline, edited || baseline);
      } else {
        markup.style.display = 'none';
        editor.style.display = 'block';
      }
    }

    async function refresh() {
      const res = await fetch('/api/state');
      const state = await res.json();
      render(state);
    }

    async function act(action) {
      const note = document.getElementById('note').value || '';
      const res = await fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, note }),
      });
      const state = await res.json();
      if (state.error) {
        document.getElementById('save-status').textContent = state.error;
        return;
      }
      render(state);
    }

    async function saveEdit() {
      if (!currentState || currentState.done) return;
      const editor = document.getElementById('editor');
      const note = document.getElementById('note');
      const payload = {
        editor_html: editor.innerHTML,
        editor_plain: plainTextFromHtml(editor.innerHTML),
        note: note.value,
      };
      const res = await fetch('/api/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const state = await res.json();
      render(state);
      document.getElementById('save-status').textContent = `Saved ${new Date().toLocaleTimeString()}.`;
    }

    async function setFilter(mode) {
      const res = await fetch('/api/filter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filter: mode }),
      });
      const state = await res.json();
      render(state);
    }

    async function exitStudio() {
      try {
        await fetch('/api/exit', { method: 'POST' });
      } finally {
        window.close();
      }
    }

    async function jumpToSelected() {
      const jump = document.getElementById('jump');
      const key = jump.value || '';
      const res = await fetch('/api/jump', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });
      const state = await res.json();
      render(state);
    }

    function toggleTimeline() {
      const shell = document.getElementById('shell');
      shell.classList.toggle('timeline-hidden');
    }

    function renderTimeline(state) {
      const root = document.getElementById('timeline');
      root.innerHTML = '';
      const byDay = new Map();
      state.timeline.forEach((row) => {
        if (!byDay.has(row.day)) byDay.set(row.day, []);
        byDay.get(row.day).push(row);
      });

      const rowsForCurrentFilter = (rows) => rows.filter((row) => {
        if (state.filter_mode === 'all') return true;
        if (state.filter_mode === 'pending') return !row.decision;
        return row.decision === state.filter_mode;
      });

      let openedPending = false;
      [...byDay.keys()].sort((a, b) => a - b).forEach((dayNum) => {
        const allRows = byDay.get(dayNum) || [];
        const visibleRows = rowsForCurrentFilter(allRows);
        const pendingCount = allRows.filter((r) => !r.decision).length;
        const isPending = pendingCount > 0;
        const details = document.createElement('details');
        details.className = 'day-group';
        details.open = false;
        if (isPending && !openedPending) {
          details.open = true;
          openedPending = true;
        }
        const summary = document.createElement('summary');
        summary.className = `day-summary ${isPending ? 'pending' : 'complete'}`;
        summary.textContent = `Day ${dayNum} - ${isPending ? 'YELLOW' : 'GREEN'}`;
        const counts = document.createElement('span');
        counts.className = 'day-count';
        counts.textContent = `${pendingCount} pending, ${allRows.length - pendingCount} resolved`;
        summary.appendChild(counts);
        details.appendChild(summary);

        const groupBody = document.createElement('div');
        groupBody.style.padding = '8px';
        if (visibleRows.length === 0) {
          const empty = document.createElement('div');
          empty.className = 'caption';
          empty.textContent = `No sections in ${state.filter_mode} view for day ${dayNum}.`;
          groupBody.appendChild(empty);
        }
        visibleRows.forEach((row) => {
          const cls = row.decision ? row.decision : 'pending';
          const el = document.createElement('div');
          el.className = `row ${cls}`;
          const reviewed = row.reviewed_at_utc ? ` | reviewed ${toLocal(row.reviewed_at_utc)}` : '';
          const edit = row.has_edit ? ' | edited' : '';
          el.textContent = `Day ${row.day} - ${row.section_label} | ${row.decision || 'pending'}${reviewed}${edit}`;
          el.onclick = () => jumpToKey(row.key);
          groupBody.appendChild(el);
        });
        details.appendChild(groupBody);
        root.appendChild(details);
      });
    }

    async function jumpToKey(key) {
      const res = await fetch('/api/jump', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });
      const state = await res.json();
      render(state);
    }

    function render(state) {
      currentState = state;
      document.getElementById('filter').value = state.filter_mode || 'pending';
      document.getElementById('meta').textContent =
        `Topic: ${state.topic ?? 'N/A'} | Days: ${state.days ?? 'N/A'} | Resolved: ${state.resolved}/${state.total_pending} | Remaining: ${state.remaining_count} | View: ${state.filter_mode} (${state.filter_count}) | Reviewer: ${state.reviewed_by} | Decisions: ${state.output_file} | Edits: ${state.edits_file} | Book: ${state.book_json_file ?? 'none'}`;

      renderTimeline(state);
      const jump = document.getElementById('jump');
      jump.innerHTML = '';
      state.timeline.forEach((row) => {
        if ((state.filter_mode === 'all') ||
            (state.filter_mode === 'pending' && !row.decision) ||
            (state.filter_mode === row.decision)) {
          const opt = document.createElement('option');
          opt.value = row.key;
          opt.textContent = `Day ${row.day} - ${row.section_label}`;
          jump.appendChild(opt);
        }
      });

      if (state.done) {
        document.getElementById('focus').textContent = state.filter_mode === 'pending'
          ? 'All pending sections resolved.'
          : `No sections in ${state.filter_mode} view.`;
        document.getElementById('position').textContent = 'You can close this tab and stop the server with Ctrl+C.';
        document.getElementById('editor-scope').textContent = '';
        document.getElementById('editor').innerHTML = '';
        document.getElementById('source').textContent = '';
        document.getElementById('compare').textContent = '';
        document.getElementById('note').value = '';
        document.getElementById('audit').textContent = '';
        return;
      }

      const dayFocus = state.current.day_focus || 'N/A';
      document.getElementById('focus').textContent = `Day ${state.current.day} - ${state.current.section_label}`;
      const readerHeading = state.current.reader_heading || state.current.section_label;
      document.getElementById('editor-scope').textContent =
        `Volume topic: ${state.topic || 'N/A'}\nDay topic: ${dayFocus}\nReader heading: ${readerHeading}\nEditable body: ${state.current.section_label} content only.`;
      const m = state.current.section_meta || {};
      let retrievalValue = m.retrieval_source || '';
      if (!retrievalValue) {
        retrievalValue = state.current.section === 'scripture' ? 'missing' : 'not-applicable';
      }
      document.getElementById('position').textContent =
        `Item ${state.current.position}/${state.current.total_remaining}. Verification: ${m.verification_status || 'n/a'} | Retrieval: ${retrievalValue} | Approval: ${m.approval_status || 'pending'}`;
      const hasSavedEdit = Boolean((state.current.editor_plain || '').trim() || (state.current.editor_html || '').trim());
      if (hasSavedEdit) {
        document.getElementById('editor').innerHTML = state.current.editor_html || textToHtml(state.current.editor_plain || '');
      } else {
        // Seed editor with current source content for first-pass editing.
        document.getElementById('editor').innerHTML = textToHtml(state.current.source_preview || '');
      }
      if (editViewMode === 'markup') {
        setEditView('markup');
      }
      const source = document.getElementById('source');
      const sourceCaption = document.getElementById('source-caption');
      if (state.current.section === 'exposition' && (state.current.grounding_evidence || []).length > 0) {
        source.style.display = 'block';
        sourceCaption.style.display = 'block';
        const evidenceBlocks = [];
        evidenceBlocks.push(`<div style="margin-bottom:10px;"><strong>Exposition source evidence</strong><br><span class="caption">Selected support only. Broader retrieval remains in research memory.</span></div>`);
        (state.current.grounding_evidence || []).forEach((ev) => {
          const sourceTitles = [...new Set((ev.source_titles || []).map((s) => String(s)))].join(' | ') || 'Unknown source';
          const sourceIds = [...new Set((ev.source_ids || []).map((s) => String(s)))].join(' | ') || 'n/a';
          const scores = (ev.similarity_scores || []).map((n) => Number(n).toFixed(3)).join(', ') || 'n/a';
          const originalExcerpts = (ev.original_excerpts_used || []).map((x) => String(x)).filter(Boolean);
          const excerptFlags = (ev.excerpts_modernized || []).map((x) => Boolean(x));
          const modernizationLabel = String(ev.modernization_label || '');
          const excerpt = String(ev.excerpt_used || '');
          const escapedExcerpt = excerpt
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
          const context = String(ev.context_snippet || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
          const informed = String(ev.how_retrieval_informed_paragraph || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
          evidenceBlocks.push(
            `<div class="source-card">
              <div class="source-title">P${ev.paragraph_number} ${ev.paragraph_name || ''}</div>
              <div class="source-meta">Context source highlighted below.</div>
              <div class="source-meta">Source IDs: ${sourceIds}</div>
              <div class="source-meta">Similarity scores: ${scores}</div>
              ${excerptFlags.some(Boolean) ? `<div class="source-meta">${modernizationLabel || 'Language modernized by AI'} shown for readability; original wording preserved below.</div>` : ''}
              <div><mark>[${escapedExcerpt}]</mark></div>
              ${originalExcerpts.length ? `<div class="source-meta" style="margin-top:6px;">Original wording:</div><ul class="source-list">${originalExcerpts.map((x) => `<li>[${String(x).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}]</li>`).join('')}</ul>` : ''}
              <div class="source-meta" style="margin-top:6px;">Context in exposition:</div>
              <div>${context || '(No direct phrase match in exposition text.)'}</div>
              <div class="source-meta" style="margin-top:6px;">- ${sourceTitles}</div>
              <div class="source-meta" style="margin-top:6px;">Retrieval rationale:</div>
              <div>${informed || '(No rationale recorded.)'}</div>
            </div>`
          );
        });
        const exText = String(state.current.source_preview || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        source.innerHTML =
          `<div class="split">
            <div class="split-col">
              <div class="source-title">Exposition</div>
              <div>${exText || '(No exposition text loaded.)'}</div>
            </div>
            <div class="split-col">${evidenceBlocks.join('')}</div>
          </div>`;
      } else if (state.current.section === 'prayer' && (state.current.prayer_trace_evidence || []).length > 0) {
        source.style.display = 'block';
        sourceCaption.style.display = 'block';
        const blocks = [];
        blocks.push(`<div style="margin-bottom:10px;"><strong>Prayer trace map evidence</strong></div>`);
        (state.current.prayer_trace_evidence || []).forEach((ev, idx) => {
          const element = String(ev.element_text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
          const type = String(ev.source_type || 'n/a');
          const ref = String(ev.source_reference || 'n/a');
          blocks.push(
            `<div class="source-card">
              <div class="source-title">Element ${idx + 1}</div>
              <div class="source-meta">Source type: ${type} | Source reference: ${ref}</div>
              <div>${element}</div>
            </div>`
          );
        });
        source.innerHTML = blocks.join('');
      } else if (state.current.section === 'timeless_wisdom') {
        source.style.display = 'block';
        sourceCaption.style.display = 'block';
        const dist = state.current.quote_distribution || [];
        const rows = dist.map((r) => `<div>${String(r.author)}: ${Number(r.count)}</div>`).join('');
        source.innerHTML =
          `<div class="source-card">
            <div class="source-title">Quote Distribution (Current Volume)</div>
            <div class="source-meta">Quick check for author diversity.</div>
            ${rows || '(No quote distribution data available.)'}
          </div>`;
      } else {
        source.style.display = 'none';
        sourceCaption.style.display = 'none';
        source.textContent = '';
      }
      const compare = document.getElementById('compare');
      const vc = state.current.validation_compare || {};
      if ((state.current.section === 'scripture' || state.current.section === 'timeless_wisdom') &&
          (vc.original_source || vc.validator_source || vc.discrepancy === true || vc.status === 'manual_required')) {
        const g = String(vc.generated_text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const v = String(vc.validator_text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const os = String(vc.original_source || 'unknown');
        const vs = String(vc.validator_source || 'unknown');
        if (vc.discrepancy === true) {
          compare.innerHTML =
            `<div><strong style="color:#b91c1c;">Discrepancy detected</strong></div>
             <div class="source-meta">Original source: ${os} | Validator source: ${vs}</div>
             <div class="source-meta" style="margin-top:8px;">Generated version</div>
             <div>${g || '(missing)'}</div>
             <div class="source-meta" style="margin-top:8px;">Validator version</div>
             <div>${v || '(missing - use Logos/manual check)'}</div>
             <div class="source-meta" style="margin-top:8px;color:#b91c1c;"><strong>Resolution note is required before Approve/Reject.</strong></div>`;
        } else if (vc.status === 'manual_required') {
          compare.innerHTML =
            `<div><strong style="color:#b45309;">Manual reconciliation required</strong></div>
             <div class="source-meta">Original source: ${os} | Validator source: ${vs}</div>
             <div>Use Logos/manual check only if needed.</div>
             <div class="source-meta" style="margin-top:8px;color:#b45309;"><strong>Resolution note is required before Approve/Reject.</strong></div>`;
        } else {
          compare.innerHTML =
            `<div><strong style="color:#15803d;">Stored and validator text agree.</strong></div>
             <div class="source-meta">Original source: ${os} | Validator source: ${vs}</div>`;
        }
      } else {
        compare.textContent = '(No validator text comparison for this section.)';
      }
      document.getElementById('note').value = state.current.note || '';
      const decision = state.current.decision;
      const decisionText = decision
        ? `Decision: ${decision.decision} by ${decision.reviewed_by || 'n/a'} at ${toLocal(decision.reviewed_at_utc)}${decision.operator_note ? ` | note: ${decision.operator_note}` : ''}`
        : 'Decision: pending';
      const editText = state.current.edit_updated_at_utc
        ? `Latest edit: ${toLocal(state.current.edit_updated_at_utc)}`
        : 'Latest edit: none';
      const sectionKey = m.section_key ? `Section key: ${m.section_key}` : '';
      const validatorMeta = m.validator_source
        ? `Validator: ${m.validator_source} (${m.validator_status || 'n/a'})`
        : 'Validator: n/a';
      const retrievalMeta = m.retrieved_at_utc
        ? `Retrieved: ${toLocal(m.retrieved_at_utc)}`
        : 'Retrieved: n/a';
      const artifactMeta = [m.grounding_map_id || '', m.prayer_trace_map_id || ''].filter(Boolean).join(' | ');
      document.getElementById('audit').textContent = `${decisionText}\n${editText}\n${sectionKey}\n${validatorMeta}\n${retrievalMeta}${artifactMeta ? `\nArtifacts: ${artifactMeta}` : ''}`;
    }

    function isEditableTarget(target) {
      if (!target) return false;
      const tag = (target.tagName || '').toLowerCase();
      if (tag === 'textarea' || tag === 'input' || tag === 'select') return true;
      return Boolean(target.isContentEditable);
    }

    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveEdit();
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (isEditableTarget(e.target)) return;
      if (e.key === 'a' || e.key === 'A') act('approve');
      else if (e.key === 'r' || e.key === 'R') act('reject');
      else if (e.key === 's' || e.key === 'S') act('skip');
      else if (e.key === 'ArrowLeft') act('prev');
      else if (e.key === 'ArrowRight') act('next');
    });

    refresh();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "DevGReviewStudio/1.0"

    def _write_json(self, payload: dict, code: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _write_html(self, text: str, code: int = HTTPStatus.OK) -> None:
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._write_html(_html_page())
            return
        if self.path == "/api/state":
            self._write_json(self.server.app_state.state_payload())  # type: ignore[attr-defined]
            return
        self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
            if self.path == "/api/action":
                action = str(payload.get("action", ""))
                note = str(payload.get("note", ""))
                state = self.server.app_state.apply_action(action, note=note)  # type: ignore[attr-defined]
                self._write_json(state)
                return
            if self.path == "/api/filter":
                mode = str(payload.get("filter", "pending"))
                state = self.server.app_state.set_filter(mode)  # type: ignore[attr-defined]
                self._write_json(state)
                return
            if self.path == "/api/jump":
                key = str(payload.get("key", ""))
                state = self.server.app_state.jump_to(key)  # type: ignore[attr-defined]
                self._write_json(state)
                return
            if self.path == "/api/exit":
                self._write_json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()  # type: ignore[attr-defined]
                return
            if self.path == "/api/edit":
                state = self.server.app_state.save_edit(  # type: ignore[attr-defined]
                    editor_html=str(payload.get("editor_html", "")),
                    editor_plain=str(payload.get("editor_plain", "")),
                    note=str(payload.get("note", "")),
                )
                self._write_json(state)
                return
            self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Open detached review studio (dark mode + WYSIWYG draft editing). "
            "Writes approval decisions plus a separate edits JSON file."
        )
    )
    parser.add_argument("--report", required=True, help="Path to approval-gate report JSON")
    parser.add_argument("--out", help="Output decisions JSON path")
    parser.add_argument("--edits-out", help="Output review edits JSON path")
    parser.add_argument(
        "--book-json",
        help="Optional DevotionalBook JSON path for read-only section content preview.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Ignore existing decisions/edits and start this report from scratch.",
    )
    parser.add_argument(
        "--reviewed-by",
        default=default_reviewed_by(),
        help="Reviewer identifier stored in decision metadata.",
    )
    parser.add_argument(
        "--decision-source",
        help=(
            "Decision provenance label. Required when --reviewed-by starts with 'agent:'. "
            "For humans this is optional."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host bind address.")
    parser.add_argument("--port", type=int, default=8766, help="Port bind address.")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not auto-open browser tab.",
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    output_path = _build_output_path(report_path, args.out)
    edits_path = _build_edits_path(report_path, args.edits_out)
    book_json_path = Path(args.book_json) if args.book_json else None
    decision_source = args.decision_source.strip() if args.decision_source else None

    app_state = StudioState(
        report_path=report_path,
        output_path=output_path,
        edits_path=edits_path,
        book_json_path=book_json_path,
        reviewed_by=args.reviewed_by,
        decision_source=decision_source,
        reset=args.reset,
    )

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.app_state = app_state  # type: ignore[attr-defined]
    url = f"http://{args.host}:{args.port}/"
    print(f"STUDIO_URL={url}")
    print(f"DECISIONS={output_path}")
    print(f"EDITS={edits_path}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
