from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.rag.cuttings_inventory import CuttingSource, inventory_cutting_sources


LIBRARY_ROOT = Path(__file__).resolve().parents[2] / "data" / "library"
RESOURCES_ROOT = LIBRARY_ROOT / "resources"
ACQUIRED_ROOT = LIBRARY_ROOT / "acquisitions" / "acquired"
PENDING_ROOT = LIBRARY_ROOT / "acquisitions" / "pending"

KNOWN_SOURCE_OVERRIDES: dict[str, dict[str, Any]] = {
    "A Discourse on Prayer": {
        "provider": "project_gutenberg",
        "title": "Works of John Bunyan — Complete",
        "author": "John Bunyan",
        "source_url": "https://www.gutenberg.org/ebooks/6049.html.gen",
        "metadata_url": "https://www.gutenberg.org/ebooks/6049",
        "download_url": "https://www.gutenberg.org/files/6049/6049-0.txt",
        "match_type": "family",
        "format_label": "Plain Text UTF-8",
        "citation_components": {
            "publication_year": None,
            "publisher": "",
            "publication_city": "",
            "quote_citation_ready": False,
        },
    },
    "International Standard Bible Encyclopedia (1915)": {
        "provider": "archive_org",
        "title": "The International Standard Bible Encyclopedia",
        "author": "James Orr",
        "source_url": "https://archive.org/details/bwb_Y0-BWA-628",
        "metadata_url": "https://archive.org/metadata/bwb_Y0-BWA-628",
        "download_url": "https://archive.org/download/bwb_Y0-BWA-628/bwb_Y0-BWA-628_djvu.txt",
        "match_type": "family",
        "format_label": "DjVuTXT",
    },
    "Jamieson-Fausset-Brown Bible Commentary": {
        "provider": "ccel",
        "title": "Commentary Critical and Explanatory on the Whole Bible",
        "author": "Robert Jamieson, A. R. Fausset, and David Brown",
        "source_url": "https://www.ccel.org/ccel/jamieson/jfb.txt",
        "metadata_url": "https://www.ccel.org/ccel/jamieson/jfb.i.html",
        "download_url": "https://www.ccel.org/ccel/j/jamieson/jfb/cache/jfb.pdf",
        "match_type": "family",
        "format_label": "Text/PDF",
        "citation_components": {
            "publication_year": 1871,
            "publisher": "",
            "publication_city": "",
            "quote_citation_ready": False,
        },
    },
    "John Gill's Exposition of the Bible": {
        "provider": "web_text",
        "title": "John Gill's Exposition of the Bible",
        "author": "John Gill",
        "source_url": "https://johngill.thekingsbible.com/",
        "metadata_url": "https://johngill.thekingsbible.com/",
        "download_url": "https://johngill.thekingsbible.com/",
        "match_type": "exact",
        "format_label": "HTML",
        "citation_components": {
            "publication_year": None,
            "publisher": "",
            "publication_city": "",
            "quote_citation_ready": False,
        },
    },
    "Luther's Works (Prayer Selections)": {
        "provider": "ccel",
        "title": "Martin Luther: Table Talk",
        "author": "Martin Luther",
        "source_url": "https://ccel.org/ccel/luther/tabletalk.html",
        "metadata_url": "https://ccel.org/ccel/luther/tabletalk/tabletalk.toc.html",
        "download_url": "https://ccel.org/ccel/l/luther/tabletalk/cache/tabletalk.pdf",
        "match_type": "family",
        "format_label": "PDF",
        "citation_components": {
            "publication_year": None,
            "publisher": "",
            "publication_city": "",
            "quote_citation_ready": False,
        },
    },
    "Sermons and Letters": {
        "provider": "ccel",
        "title": "John Calvin: Three Volumes of Sermons",
        "author": "John Calvin",
        "source_url": "https://www.ccel.org/ccel/calvin/sermons/",
        "metadata_url": "https://www.ccel.org/ccel/calvin/sermons/sermons.i.html",
        "download_url": "",
        "match_type": "family",
        "format_label": "HTML",
        "citation_components": {
            "publication_year": None,
            "publisher": "",
            "publication_city": "",
            "quote_citation_ready": False,
        },
    },
    "Sermons and Tracts": {
        "provider": "ccel",
        "title": "John Wesley: Sermons on Several Occasions",
        "author": "John Wesley",
        "source_url": "https://www.ccel.org/ccel/wesley/sermons.iv.html",
        "metadata_url": "https://www.ccel.org/ccel/wesley/sermons.iv.html",
        "download_url": "https://www.ccel.org/ccel/w/wesley/sermons/cache/sermons.pdf",
        "match_type": "family",
        "format_label": "PDF",
        "citation_components": {
            "publication_year": None,
            "publisher": "",
            "publication_city": "",
            "quote_citation_ready": False,
        },
    },
}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _surname(author: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z]+", author) if part]
    return parts[-1].lower() if parts else ""


