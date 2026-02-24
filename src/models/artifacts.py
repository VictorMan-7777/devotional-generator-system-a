from __future__ import annotations

from typing import List

from pydantic import BaseModel, field_validator


class GroundingMapEntry(BaseModel):
    paragraph_number: int  # 1–4 (declaration, context, theological, bridge)
    paragraph_name: str
    sources_retrieved: List[str]  # Document names retrieved
    excerpts_used: List[str]  # Specific passages drawn upon
    how_retrieval_informed_paragraph: str  # One-sentence statement


class GroundingMap(BaseModel):
    id: str  # UUID
    exposition_id: str
    entries: List[GroundingMapEntry]  # Must have exactly 4 entries

    @field_validator("entries")
    @classmethod
    def must_have_four_entries(cls, v: List[GroundingMapEntry]) -> List[GroundingMapEntry]:
        if len(v) != 4:
            raise ValueError("GroundingMap must have exactly 4 entries")
        if not all(e.sources_retrieved and e.excerpts_used for e in v):
            raise ValueError("All GroundingMap entries must be non-empty")
        return v


class PrayerTraceMapEntry(BaseModel):
    element_text: str  # The petition, address, or thematic element
    source_type: str  # "scripture" | "exposition" | "be_still"
    source_reference: str  # Specific verse/sentence/prompt being referenced


class PrayerTraceMap(BaseModel):
    id: str  # UUID
    prayer_id: str
    entries: List[PrayerTraceMapEntry]  # One per prayer element; no untraceable elements

    @field_validator("entries")
    @classmethod
    def no_untraceable_elements(cls, v: List[PrayerTraceMapEntry]) -> List[PrayerTraceMapEntry]:
        valid_types = {"scripture", "exposition", "be_still"}
        invalid = [e for e in v if e.source_type not in valid_types]
        if invalid:
            raise ValueError(
                "All prayer elements must be traceable to scripture, exposition, or be_still"
            )
        return v
