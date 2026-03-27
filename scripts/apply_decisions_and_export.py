from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.review.run_pending_approvals import load_existing_decisions
from src.api.export_gate import ExportGate
from src.api.pdf_export import export_pdf
from src.models.devotional import DevotionalBook, OutputMode, SectionApprovalStatus
from src.rendering.engine import DocumentRenderer
from src.review_store import apply_review_state_to_book, build_review_socket, infer_run_slug

_SECTION_NAME_MAP = {
    "timeless wisdom": "timeless_wisdom",
    "timeless_wisdom": "timeless_wisdom",
    "scripture": "scripture",
    "exposition": "exposition",
    "be still": "be_still",
    "be_still": "be_still",
    "action steps": "action_steps",
    "action_steps": "action_steps",
    "prayer": "prayer",
    "sending prompt": "sending_prompt",
    "sending_prompt": "sending_prompt",
    "day7": "day7",
    "day 7": "day7",
    "day_7": "day7",
}


def _normalize_section_name(section: str) -> str:
    key = " ".join(str(section or "").strip().lower().replace("-", " ").replace("_", " ").split())
    if key in _SECTION_NAME_MAP:
        return _SECTION_NAME_MAP[key]
    candidate = key.replace(" ", "_")
    if candidate in {
        "timeless_wisdom",
        "scripture",
        "exposition",
        "be_still",
        "action_steps",
        "prayer",
        "sending_prompt",
        "day7",
    }:
        return candidate
    raise ValueError(f"Unknown section name in decisions: {section!r}")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _default_pdf_path(book_json: Path, output_mode: OutputMode) -> Path:
    name = book_json.name
    if name.endswith("__book.json"):
        suffix = "__reviewed-proof.pdf" if output_mode == OutputMode.PERSONAL else f"__{output_mode.value}.pdf"
        return book_json.with_name(name.replace("__book.json", suffix))
    return book_json.with_suffix(".pdf")


def _load_book(path: Path) -> DevotionalBook:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return DevotionalBook.model_validate(payload)


def _find_day(book: DevotionalBook, day_number: int):
    for day in book.days:
        if int(day.day_number) == int(day_number):
            return day
    return None


def _apply_decisions(book: DevotionalBook, decisions_path: Path) -> tuple[int, int, int]:
    decision_map = load_existing_decisions(decisions_path)
    applied = 0
    skipped = 0
    ignored = 0
    for record in decision_map.values():
        decision = str(record.get("decision", "")).strip().lower()
        if decision == "skipped":
            skipped += 1
            continue
        if decision not in {"approved", "rejected"}:
            ignored += 1
            continue

        day_number = int(record["day"])
        section_name = _normalize_section_name(str(record["section"]))
        day = _find_day(book, day_number)
        if day is None:
            raise ValueError(f"Decision references missing day {day_number}")

        section_obj = getattr(day, section_name, None)
        if section_obj is None:
            raise ValueError(
                f"Decision references unavailable section '{section_name}' on day {day_number}"
            )

        section_obj.approval_status = (
            SectionApprovalStatus.APPROVED if decision == "approved" else SectionApprovalStatus.REJECTED
        )
        applied += 1

    return applied, skipped, ignored


def run_apply_decisions_and_export(
    *,
    book_json_path: Path,
    decisions_json_path: Path,
    out_pdf_path: Path | None = None,
    output_mode: OutputMode = OutputMode.PUBLISH_READY,
) -> tuple[Path | None, str | None, int, int, int]:
    book = _load_book(book_json_path)
    review_socket = build_review_socket()
    run_slug = infer_run_slug(book_json_path)
    apply_review_state_to_book(socket=review_socket, run_slug=run_slug, book=book)
    applied, skipped, ignored = _apply_decisions(book, decisions_json_path)

    # Persist mutated book first so state transitions are durable/auditable.
    _atomic_write_json(book_json_path, book.model_dump(mode="json"))

    gate = ExportGate().check_exportability(book, OutputMode.PUBLISH_READY)
    if output_mode == OutputMode.PUBLISH_READY and not gate.exportable:
        return None, gate.blocked_reason, applied, skipped, ignored

    target_pdf = out_pdf_path or _default_pdf_path(book_json_path, output_mode)
    doc = DocumentRenderer().render(book, OutputMode.PUBLISH_READY)
    export_mode = "reviewed-proof" if output_mode == OutputMode.PERSONAL else output_mode.value
    pdf_bytes = export_pdf(doc, output_mode=export_mode)
    target_pdf.write_bytes(pdf_bytes)
    return target_pdf, None, applied, skipped, ignored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply approval decisions to a __book.json file and emit publish-ready PDF when exportable."
        )
    )
    parser.add_argument("--book-json", required=True, help="Path to __book.json")
    parser.add_argument("--decisions-json", required=True, help="Path to __approval-decisions.json")
    parser.add_argument("--out-pdf", help="Optional output PDF path")
    parser.add_argument(
        "--output-mode",
        choices=[OutputMode.PERSONAL.value, OutputMode.PUBLISH_READY.value],
        default=OutputMode.PUBLISH_READY.value,
        help="Export mode: personal emits a reviewed-proof PDF, publish-ready emits the final PDF.",
    )
    args = parser.parse_args(argv)

    book_path = Path(args.book_json)
    decisions_path = Path(args.decisions_json)
    out_pdf = Path(args.out_pdf) if args.out_pdf else None
    output_mode = OutputMode(args.output_mode)

    if not book_path.exists():
        raise FileNotFoundError(f"Book JSON not found: {book_path}")
    if not decisions_path.exists():
        raise FileNotFoundError(f"Decisions JSON not found: {decisions_path}")

    pdf_path, blocked_reason, applied, skipped, ignored = run_apply_decisions_and_export(
        book_json_path=book_path,
        decisions_json_path=decisions_path,
        out_pdf_path=out_pdf,
        output_mode=output_mode,
    )

    print(f"BOOK={book_path}")
    print(f"DECISIONS={decisions_path}")
    print(f"APPLIED={applied}")
    print(f"SKIPPED={skipped}")
    print(f"IGNORED={ignored}")

    if pdf_path is None:
        print(f"BLOCKED_REASON={blocked_reason or 'unknown'}")
        return 2

    print(f"PDF={pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