def _request_json(url: str, *, timeout: int = 30) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 DevG Librarian"})
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


def _request_text(url: str, *, timeout: int = 30) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 DevG Librarian"})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


@dataclass(frozen=True)
class AcquisitionCandidate:
    provider: str
    identifier: str
    title: str
    author: str
    score: float
    source_url: str
    metadata_url: str
    download_url: str
    match_type: str
    format_label: str


def _title_score(requested_title: str, candidate_title: str) -> float:
    requested = _norm(requested_title)
    candidate = _norm(candidate_title)
    if not requested or not candidate:
        return 0.0
    ratio = SequenceMatcher(None, requested, candidate).ratio()
    if requested == candidate:
        return 100.0
    if requested in candidate or candidate in requested:
        return 90.0
    requested_words = set(requested.split())
    candidate_words = set(candidate.split())
    overlap = len(requested_words & candidate_words) / max(1, len(requested_words))
    return max(ratio * 100.0, overlap * 100.0)


def _author_score(requested_author: str, candidate_author: str) -> float:
    requested = _norm(requested_author)
    candidate = _norm(candidate_author)
    if not requested:
        return 0.0
    if requested and requested in candidate:
        return 25.0
    surname = _surname(requested_author)
    if surname and surname in candidate:
        return 15.0
    return 0.0


def _author_penalty(requested_author: str, candidate_author: str) -> float:
    requested = _norm(requested_author)
    candidate = _norm(candidate_author)
    if not requested or not candidate:
        return 0.0
    if _author_score(requested_author, candidate_author) > 0:
        return 0.0
    return -45.0


def _format_bonus(formats: list[str]) -> tuple[float, str, str]:
    format_set = {str(item or "").strip() for item in formats}
    checks = [
        ("DjVuTXT", 20.0, "djvu_txt"),
        ("OCR Search Text", 18.0, "ocr_search_text"),
        ("EPUB", 16.0, "epub"),
        ("Text PDF", 10.0, "pdf"),
    ]
    for label, bonus, token in checks:
        if label in format_set:
            return bonus, token, label
    return 0.0, "", ""


def search_gutenberg_candidates(bible_book: str) -> list[AcquisitionCandidate]:
    """Search Project Gutenberg (via Gutendex API) for public-domain commentaries
    covering bible_book.  Returns AcquisitionCandidate list with plain-text download URLs.
    """
    search_terms = [
        f"{bible_book} commentary",
        f"{bible_book} exposition",
        f"{bible_book} notes",
    ]
    candidates: list[AcquisitionCandidate] = []
    seen: set[str] = set()
    for term in search_terms:
        try:
            url = "https://gutendex.com/books/?search=" + quote(term) + "&topic=religion"
            data = _request_json(url)
        except Exception:
            continue
        for book in data.get("results", []):
            gutenberg_id = str(book.get("id") or "").strip()
            if not gutenberg_id or gutenberg_id in seen:
                continue
            seen.add(gutenberg_id)
            title = str(book.get("title") or "").strip()
            authors = book.get("authors") or []
            author = "; ".join(
                str(a.get("name") or "").strip()
                for a in authors
                if str(a.get("name") or "").strip()
            )
            formats = book.get("formats") or {}
            txt_url = (
                formats.get("text/plain; charset=utf-8")
                or formats.get("text/plain; charset=us-ascii")
                or formats.get("text/plain")
                or ""
            )
            if not txt_url:
                continue
            candidates.append(
                AcquisitionCandidate(
                    provider="project_gutenberg",
                    identifier=f"pg{gutenberg_id}",
                    title=title,
                    author=author,
                    score=50.0,
                    source_url=f"https://www.gutenberg.org/ebooks/{gutenberg_id}",
                    metadata_url=f"https://gutendex.com/books/{gutenberg_id}/",
                    download_url=txt_url,
                    match_type="weak",
                    format_label="text/plain",
                )
            )
        time.sleep(0.1)
    return candidates


