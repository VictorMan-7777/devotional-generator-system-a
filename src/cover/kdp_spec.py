"""KDP cover specifications for 6×9 inch trim size."""
from __future__ import annotations

DPI = 300
TRIM_W_IN = 6.0
TRIM_H_IN = 9.0
BLEED_IN = 0.125
SAFE_MARGIN_IN = 0.25  # KDP requires text/art stay 0.25" from trim edge

# Combined: text must be ≥ this distance from the outer bleed edge
SAFE_FROM_BLEED_IN = BLEED_IN + SAFE_MARGIN_IN  # 0.375"

# White paper thickness per page (KDP standard)
PAPER_THICKNESS_IN = 0.002252
SPINE_BASE_IN = 0.06  # minimum spine base width

# Barcode zone on back cover: white box, min 2" × 1.2", 0.25" from trim edges
BARCODE_W_IN = 2.0
BARCODE_H_IN = 1.2


def spine_width_in(page_count: int) -> float:
    return page_count * PAPER_THICKNESS_IN + SPINE_BASE_IN


def pt_to_px(points: float) -> int:
    """Convert typographic points to pixels at DPI."""
    return round(points * DPI / 72)


def in_to_px(inches: float) -> int:
    return round(inches * DPI)


def cover_dims_px(page_count: int) -> tuple[int, int]:
    """Full wrap dimensions (px): back + spine + front + bleed on all 4 sides."""
    spine_in = spine_width_in(page_count)
    total_w_in = BLEED_IN + TRIM_W_IN + spine_in + TRIM_W_IN + BLEED_IN
    total_h_in = BLEED_IN + TRIM_H_IN + BLEED_IN
    return (round(total_w_in * DPI), round(total_h_in * DPI))


def cover_zones_px(page_count: int) -> dict[str, int]:
    """
    Return pixel x/y offsets for major regions within the full-wrap image.

    Origin (0,0) is top-left of bleed area.
    """
    spine_in = spine_width_in(page_count)
    bleed_px = in_to_px(BLEED_IN)
    trim_px = in_to_px(TRIM_W_IN)
    spine_px = round(spine_in * DPI)
    trim_h_px = in_to_px(TRIM_H_IN)
    safe_px = in_to_px(SAFE_FROM_BLEED_IN)

    return {
        # Pixel width/height totals
        "total_w": round((BLEED_IN + TRIM_W_IN + spine_in + TRIM_W_IN + BLEED_IN) * DPI),
        "total_h": round((BLEED_IN + TRIM_H_IN + BLEED_IN) * DPI),
        # Region x-start positions
        "bleed_left": 0,
        "back_x": bleed_px,
        "spine_x": bleed_px + trim_px,
        "front_x": bleed_px + trim_px + spine_px,
        "bleed_right_x": bleed_px + trim_px + spine_px + trim_px,
        # Region widths
        "trim_w": trim_px,
        "spine_w": spine_px,
        "bleed_px": bleed_px,
        # Height
        "trim_h": trim_h_px,
        "total_y_safe_top": safe_px,
        "total_y_safe_bottom": bleed_px + trim_h_px - in_to_px(SAFE_MARGIN_IN),
        # Safe inset from left/right within a trim region
        "safe_inset": in_to_px(SAFE_MARGIN_IN),
    }
