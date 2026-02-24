from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class BlockType(str, Enum):
    # Content blocks
    HEADING = "heading"
    BODY_TEXT = "body_text"
    BLOCK_QUOTE = "block_quote"  # Indented block quote (FR-61, FR-62)
    FOOTNOTE = "footnote"  # Turabian attribution (FR-63)
    PROMPT_LIST = "prompt_list"  # Be Still prompts / Day 7 track prompts
    ACTION_LIST = "action_list"  # Walk It Out items
    DIVIDER = "divider"  # Typographic rule (sending prompt separator, Day 7)
    PAGE_BREAK = "page_break"  # Each day on new page (FR-91)
    # Front matter blocks
    TITLE = "title"
    SUBTITLE = "subtitle"
    IMPRINT = "imprint"  # Sacred Whispers Publishers
    TOC_ENTRY = "toc_entry"


class PageNumberStyle(str, Enum):
    ROMAN = "roman"
    ARABIC = "arabic"
    SUPPRESSED = "suppressed"


class DocumentBlock(BaseModel):
    block_type: BlockType
    content: str
    # Reserved — not consumed by the Phase 003 PDF engine.
    # The engine reads page_number_style from DocumentPage only.
    # Do not remove: may be used by Phase 004 UI.
    page_number_style: PageNumberStyle = PageNumberStyle.ARABIC
    # Reserved — not consumed by the Phase 003 PDF engine.
    # Populated by Phase 002 renderers (e.g., {"heading_level": 2}, {"footnote_id": "tw"}).
    # Do not remove: Phase 004 UI may read heading_level for display hierarchy.
    metadata: Dict[str, Any] = {}


class DocumentPage(BaseModel):
    blocks: List[DocumentBlock]
    starts_new_page: bool = False
    page_number_style: PageNumberStyle = PageNumberStyle.ARABIC


class DocumentRepresentation(BaseModel):
    title: str
    subtitle: Optional[str] = None
    front_matter: List[DocumentPage]
    content_pages: List[DocumentPage]
    has_toc: bool
    has_day7: bool
    # Reserved — not consumed by the Phase 003 PDF engine.
    # Currently always None from DocumentRenderer.render(); the engine computes its
    # own page count via two-pass layout. Do not use for layout decisions.
    total_estimated_pages: Optional[int] = None