def _build_archive_queries(title: str, author: str) -> list[str]:
    queries = []
    title_clean = str(title or "").strip()
    author_clean = str(author or "").strip()
    if title_clean and author_clean:
        queries.append(f'title:("{title_clean}") AND creator:("{author_clean}")')
        surname = _surname(author_clean)
        if surname:
            queries.append(f'title:("{title_clean}") AND creator:("{surname}")')
    if title_clean:
        queries.append(f'title:("{title_clean}")')
    title_words = [word for word in _norm(title_clean).split() if len(word) >= 4]
    if title_words:
        queries.append(" AND ".join(f"title:({quote_word})" for quote_word in title_words[:4]))
    return list(dict.fromkeys(query for query in queries if query))


def _archive_download_choice(identifier: str, metadata: dict[str, Any]) -> tuple[str, str]:
    files = metadata.get("files") or []
    for preferred_format, suffix in (
        ("DjVuTXT", "_djvu.txt"),
        ("OCR Search Text", "_hocr_searchtext.txt.gz"),
        ("EPUB", ".epub"),
        ("Text PDF", ".pdf"),
    ):
        for row in files:
            if str(row.get("format") or "").strip() == preferred_format:
                name = str(row.get("name") or "").strip()
                if name:
                    return f"https://archive.org/download/{identifier}/{name}", preferred_format
        if suffix:
            return f"https://archive.org/download/{identifier}/{identifier}{suffix}", preferred_format
    return "", ""


def search_archive_candidates(title: str, author: str) -> list[AcquisitionCandidate]:
    candidates: dict[str, AcquisitionCandidate] = {}
    for query in _build_archive_queries(title, author):
        url = (
            "https://archive.org/advancedsearch.php?q="
            + quote(query)
            + "&fl[]=identifier,title,creator,mediatype,format&rows=8&page=1&output=json"
        )
        data = _request_json(url)
        for row in data.get("response", {}).get("docs", []):
            if str(row.get("mediatype") or "").strip() != "texts":
                continue
            identifier = str(row.get("identifier") or "").strip()
            if not identifier:
                continue
            candidate_title = str(row.get("title") or "").strip()
            candidate_author_raw = row.get("creator")
            if isinstance(candidate_author_raw, list):
                candidate_author = "; ".join(str(item) for item in candidate_author_raw if str(item).strip())
            else:
                candidate_author = str(candidate_author_raw or "").strip()
            title_score = _title_score(title, candidate_title)
            author_score = _author_score(author, candidate_author)
            bonus, _, format_label = _format_bonus(list(row.get("format") or []))
            score = title_score + author_score + _author_penalty(author, candidate_author) + bonus
            if title_score >= 90 and author_score >= 15:
                match_type = "exact"
            elif title_score >= 65 and author_score >= 15:
                match_type = "family"
            else:
                match_type = "weak"
            candidate = AcquisitionCandidate(
                provider="archive_org",
                identifier=identifier,
                title=candidate_title,
                author=candidate_author,
                score=score,
                source_url=f"https://archive.org/details/{identifier}",
                metadata_url=f"https://archive.org/metadata/{identifier}",
                download_url="",
                match_type=match_type,
                format_label=format_label,
            )
            existing = candidates.get(identifier)
            if existing is None or candidate.score > existing.score:
                candidates[identifier] = candidate
        time.sleep(0.15)
    ranked = sorted(candidates.values(), key=lambda item: (-item.score, item.title.lower()))
    results: list[AcquisitionCandidate] = []
    for item in ranked[:5]:
        try:
            metadata = _request_json(item.metadata_url)
            download_url, format_label = _archive_download_choice(item.identifier, metadata)
        except Exception:
            download_url, format_label = "", item.format_label
        results.append(
            AcquisitionCandidate(
                provider=item.provider,
                identifier=item.identifier,
                title=item.title,
                author=item.author,
                score=item.score,
                source_url=item.source_url,
                metadata_url=item.metadata_url,
                download_url=download_url,
                match_type=item.match_type,
                format_label=format_label,
            )
        )
    return results


