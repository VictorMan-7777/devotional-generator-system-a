from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


DEFAULT_PRIMARY_SOURCE = "bolls_life"
DEFAULT_VALIDATOR_SOURCE = "api_bible"
DEFAULT_FALLBACK_SOURCES = ("operator_import",)


@dataclass(frozen=True)
class ScriptureSourcePolicy:
    primary_source: str = DEFAULT_PRIMARY_SOURCE
    validator_source: str = DEFAULT_VALIDATOR_SOURCE
    fallback_sources: tuple[str, ...] = DEFAULT_FALLBACK_SOURCES
    cache_ttl_days: int = 30

    @classmethod
    def from_env(cls) -> "ScriptureSourcePolicy":
        primary = os.getenv("DEVG_SCRIPTURE_PRIMARY_SOURCE", DEFAULT_PRIMARY_SOURCE).strip().lower()
        validator = os.getenv("DEVG_SCRIPTURE_VALIDATOR_SOURCE", DEFAULT_VALIDATOR_SOURCE).strip().lower()
        fallback_raw = os.getenv(
            "DEVG_SCRIPTURE_FALLBACK_SOURCES",
            ",".join(DEFAULT_FALLBACK_SOURCES),
        )
        fallback = tuple(
            item.strip().lower()
            for item in fallback_raw.split(",")
            if item.strip()
        )
        ttl_raw = os.getenv("DEVG_SCRIPTURE_CACHE_TTL_DAYS", "30").strip()
        try:
            ttl = max(1, int(ttl_raw))
        except ValueError:
            ttl = 30
        return cls(
            primary_source=primary or DEFAULT_PRIMARY_SOURCE,
            validator_source=validator or DEFAULT_VALIDATOR_SOURCE,
            fallback_sources=fallback or DEFAULT_FALLBACK_SOURCES,
            cache_ttl_days=ttl,
        )

    def retrieval_order(self) -> tuple[str, ...]:
        ordered: list[str] = [self.primary_source]
        if self.validator_source and self.validator_source not in ordered:
            ordered.append(self.validator_source)
        for source in self.fallback_sources:
            if source and source not in ordered:
                ordered.append(source)
        return tuple(ordered)

    def choose_validator_source(
        self,
        *,
        original_source: str,
        available_sources: Iterable[str],
    ) -> str | None:
        normalized_original = str(original_source or "").strip().lower()
        available = [str(source or "").strip().lower() for source in available_sources if str(source or "").strip()]
        preferred = str(self.validator_source or "").strip().lower()
        if preferred and preferred != normalized_original and preferred in available:
            return preferred
        for source in available:
            if source != normalized_original:
                return source
        return None


def scripture_source_metadata(
    *,
    source: str,
    translation: str,
    retrieved_at: datetime | None = None,
    cache_ttl_days: int = 30,
) -> dict[str, str]:
    now = retrieved_at or datetime.now(timezone.utc)
    source_norm = str(source or "").strip().lower()
    translation_norm = str(translation or "").strip() or "Unknown"
    metadata = {
        "retrieval_reference": "",
        "retrieved_at_utc": now.isoformat(),
        "copyright_notice": "",
        "source_access_policy": "reference_canonical_text_refreshable",
        "text_cache_status": "cached",
        "cache_expires_at_utc": "",
    }
    if source_norm == "api_bible":
        if translation_norm in {"NASB", "NASB1995", "NASB 1995"}:
            metadata["copyright_notice"] = (
                "New American Standard Bible®, Copyright © 1995, "
                "The Lockman Foundation. All rights reserved. lockman.org"
            )
        else:
            metadata["copyright_notice"] = (
                f"{translation_norm} copyright notice required in rendered output; "
                "licensed text cache must be refreshed at least every 30 days."
            )
        metadata["source_access_policy"] = "licensed_text_cache_refresh_30d"
        metadata["cache_expires_at_utc"] = (
            now + timedelta(days=max(1, int(cache_ttl_days)))
        ).isoformat()
    elif source_norm == "bolls_life":
        metadata["source_access_policy"] = "reference_canonical_text_refreshable"
    elif source_norm == "operator_import":
        metadata["source_access_policy"] = "operator_supplied_validation_copy"
    return metadata


def scripture_exact_text_compatible(
    *,
    original_source: str,
    validator_source: str,
    translation: str,
) -> bool:
    original = str(original_source or "").strip().lower()
    validator = str(validator_source or "").strip().lower()
    translation_norm = str(translation or "").strip().upper()

    if not original or not validator:
        return False
    if original == validator:
        return True
    api_bible_id = os.getenv("API_BIBLE_BIBLE_ID", "").strip().lower()
    if (
        "NASB" in translation_norm
        and {original, validator} == {"api_bible", "bolls_life"}
        and api_bible_id == "b8ee27bcd1cae43a-01"
    ):
        return True
    if "NASB" in translation_norm and "operator_import" in {original, validator}:
        return False
    return False
