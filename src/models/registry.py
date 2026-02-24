from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QuoteRecord(BaseModel):
    id: str  # UUID
    volume_id: str
    series_id: str
    quote_text: str
    author: str
    source_title: str
    publication_year: Optional[int] = None
    added_at: datetime


class ScriptureRecord(BaseModel):
    id: str  # UUID
    volume_id: str
    reference: str  # e.g. "Romans 8:15"
    translation: str
    added_at: datetime


class VolumeRecord(BaseModel):
    id: str  # UUID
    series_id: str
    volume_number: int
    title: Optional[str] = None
    created_at: datetime