def _candidate_json(candidate: AcquisitionCandidate) -> dict[str, Any]:
    return asdict(candidate)


def _write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _download_best_asset(candidate: AcquisitionCandidate, resource_dir: Path) -> dict[str, str]:
    if not candidate.download_url:
        return {}
    suffix = Path(candidate.download_url).suffix or ".txt"
    target = resource_dir / f"source{suffix}"
    try:
        req = Request(candidate.download_url, headers={"User-Agent": "Mozilla/5.0 DevG Librarian"})
        with urlopen(req, timeout=60) as response:
            data = response.read()
        target.write_bytes(data)
        return {
            "local_asset_path": str(target),
            "download_url": candidate.download_url,
            "download_format": candidate.format_label,
        }
    except Exception:
        return {}


def _download_override_asset(download_url: str, resource_dir: Path) -> dict[str, str]:
    if not download_url:
        return {}
    suffix = Path(download_url).suffix or ".html"
    target = resource_dir / f"source{suffix}"
    try:
        req = Request(download_url, headers={"User-Agent": "Mozilla/5.0 DevG Librarian"})
        with urlopen(req, timeout=60) as response:
            data = response.read()
        target.write_bytes(data)
        return {
            "local_asset_path": str(target),
            "download_url": download_url,
        }
    except Exception:
        return {}


