from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SectionApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"


class OutputMode(str, Enum):
    PERSONAL = "personal"
    PUBLISH_READY = "publish-ready"


class DevotionalInput(BaseModel):
    topic: str
    num_days: int = Field(default=6, ge=1, le=7)
    scripture_version: str = "NASB"
    output_mode: OutputMode = OutputMode.PUBLISH_READY
    title: Optional[str] = None
    day_focus: Optional[List[str]] = None


class TimelessWisdomSection(BaseModel):
    quote_text: str
    author: str
    source_title: str
    publication_year: Optional[int] = None
    page_or_url: str
    public_domain: bool
    verification_status: str  # "catalog_verified" | "human_approved"
    approval_status: SectionApprovalStatus = SectionApprovalStatus.PENDING


class ScriptureSection(BaseModel):
    reference: str  # e.g. "Romans 8:15"
    text: str
    translation: str
    retrieval_source: str  # "bolls_life" | "api_bible" | "operator_import"
    verification_status: str
    approval_status: SectionApprovalStatus = SectionApprovalStatus.PENDING


class ExpositionSection(BaseModel):
    text: str  # Full 500–700 word text
    word_count: int
    grounding_map_id: str  # FK to GroundingMap
    approval_status: SectionApprovalStatus = SectionApprovalStatus.PENDING


class BeStillSection(BaseModel):
    prompts: List[str]  # 3–5 prompts
    approval_status: SectionApprovalStatus = SectionApprovalStatus.PENDING


class ActionStepsSection(BaseModel):
    items: List[str]  # 1–3 items
    connector_phrase: str
    approval_status: SectionApprovalStatus = SectionApprovalStatus.PENDING


class PrayerSection(BaseModel):
    text: str  # 120–200 words
    word_count: int
    prayer_trace_map_id: str  # FK to PrayerTraceMap
    approval_status: SectionApprovalStatus = SectionApprovalStatus.PENDING


class SendingPromptSection(BaseModel):  # Day 6, only when Day 7 enabled
    text: str  # 40–80 words
    word_count: int
    approval_status: SectionApprovalStatus = SectionApprovalStatus.PENDING


class Day7Section(BaseModel):  # Only when num_days == 7
    before_service: str  # 50–80 words
    after_service_track_a: List[str]  # 2–3 prompts + closing question
    after_service_track_b: List[str]  # 2–3 prompts + closing question
    after_service_word_count: int  # Must be 120–180
    approval_status: SectionApprovalStatus = SectionApprovalStatus.PENDING


class DailyDevotional(BaseModel):
    day_number: int = Field(ge=1, le=7)
    day_focus: Optional[str] = None
    timeless_wisdom: TimelessWisdomSection
    scripture: ScriptureSection
    exposition: ExpositionSection
    be_still: BeStillSection
    action_steps: ActionStepsSection
    prayer: PrayerSection
    sending_prompt: Optional[SendingPromptSection] = None  # Day 6 only
    day7: Optional[Day7Section] = None  # Day 7 only
    created_at: datetime
    last_modified: datetime


class DevotionalBook(BaseModel):
    id: str  # UUID
    input: DevotionalInput
    days: List[DailyDevotional]
    series_id: Optional[str] = None
    volume_number: Optional[int] = None
