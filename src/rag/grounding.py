"""grounding.py — Phase 005 CP2 GroundingMapBuilder.

Assembles a valid GroundingMap from RetrievedExcerpt lists supplied per
paragraph slot (1–4). Raises ValueError early rather than passing invalid
data to the Pydantic validator.

No LLM calls. No network calls. No seed-file I/O.
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from src.interfaces.rag import RetrievedExcerpt
from src.models.artifacts import GroundingMap, GroundingMapEntry

_DEFAULT_PARAGRAPH_NAMES: Dict[int, str] = {
    1: "declaration",
    2: "context",
    3: "theological",
    4: "bridge",
}


class GroundingMapBuilder:
    """Build a valid GroundingMap from per-paragraph RetrievedExcerpt lists.

    Usage::

        builder = GroundingMapBuilder()
        gm = builder.build(
            exposition_id="some-uuid",
            paragraph_excerpts={
                1: [excerpt_a, excerpt_b],
                2: [excerpt_c],
                3: [excerpt_d, excerpt_e],
                4: [excerpt_f],
            },
        )

    Args (build):
        exposition_id: UUID string of the ExpositionSection being grounded.
        paragraph_excerpts: Mapping from paragraph_number (1–4) to a
            non-empty List[RetrievedExcerpt]. All four keys must be present.
        paragraph_names: Optional override for paragraph slot labels.
            Defaults: {1: "declaration", 2: "context",
                       3: "theological", 4: "bridge"}.

    Returns:
        GroundingMap with a freshly generated id, the supplied exposition_id,
        and exactly 4 GroundingMapEntry objects.

    Raises:
        ValueError if any of paragraphs 1–4 is absent from paragraph_excerpts
        or has an empty excerpt list.
    """

    def build(
        self,
        exposition_id: str,
        paragraph_excerpts: Dict[int, List[RetrievedExcerpt]],
        paragraph_names: Optional[Dict[int, str]] = None,
    ) -> GroundingMap:
        names = dict(_DEFAULT_PARAGRAPH_NAMES)
        if paragraph_names:
            names.update(paragraph_names)

        entries: List[GroundingMapEntry] = []
        for para_num in (1, 2, 3, 4):
            if para_num not in paragraph_excerpts:
                raise ValueError(
                    f"GroundingMapBuilder: paragraph {para_num} missing from paragraph_excerpts"
                )
            excerpts = paragraph_excerpts[para_num]
            if not excerpts:
                raise ValueError(
                    f"GroundingMapBuilder: paragraph {para_num} has an empty excerpt list"
                )

            # Deduplicate source titles while preserving insertion order.
            seen: set[str] = set()
            sources: List[str] = []
            for e in excerpts:
                if e.source_title not in seen:
                    sources.append(e.source_title)
                    seen.add(e.source_title)

            entries.append(
                GroundingMapEntry(
                    paragraph_number=para_num,
                    paragraph_name=names[para_num],
                    sources_retrieved=sources,
                    excerpts_used=[e.text[:80] for e in excerpts],
                    how_retrieval_informed_paragraph=(
                        f"Retrieved {len(excerpts)} excerpt(s) "
                        f"from {len(sources)} source(s)."
                    ),
                )
            )

        return GroundingMap(
            id=str(uuid.uuid4()),
            exposition_id=exposition_id,
            entries=entries,
        )
