"""
Cover design concepts for the Devotional Generator.

Three distinct aesthetic directions — each fully typographic (Option C) with an
optional Unsplash photo background for Design 3 (Option A) when an API key is set.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ColorPalette:
    background_top: tuple[int, int, int]      # RGB gradient start
    background_bottom: tuple[int, int, int]   # RGB gradient end (= top for solid)
    title: tuple[int, int, int]
    subtitle: tuple[int, int, int]
    author: tuple[int, int, int]
    rule: tuple[int, int, int]                # decorative rule / ornament
    spine_bg: tuple[int, int, int]
    spine_text: tuple[int, int, int]
    back_blurb: tuple[int, int, int]


@dataclass(frozen=True)
class CoverConcept:
    design_id: str
    name: str
    description: str
    palette: ColorPalette
    # Unsplash search query — used only if UNSPLASH_ACCESS_KEY is set
    unsplash_query: Optional[str] = None
    # Overlay opacity when using a photo (0.0 = no overlay, 1.0 = opaque)
    photo_overlay_opacity: float = 0.55


# ── Design 1: Shepherd's Rest — Deep Navy + Gold ─────────────────────────────

DESIGN_SHEPHERDS_REST = CoverConcept(
    design_id="shepherds_rest",
    name="Shepherd's Rest",
    description=(
        "Deep navy gradient with warm gold accents. Classic, authoritative, "
        "premium devotional feel. Reminiscent of fine gilt-edged study Bibles."
    ),
    palette=ColorPalette(
        background_top=(28, 41, 81),        # deep navy #1C2951
        background_bottom=(13, 18, 51),     # midnight navy #0D1233
        title=(245, 240, 232),              # cream ivory #F5F0E8
        subtitle=(201, 168, 76),            # warm gold #C9A84C
        author=(184, 151, 74),              # muted gold #B8974A
        rule=(201, 168, 76),               # warm gold
        spine_bg=(28, 41, 81),
        spine_text=(245, 240, 232),
        back_blurb=(220, 215, 205),         # light ivory for blurb
    ),
)

# ── Design 2: Still Waters — Deep Teal + White ───────────────────────────────

DESIGN_STILL_WATERS = CoverConcept(
    design_id="still_waters",
    name="Still Waters",
    description=(
        "Deep teal background, crisp white title with sage green subtitle. "
        "Clean, modern calm — suggests still water and quiet trust."
    ),
    palette=ColorPalette(
        background_top=(22, 60, 60),        # deep teal #163C3C
        background_bottom=(14, 45, 45),     # darker teal #0E2D2D
        title=(255, 255, 255),              # pure white
        subtitle=(143, 200, 200),           # soft aqua #8FC8C8
        author=(180, 210, 210),             # light aqua-gray
        rule=(143, 200, 200),              # soft aqua
        spine_bg=(22, 60, 60),
        spine_text=(255, 255, 255),
        back_blurb=(210, 230, 230),
    ),
)

# ── Design 3: Sanctuary — Burgundy + Cream ───────────────────────────────────
# When UNSPLASH_ACCESS_KEY is set, fetches a pastoral photo and overlays the text.

DESIGN_SANCTUARY = CoverConcept(
    design_id="sanctuary",
    name="Sanctuary",
    description=(
        "Warm burgundy with cream title and pale gold subtitle. Intimate and "
        "devotional. Optionally upgrades to a pastoral Unsplash photo background."
    ),
    palette=ColorPalette(
        background_top=(92, 27, 27),        # deep burgundy #5C1B1B
        background_bottom=(61, 16, 16),     # dark wine #3D1010
        title=(250, 245, 235),              # cream #FAF5EB
        subtitle=(212, 180, 131),           # pale gold #D4B483
        author=(195, 165, 120),             # muted gold
        rule=(212, 180, 131),              # pale gold
        spine_bg=(92, 27, 27),
        spine_text=(250, 245, 235),
        back_blurb=(235, 220, 200),
    ),
    unsplash_query="green pastures peaceful shepherd field golden light",
    photo_overlay_opacity=0.60,
)


ALL_CONCEPTS: list[CoverConcept] = [
    DESIGN_SHEPHERDS_REST,
    DESIGN_STILL_WATERS,
    DESIGN_SANCTUARY,
]