def _split_publisher_field(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""
    if " : " in text:
        city, publisher = text.split(" : ", 1)
        return city.strip(" ,;"), publisher.strip(" ,;")
    return "", text.strip(" ,;")


def _extract_citation_components(metadata: dict[str, Any]) -> dict[str, Any]:
    info = metadata.get("metadata") or {}
    publisher_raw = str(info.get("publisher") or "").strip()
    publication_city, publisher = _split_publisher_field(publisher_raw)
    date = str(info.get("date") or "").strip()
    year_match = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", date)
    publication_year = int(year_match.group(1)) if year_match else None
    quote_ready = bool(publication_year and publisher and publication_city)
    return {
        "publication_year": publication_year,
        "publisher": publisher,
        "publication_city": publication_city,
        "quote_citation_ready": quote_ready,
    }


def acquire_cutting_parent_resource(source: CuttingSource) -> dict[str, Any]:
    slug = _slug(source.source_title)
    resource_dir = RESOURCES_ROOT / slug
    resource_dir.mkdir(parents=True, exist_ok=True)

    use_override = False
    override = KNOWN_SOURCE_OVERRIDES.get(source.source_title)
    archive_candidates: list[AcquisitionCandidate] = []
    best = None
    if override:
        acquisition_status = "acquired"
        use_override = True
    else:
        archive_candidates = search_archive_candidates(source.source_title, source.author)
        best = archive_candidates[0] if archive_candidates else None
        if best is not None and best.match_type in {"exact", "family"} and best.score >= 80:
            acquisition_status = "acquired"
        else:
            acquisition_status = "blocked"

    holding: dict[str, Any] = {
        "title": source.source_title,
        "author_or_editor": source.author,
        "source_kind_from_cuttings": source.source_kind,
        "cutting_count": source.cutting_count,
        "acquired_at_utc": _utc_stamp(),
        "status": acquisition_status,
        "provider_candidates": [_candidate_json(item) for item in archive_candidates],
        "selected_provider": best.provider if best else "",
        "selected_identifier": best.identifier if best else "",
        "selected_title": best.title if best else "",
        "selected_author": best.author if best else "",
        "selected_source_url": best.source_url if best else "",
        "selected_metadata_url": best.metadata_url if best else "",
        "selected_match_type": best.match_type if best else "",
    }
    if use_override and override is not None:
        holding.update(
            {
                "selected_provider": override["provider"],
                "selected_identifier": "",
                "selected_title": override["title"],
                "selected_author": override["author"],
                "selected_source_url": override["source_url"],
                "selected_metadata_url": override["metadata_url"],
                "selected_match_type": override["match_type"],
                "citation_components": dict(override.get("citation_components") or {}),
            }
        )
        holding.update(_download_override_asset(str(override.get("download_url") or ""), resource_dir))
    elif best is not None:
        try:
            metadata = _request_json(best.metadata_url)
            _write_json(resource_dir / "metadata.json", metadata)
            holding["local_metadata_path"] = str(resource_dir / "metadata.json")
            holding["citation_components"] = _extract_citation_components(metadata)
        except Exception:
            holding["local_metadata_path"] = ""
            holding["citation_components"] = {
                "publication_year": None,
                "publisher": "",
                "publication_city": "",
                "quote_citation_ready": False,
            }
        holding.update(_download_best_asset(best, resource_dir))
    else:
        holding["citation_components"] = {
            "publication_year": None,
            "publisher": "",
            "publication_city": "",
            "quote_citation_ready": False,
        }

    _write_json(resource_dir / "holding.json", holding)

    acquisition_record = {
        "title": source.source_title,
        "author_or_editor": source.author,
        "source_kind_from_cuttings": source.source_kind,
        "why_needed": "Current system has cuttings from this resource but not the parent work in the library.",
        "status": acquisition_status,
        "assigned_librarian": "acquisition_librarian",
        "requested_at_utc": "",
        "acquired_at_utc": holding["acquired_at_utc"],
        "cutting_count": source.cutting_count,
        "seen_in": [source.source_kind],
        "selected_source_url": holding.get("selected_source_url", ""),
        "selected_metadata_url": holding.get("selected_metadata_url", ""),
        "local_holding_path": str(resource_dir / "holding.json"),
        "local_asset_path": holding.get("local_asset_path", ""),
        "next_actions": {
            "acquisition_librarian": (
                "Inspect the acquired resource, then draft a real card only after confirming it is the right parent resource."
                if acquisition_status == "acquired"
                else "Search another approved source and try again."
            ),
            "research_librarian": (
                "After acquisition is confirmed, collaborate on the card and begin reading notes."
                if acquisition_status == "acquired"
                else "Wait for a shelf-ready parent resource."
            ),
        },
        "follow_on_work": [
            "create_draft_live_card",
            "evaluate_card",
            "revise_if_needed",
            "create_research_reading_notes",
            "evaluate_notes",
        ],
    }
    _write_json(ACQUIRED_ROOT / f"{datetime.now(timezone.utc):%Y-%m-%d}__{slug}.json", acquisition_record)

    pending = PENDING_ROOT / f"{datetime.now(timezone.utc):%Y-%m-%d}__{slug}.json"
    if pending.exists():
        pending.unlink()

    return {
        "title": source.source_title,
        "status": acquisition_status,
        "selected_source_url": holding.get("selected_source_url", ""),
        "selected_match_type": holding.get("selected_match_type", ""),
        "citation_components": holding.get("citation_components", {}),
        "local_holding_path": str(resource_dir / "holding.json"),
        "local_asset_path": holding.get("local_asset_path", ""),
        "candidate_count": len(archive_candidates),
    }


def acquire_all_cutting_parent_resources(limit: int | None = None) -> dict[str, Any]:
    sources = inventory_cutting_sources(retired_titles=set())
    if limit is not None:
        sources = sources[: max(0, limit)]
    results = []
    for source in sources:
        results.append(acquire_cutting_parent_resource(source))
        time.sleep(0.2)
    acquired = sum(1 for row in results if row["status"] == "acquired")
    blocked = sum(1 for row in results if row["status"] != "acquired")
    summary = {
        "started_at_utc": _utc_stamp(),
        "requested_count": len(results),
        "acquired_count": acquired,
        "blocked_count": blocked,
        "results": results,
    }
    _write_json(LIBRARY_ROOT / "acquisition-summary.json", summary)
    return summary
