"""acquisition_librarian.py — Orchestrates the escalation pipeline from
Research Librarian thin-bundle detection to verified resources in ExpositionRAG.

Pipeline stages and request statuses:
  requested     → initial thin-bundle detection
  escalated     → acquisition librarian has been notified
  downloading   → source text is being fetched for cataloged-but-unindexed holdings
  indexing      → source text is being chunked into excerpt_catalog
  card_review   → card drafted, awaiting Librarian Trainer verification
  ready         → resources verified and visible to ExpositionRAG
  answered      → bundle sufficient, no further action needed
  blocked       → no accessible source text found after all attempts

Entry points:
  escalate_for_passage()  — called by research_librarian when bundle is thin.
  process_pending_escalations()  — batch processor for queued escalations.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.rag.library_acquisition import (
    LIBRARY_ROOT,
    RESOURCES_ROOT,
    search_archive_candidates,
)
from src.rag.library_cards import draft_and_evaluate_card
from src.rag.library_requests import (
    list_resource_acquisition_requests,
    request_resource_acquisition,
    update_resource_acquisition_request,
)
from src.persistence.paths import default_registry_db_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_INDEXER_RESOURCES_CONFIG = (
    Path(__file__).resolve().parents[2] / "scripts" / "library" / "index_source_texts.py"
)

# Minimum excerpt_catalog rows for a resource to be considered indexed.
_INDEX_THRESHOLD = 10

# How many archive.org candidates to evaluate per acquisition search.
_MAX_CANDIDATES = 3


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ---------------------------------------------------------------------------
# Step 1 — Identify undownloaded holdings that cover the target passage
# ---------------------------------------------------------------------------

def _bible_book_from_reference(reference: str) -> str:
    """Extract canonical Bible book name from a scripture reference."""
    match = re.match(r"^(\d\s+)?([A-Za-z]+)", reference.strip())
    if match:
        numbered = (match.group(1) or "").strip()
        book = match.group(2).strip()
        return f"{numbered} {book}".strip() if numbered else book
    return ""


def _holding_covers_book(holding: dict[str, Any], book_name: str) -> bool:
    """Return True if a holding record plausibly covers the target Bible book.

    Holdings from whole-Bible commentaries always return True.  Dictionary and
    reference works also return True (they cover all books by definition).
    Single-book or topical resources are excluded unless the book name appears
    in covered_books or the resource title.
    """
    resource_type = str(holding.get("resource_type", "")).lower()
    scope = str(holding.get("scope", "")).lower()
    if scope in ("whole_bible", "reference") or resource_type in (
        "whole_bible_commentary", "dictionary", "encyclopedia", "reference_work"
    ):
        return True
    covered = [str(b).lower() for b in (holding.get("covered_books") or [])]
    if book_name.lower() in covered:
        return True
    title = str(holding.get("title", "")).lower()
    return book_name.lower() in title


def find_undownloaded_holdings(bible_book: str) -> list[dict[str, Any]]:
    """Return holdings that have a source URL but no source.txt, and cover bible_book."""
    candidates = []
    if not RESOURCES_ROOT.exists():
        return candidates
    for resource_dir in sorted(RESOURCES_ROOT.iterdir()):
        if not resource_dir.is_dir():
            continue
        holding_path = resource_dir / "holding.json"
        source_txt = resource_dir / "source.txt"
        if source_txt.exists() or not holding_path.exists():
            continue
        try:
            holding = json.loads(holding_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Need a download URL
        url = (
            str(holding.get("download_url") or "").strip()
            or str(holding.get("selected_source_url") or "").strip()
        )
        if not url:
            continue
        if not _holding_covers_book(holding, bible_book):
            continue
        candidates.append({
            "slug": resource_dir.name,
            "holding_path": str(holding_path),
            "resource_dir": str(resource_dir),
            "download_url": url,
            "title": str(holding.get("title", resource_dir.name)),
            "author": str(holding.get("author_or_editor", "")),
        })
    return candidates


# ---------------------------------------------------------------------------
# Step 2 — Download source text
# ---------------------------------------------------------------------------

def download_source_text(slug: str, url: str) -> tuple[bool, str]:
    """Download a resource's source text from url into resources/{slug}/source.txt.

    Returns (success, message).
    """
    resource_dir = RESOURCES_ROOT / slug
    resource_dir.mkdir(parents=True, exist_ok=True)
    target = resource_dir / "source.txt"
    if target.exists():
        return True, f"{slug}: source.txt already exists"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 DevG LibraryAcquisition"})
        with urlopen(req, timeout=120) as resp:
            if resp.status not in (200,):
                return False, f"{slug}: HTTP {resp.status}"
            data = resp.read()
        target.write_bytes(data)
        return True, f"{slug}: downloaded {len(data):,} bytes → source.txt"
    except Exception as exc:
        return False, f"{slug}: download failed — {exc}"


# ---------------------------------------------------------------------------
# Step 3 — Index a newly downloaded resource
# ---------------------------------------------------------------------------

def index_resource_into_catalog(
    slug: str,
    source_title: str,
    author: str,
    source_type: str = "commentary",
    skip_header_lines: int = 60,
    db_path: Path | None = None,
) -> int:
    """Index data/library/resources/{slug}/source.txt into excerpt_catalog.

    Delegates to the same logic as scripts/library/index_source_texts.py but
    without requiring the script to be re-run manually.

    Returns the number of new rows inserted (0 if already indexed or no source.txt).
    """
    # Import inline to avoid circular imports; ensure scripts/ is on sys.path
    import sys as _sys
    _scripts_root = str(Path(__file__).resolve().parents[2])
    if _scripts_root not in _sys.path:
        _sys.path.insert(0, _scripts_root)
    from scripts.library.index_source_texts import (  # type: ignore[import]
        _connect, _ensure_schema, _already_indexed, index_resource,
    )
    db = db_path or default_registry_db_path()
    conn = _connect(db)
    _ensure_schema(conn)
    resource_config = {
        "slug": slug,
        "source_title": source_title,
        "author": author,
        "source_type": source_type,
        "skip_header_lines": skip_header_lines,
    }
    n = index_resource(resource_config, conn)
    conn.close()
    return n


# ---------------------------------------------------------------------------
# Step 4 — Draft library card for newly indexed resource
# ---------------------------------------------------------------------------

def _draft_card_for_slug(slug: str) -> dict[str, Any]:
    """Draft and evaluate a library card for a newly indexed holding."""
    holding_path = RESOURCES_ROOT / slug / "holding.json"
    if not holding_path.exists():
        return {"outcome": "skipped", "reason": "no holding.json"}
    try:
        result = draft_and_evaluate_card(holding_path)
        return result
    except Exception as exc:
        return {"outcome": "error", "reason": str(exc)}


# ---------------------------------------------------------------------------
# Step 5 — Search archive.org for new resources (if existing holdings insufficient)
# ---------------------------------------------------------------------------

def search_and_acquire_new_resource(
    bible_book: str,
) -> dict[str, Any]:
    """Search archive.org for a public-domain commentary covering bible_book.

    Tries up to _MAX_CANDIDATES search results.  Downloads the first accessible
    DjVuTXT/OCR text.  Returns acquisition result dict.
    """
    # Build search terms targeting Bible commentary for this book
    search_title = f"Commentary on the Book of {bible_book}"
    search_author = ""  # open search — any author
    try:
        candidates = search_archive_candidates(search_title, search_author)
    except Exception as exc:
        return {"status": "blocked", "reason": f"archive.org search failed: {exc}"}

    for candidate in candidates[:_MAX_CANDIDATES]:
        if not candidate.download_url:
            continue
        slug = _slug(candidate.title)[:50]
        resource_dir = RESOURCES_ROOT / slug
        if (resource_dir / "source.txt").exists():
            continue  # already have it
        ok, msg = download_source_text(slug, candidate.download_url)
        if ok:
            # Save a minimal holding.json so card-drafting works
            holding = {
                "title": candidate.title,
                "author_or_editor": candidate.author,
                "resource_type": "whole_bible_commentary",
                "scope": "whole_bible",
                "acquisition_status": "acquired",
                "selected_source_url": candidate.source_url,
                "download_url": candidate.download_url,
                "local_asset_path": str(resource_dir / "source.txt"),
            }
            resource_dir.mkdir(parents=True, exist_ok=True)
            (resource_dir / "holding.json").write_text(json.dumps(holding, indent=2))
            return {
                "status": "acquired",
                "slug": slug,
                "title": candidate.title,
                "author": candidate.author,
                "message": msg,
            }

    return {
        "status": "blocked",
        "reason": (
            f"No accessible public-domain commentary found for '{bible_book}' "
            f"on archive.org. Manual acquisition needed."
        ),
    }


# ---------------------------------------------------------------------------
# Public entry point — escalate_for_passage
# ---------------------------------------------------------------------------

def escalate_for_passage(
    *,
    scripture_reference: str,
    topic: str,
    missing_kinds: list[str],
    request_id: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Orchestrate the full escalation pipeline for a thin passage bundle.

    Called by research_librarian when fewer than 4 exposition resources are
    found.  Runs asynchronously-safe: all steps are idempotent, and the
    function always returns a result dict regardless of failures.

    Pipeline:
      1. Record escalation in the acquisition request table.
      2. Identify cataloged holdings with source URL but no source.txt.
      3. For each, attempt to download source.txt.
      4. Index any newly downloaded resources.
      5. Draft library cards for newly indexed resources.
      6. If still insufficient, search archive.org for new resources.
      7. Update request status to card_review or blocked.

    Returns a result dict describing what happened.
    """
    result: dict[str, Any] = {
        "scripture_reference": scripture_reference,
        "missing_kinds": missing_kinds,
        "downloaded": [],
        "indexed": [],
        "cards_drafted": [],
        "new_acquisitions": [],
        "final_status": "escalated",
    }

    # Step 1 — Record the escalation
    req_record = request_resource_acquisition(
        requested_by="research_librarian",
        scripture_reference=scripture_reference,
        topic=topic,
        worker_name="acquisition_librarian",
        reason=(
            f"Research librarian bundle thin for {scripture_reference}. "
            f"Missing: {', '.join(missing_kinds)}. "
            "Acquisition librarian escalation triggered."
        ),
        requested_resource_kinds=missing_kinds,
        status="escalated",
        notes="Acquisition librarian pipeline started.",
        request_id=request_id,
    )
    req_id = req_record.request_id
    result["request_id"] = req_id

    bible_book = _bible_book_from_reference(scripture_reference)

    # Step 2 — Find cataloged holdings missing source.txt
    update_resource_acquisition_request(
        request_id=req_id,
        status="downloading",
        notes=f"Scanning cataloged holdings for {bible_book} without source.txt.",
    )

    undownloaded = find_undownloaded_holdings(bible_book)

    # Step 3 — Download source texts
    if undownloaded:
        print(
            f"\n[Acquisition Librarian] {len(undownloaded)} resource(s) queued for download "
            f"({bible_book}) — pipeline paused while resources are fetched...",
            flush=True,
        )
    for holding_info in undownloaded:
        slug = holding_info["slug"]
        url = holding_info["download_url"]
        title = holding_info.get("title", slug)
        print(f"  ⬇  Downloading: {title} ...", end=" ", flush=True)
        ok, msg = download_source_text(slug, url)
        result["downloaded"].append({"slug": slug, "ok": ok, "message": msg})
        if ok:
            print("done.", flush=True)
            time.sleep(0.5)  # polite rate limiting
        else:
            print(f"failed ({msg})", flush=True)

    # Step 4 — Index newly downloaded resources
    update_resource_acquisition_request(
        request_id=req_id,
        status="indexing",
        notes=f"Indexing newly downloaded resources for {scripture_reference}.",
    )

    for dl in result["downloaded"]:
        if not dl["ok"]:
            continue
        slug = dl["slug"]
        holding_path = RESOURCES_ROOT / slug / "holding.json"
        if not holding_path.exists():
            continue
        try:
            holding = json.loads(holding_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        source_title = str(holding.get("title", slug))
        author = str(holding.get("author_or_editor", ""))
        print(f"  📚 Indexing: {source_title} ...", end=" ", flush=True)
        rows_added = index_resource_into_catalog(
            slug=slug,
            source_title=source_title,
            author=author,
            source_type="commentary",
            skip_header_lines=60,
            db_path=db_path,
        )
        print(f"{rows_added:,} passages indexed.", flush=True)
        result["indexed"].append({"slug": slug, "rows_added": rows_added})

    # Step 5 — Draft cards for newly indexed resources
    update_resource_acquisition_request(
        request_id=req_id,
        status="card_review",
        notes="Drafting library cards for newly indexed resources.",
    )

    for idx in result["indexed"]:
        if idx["rows_added"] > 0:
            card_result = _draft_card_for_slug(idx["slug"])
            result["cards_drafted"].append({"slug": idx["slug"], **card_result})

    # Step 6 — If nothing was downloaded, try archive.org for new resources
    if not any(dl["ok"] for dl in result["downloaded"]):
        new_acq = search_and_acquire_new_resource(bible_book)
        result["new_acquisitions"].append(new_acq)
        if new_acq.get("status") == "acquired":
            slug = new_acq["slug"]
            rows_added = index_resource_into_catalog(
                slug=slug,
                source_title=new_acq["title"],
                author=new_acq["author"],
                source_type="commentary",
                db_path=db_path,
            )
            result["indexed"].append({"slug": slug, "rows_added": rows_added})
            if rows_added > 0:
                card_result = _draft_card_for_slug(slug)
                result["cards_drafted"].append({"slug": slug, **card_result})

    # Step 7 — Set final status
    any_indexed = any(idx.get("rows_added", 0) > 0 for idx in result["indexed"])
    any_blocked = (
        not any_indexed
        and not any(dl["ok"] for dl in result["downloaded"])
        and all(
            a.get("status") == "blocked"
            for a in result["new_acquisitions"]
        )
    )

    final_status = "card_review" if any_indexed else ("blocked" if any_blocked else "escalated")
    result["final_status"] = final_status

    cards_summary = "; ".join(
        f"{c['slug']} ({c.get('outcome','?')})" for c in result["cards_drafted"]
    )
    indexed_summary = "; ".join(
        f"{i['slug']} (+{i['rows_added']} rows)" for i in result["indexed"]
    )
    update_resource_acquisition_request(
        request_id=req_id,
        status=final_status,
        notes=(
            f"Acquisition cycle complete for {scripture_reference}. "
            f"Indexed: {indexed_summary or 'none'}. "
            f"Cards drafted: {cards_summary or 'none'}. "
            "Awaiting Librarian Trainer card verification before resources go live."
            if any_indexed
            else (
                f"Acquisition blocked for {scripture_reference} — "
                "no accessible source texts found. Manual acquisition needed."
            )
        ),
        completed_at_utc=_utc_now() if final_status == "blocked" else None,
    )

    return result


# ---------------------------------------------------------------------------
# Batch processor — process_pending_escalations
# ---------------------------------------------------------------------------

def process_pending_escalations(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Process all pending 'requested' acquisition requests by running the
    escalation pipeline for each.

    Intended to be called periodically (e.g., from a cron or maintenance job)
    rather than inline during generation.  Returns list of result dicts.
    """
    results = []
    pending = list_resource_acquisition_requests(
        requested_by="research_librarian",
        status="requested",
    )
    for req in pending:
        result = escalate_for_passage(
            scripture_reference=req.scripture_reference,
            topic=req.topic,
            missing_kinds=list(req.requested_resource_kinds or ["exposition"]),
            request_id=req.request_id,
            db_path=db_path,
        )
        results.append(result)
        time.sleep(1.0)  # polite pause between passages
    return results
