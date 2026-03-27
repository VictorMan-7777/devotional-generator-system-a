from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.persistence.adapters.sqlite_adapter import SQLiteRegistrySocket
from src.persistence.paths import default_registry_db_path
from src.rag.research_memory import (
    reset_exposition_candidate_markers,
    reset_quote_candidate_markers,
)


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _artifact_candidates(meta_path: Path, meta: dict) -> list[Path]:
    explicit = [
        meta.get("book_json_path"),
        meta.get("approval_report_path"),
        meta.get("approval_decisions_path"),
        meta.get("agent_validation_report_path"),
        meta.get("audit_linkage_path"),
        meta.get("preview_pdf_path"),
    ]
    paths = [Path(str(p)) for p in explicit if str(p or "").strip()]
    if meta_path not in paths:
        paths.append(meta_path)
    run_slug = str(meta.get("run_slug") or "").strip()
    if run_slug:
        base = meta_path.parent
        for candidate in base.glob(f"{run_slug}__*"):
            if candidate not in paths:
                paths.append(candidate)
    return paths


def _resolve_meta_relative_path(meta_path: Path, path_value: str | None) -> Path | None:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parents[1] / candidate


def _research_scope(meta_path: Path, meta: dict) -> tuple[set[str], set[str]]:
    book_path = _resolve_meta_relative_path(meta_path, meta.get("book_json_path"))
    if book_path is None or not book_path.exists():
        return set(), set()
    book = _load_json(book_path)
    days = book.get("days")
    if not isinstance(days, list):
        return set(), set()
    references: set[str] = set()
    topics: set[str] = set()
    for day in days:
        if not isinstance(day, dict):
            continue
        scripture = day.get("scripture") or {}
        if isinstance(scripture, dict):
            reference = str(scripture.get("reference") or "").strip()
            if reference:
                references.add(reference)
        day_focus = str(day.get("day_focus") or "").strip()
        if day_focus:
            topics.add(day_focus)
    run_topic = str(meta.get("topic") or "").strip()
    if run_topic:
        topics.add(run_topic)
    return references, topics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Purge a previous run's artifacts and registry placeholders before regeneration."
    )
    parser.add_argument("--meta", required=True, help="Path to run __meta.json")
    parser.add_argument(
        "--db-path",
        default=None,
        help="SQLite registry DB path for persisted series/volume state.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Only purge registry state; keep files on disk.",
    )
    parser.add_argument(
        "--keep-research-memory",
        action="store_true",
        help="Keep quote/exposition research memory for this run's scriptures/topics.",
    )
    args = parser.parse_args(argv)

    meta_path = Path(args.meta)
    if not meta_path.exists():
        raise FileNotFoundError(f"Meta file not found: {meta_path}")

    meta = _load_json(meta_path)
    volume_id = str(meta.get("volume_id") or "").strip()
    series_id = str(meta.get("series_id") or "").strip()
    standalone = bool(meta.get("standalone_volume"))

    db_path = Path(args.db_path) if args.db_path else default_registry_db_path()

    deleted_volume = False
    if volume_id:
        socket = SQLiteRegistrySocket(db_path=db_path)
        deleted_volume = socket.delete_volume(
            volume_id,
            delete_series_if_orphan=(standalone or not bool(series_id)),
        )

    reset_quote_memory = 0
    reset_exposition_memory = 0
    if not args.keep_research_memory:
        references, topics = _research_scope(meta_path, meta)
        reset_quote_memory = reset_quote_candidate_markers(
            db_path=db_path,
            scripture_references=sorted(references),
            topics=sorted(topics),
        )
        reset_exposition_memory = reset_exposition_candidate_markers(
            db_path=db_path,
            passage_references=sorted(references),
            topics=sorted(topics),
        )

    removed: list[str] = []
    if not args.keep_artifacts:
        for candidate in _artifact_candidates(meta_path, meta):
            if candidate.exists():
                candidate.unlink()
                removed.append(str(candidate))

    print(f"META={meta_path}")
    print(f"VOLUME_ID={volume_id}")
    print(f"SERIES_ID={series_id}")
    print(f"STANDALONE={standalone}")
    print(f"REGISTRY_VOLUME_DELETED={deleted_volume}")
    print(f"QUOTE_MEMORY_MARKERS_RESET={reset_quote_memory}")
    print(f"EXPOSITION_MEMORY_MARKERS_RESET={reset_exposition_memory}")
    print(f"ARTIFACTS_REMOVED={len(removed)}")
    for path in removed:
        print(f"REMOVED={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
