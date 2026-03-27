from __future__ import annotations

from typing import Any


def is_url(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith("http://") or text.startswith("https://")


def normalize_quote_citation_fields(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    page_or_url = str(data.get("page_or_url", "") or "").strip()
    source_url = str(data.get("source_url", "") or "").strip()
    citation_locator = str(data.get("citation_locator", "") or "").strip()

    if not source_url and is_url(page_or_url):
        source_url = page_or_url
    if not citation_locator and page_or_url and not is_url(page_or_url):
        citation_locator = page_or_url

    data["page_or_url"] = page_or_url
    data["source_url"] = source_url
    data["citation_locator"] = citation_locator
    data["publisher"] = str(data.get("publisher", "") or "").strip()
    data["publication_city"] = str(data.get("publication_city", "") or "").strip()
    return data


def quote_attribution_line(author: str, source_title: str) -> str:
    parts = [str(author or "").strip(), str(source_title or "").strip()]
    filtered = [part for part in parts if part]
    return f"- {', '.join(filtered)}" if filtered else ""


def quote_citation_completeness(
    *,
    citation_locator: str = "",
    publisher: str = "",
    publication_city: str = "",
    source_url: str = "",
) -> int:
    score = 0
    if str(citation_locator or "").strip() and not is_url(str(citation_locator)):
        score += 2
    if str(publisher or "").strip():
        score += 1
    if str(publication_city or "").strip():
        score += 1
    if str(source_url or "").strip():
        score += 1
    return score


def has_strong_quote_citation(
    *,
    citation_locator: str = "",
    publisher: str = "",
    publication_city: str = "",
) -> bool:
    locator = str(citation_locator or "").strip()
    return bool(
        locator
        and not is_url(locator)
        and str(publisher or "").strip()
        and str(publication_city or "").strip()
    )


def supports_agent_quote_validation(
    *,
    author: str = "",
    source_title: str = "",
    quote_text: str = "",
    source_url: str = "",
) -> bool:
    return all(
        str(value or "").strip()
        for value in [author, source_title, quote_text, source_url]
    )


def quote_footnote(
    *,
    author: str,
    source_title: str,
    publication_year: int | None,
    citation_locator: str = "",
    publisher: str = "",
    publication_city: str = "",
) -> str:
    year = publication_year or "n.d."
    place_publisher = ""
    if publication_city and publisher:
        place_publisher = f"{publication_city}: {publisher}"
    elif publisher:
        place_publisher = publisher
    elif publication_city:
        place_publisher = publication_city

    parts: list[str] = []
    lead = ", ".join(part for part in [str(author or "").strip(), str(source_title or "").strip()] if part)
    if lead:
        parts.append(lead)
    if place_publisher:
        parts.append(f"({place_publisher}, {year})")
    else:
        parts.append(f"({year})")
    locator = str(citation_locator or "").strip()
    if locator and not is_url(locator):
        parts.append(locator)
    return ", ".join(part for part in parts if part).strip() + "."


def merge_quote_citation_fields(*payloads: dict[str, Any]) -> dict[str, Any]:
    """Merge citation fields from multiple records for the same quote/work.

    Prefer the first non-empty value for bibliographic fields while retaining a
    union of discovered source URLs. This lets the selector search all available
    sources for a quote before deciding that no complete Turabian citation
    exists.
    """
    merged: dict[str, Any] = {}
    source_urls: list[str] = []
    page_or_url_values: list[str] = []
    for raw in payloads:
        data = normalize_quote_citation_fields(dict(raw))
        for key in (
            "quote_text",
            "original_quote_text",
            "language_modernized",
            "modernization_label",
            "author",
            "source_title",
            "publication_year",
            "citation_locator",
            "publisher",
            "publication_city",
            "public_domain",
        ):
            if key not in merged or merged.get(key) in ("", None, False):
                value = data.get(key)
                if value not in ("", None, False):
                    merged[key] = value
        page_or_url = str(data.get("page_or_url", "") or "").strip()
        if page_or_url:
            page_or_url_values.append(page_or_url)
        source_url = str(data.get("source_url", "") or "").strip()
        if source_url and source_url not in source_urls:
            source_urls.append(source_url)

    merged.setdefault("page_or_url", next((value for value in page_or_url_values if value), ""))
    merged["source_url"] = source_urls[0] if source_urls else ""
    merged["source_trace"] = source_urls or [
        value for value in page_or_url_values if is_url(value)
    ]
    merged["citation_completeness"] = quote_citation_completeness(
        citation_locator=str(merged.get("citation_locator", "") or ""),
        publisher=str(merged.get("publisher", "") or ""),
        publication_city=str(merged.get("publication_city", "") or ""),
        source_url=str(merged.get("source_url", "") or ""),
    )
    return merged
