"""
cover/engine.py — KDP-compliant full-wrap cover generator.

Renders a full-wrap cover PDF (back + spine + front) at 300 DPI using Pillow.

Supports three design concepts:
  - Typographic only (Option C): rich color palette, no external dependencies.
  - Photo + typographic (Option A): fetches a Unsplash image if
    UNSPLASH_ACCESS_KEY is set in environment; falls back to typographic.

Output: 300 DPI PNG (for review) and a KDP-ready PDF via img2pdf.
"""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.cover.concepts import CoverConcept
from src.cover.kdp_spec import (
    BARCODE_H_IN,
    BARCODE_W_IN,
    cover_zones_px,
    in_to_px,
    pt_to_px,
)

# ── Font loading ──────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent.parent
_FONT_DIR = _REPO_ROOT / "ui" / "fonts"


def _load_font(style: str, size_pt: float) -> ImageFont.FreeTypeFont:
    names = {
        "regular": "EBGaramond-Regular.ttf",
        "bold": "EBGaramond-Bold.ttf",
        "italic": "EBGaramond-Italic.ttf",
    }
    path = _FONT_DIR / names.get(style, names["regular"])
    return ImageFont.truetype(str(path), size=pt_to_px(size_pt))


# ── Gradient helpers ──────────────────────────────────────────────────────────

def _fill_gradient(
    img: Image.Image,
    x0: int, y0: int,
    x1: int, y1: int,
    color_top: tuple[int, int, int],
    color_bottom: tuple[int, int, int],
) -> None:
    """Fill a rectangular region with a top-to-bottom gradient."""
    region = Image.new("RGB", (x1 - x0, y1 - y0))
    draw = ImageDraw.Draw(region)
    height = y1 - y0
    for y in range(height):
        t = y / max(height - 1, 1)
        r = round(color_top[0] + (color_bottom[0] - color_top[0]) * t)
        g = round(color_top[1] + (color_bottom[1] - color_top[1]) * t)
        b = round(color_top[2] + (color_bottom[2] - color_top[2]) * t)
        draw.line([(0, y), (x1 - x0, y)], fill=(r, g, b))
    img.paste(region, (x0, y0))


# ── Text helpers ──────────────────────────────────────────────────────────────

def _wrap_lines(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Wrap text into lines no wider than max_w pixels."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_w and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
    center_x: int,
    top_y: int,
    line_spacing_pt: float = 6.0,
) -> int:
    """Draw centered multi-line text. Returns the y position after last line."""
    dummy_img = Image.new("RGB", (1, 1))
    dummy = ImageDraw.Draw(dummy_img)
    y = top_y
    for line in lines:
        bbox = dummy.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = center_x - text_w // 2
        draw.text((x, y), line, font=font, fill=color)
        line_h = bbox[3] - bbox[1]
        y += line_h + pt_to_px(line_spacing_pt)
    return y


# ── Unsplash photo fetch ──────────────────────────────────────────────────────

def _fetch_unsplash_image(query: str, width: int, height: int) -> Optional[Image.Image]:
    """
    Fetch a high-res photo from Unsplash. Returns None if no API key or on error.
    Set UNSPLASH_ACCESS_KEY in environment to enable.
    """
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if not access_key:
        return None
    try:
        import requests  # type: ignore[import]

        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "portrait"},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None
        photo_url = results[0]["urls"]["raw"] + f"&w={width}&h={height}&fit=crop"
        img_resp = requests.get(photo_url, timeout=30)
        img_resp.raise_for_status()
        return Image.open(io.BytesIO(img_resp.content)).convert("RGB").resize(
            (width, height), Image.LANCZOS
        )
    except Exception:
        return None


# ── Core renderers ────────────────────────────────────────────────────────────

def _render_front_cover(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    concept: CoverConcept,
    zones: dict[str, int],
    title: str,
    subtitle: str,
    author: str,
) -> None:
    p = concept.palette
    fx = zones["front_x"]
    tw = zones["trim_w"]
    bleed = zones["bleed_px"]
    total_h = zones["total_h"]
    safe = zones["safe_inset"]

    # ── Background ──
    _fill_gradient(img, fx, 0, fx + tw + bleed, total_h, p.background_top, p.background_bottom)

    content_x = fx + safe
    content_w = tw - safe * 2
    center_x = fx + tw // 2
    safe_top = zones["total_y_safe_top"]
    safe_bot = zones["total_y_safe_bottom"]
    usable_h = safe_bot - safe_top

    # ── Publisher imprint (top) ──
    imprint_font = _load_font("regular", 11)
    imprint_text = "✦  SACRED WHISPERS PUBLISHERS  ✦"
    imprint_lines = _wrap_lines(imprint_text, imprint_font, content_w)
    _draw_centered_text(draw, imprint_lines, imprint_font, p.subtitle, center_x, safe_top + pt_to_px(24))

    # ── Decorative rule (upper) ──
    rule_top_y = safe_top + pt_to_px(60)
    rule_h = max(2, pt_to_px(1))
    draw.rectangle(
        [content_x + pt_to_px(20), rule_top_y, content_x + content_w - pt_to_px(20), rule_top_y + rule_h],
        fill=p.rule,
    )

    # ── Title ──
    title_font = _load_font("italic", 52)
    title_lines = _wrap_lines(title, title_font, content_w)
    title_y = safe_top + int(usable_h * 0.18)
    title_end_y = _draw_centered_text(draw, title_lines, title_font, p.title, center_x, title_y, line_spacing_pt=10)

    # ── Decorative rule (below title) ──
    rule_mid_y = title_end_y + pt_to_px(16)
    draw.rectangle(
        [content_x + pt_to_px(40), rule_mid_y, content_x + content_w - pt_to_px(40), rule_mid_y + rule_h],
        fill=p.rule,
    )

    # ── Subtitle ──
    subtitle_font = _load_font("regular", 22)
    subtitle_lines = _wrap_lines(subtitle, subtitle_font, content_w)
    subtitle_y = rule_mid_y + pt_to_px(18)
    _draw_centered_text(draw, subtitle_lines, subtitle_font, p.subtitle, center_x, subtitle_y)

    # ── Author / publisher (bottom) ──
    author_font = _load_font("italic", 16)
    author_lines = _wrap_lines(author, author_font, content_w)
    author_y = safe_bot - pt_to_px(40)
    _draw_centered_text(draw, author_lines, author_font, p.author, center_x, author_y)

    # ── Lower decorative rule ──
    rule_bot_y = author_y - pt_to_px(14)
    draw.rectangle(
        [content_x + pt_to_px(20), rule_bot_y, content_x + content_w - pt_to_px(20), rule_bot_y + rule_h],
        fill=p.rule,
    )


def _render_back_cover(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    concept: CoverConcept,
    zones: dict[str, int],
    blurb: str,
    website: str,
) -> None:
    p = concept.palette
    bx = zones["back_x"]
    tw = zones["trim_w"]
    bleed = zones["bleed_px"]
    total_h = zones["total_h"]
    safe = zones["safe_inset"]

    # ── Background ──
    _fill_gradient(img, 0, 0, bx + tw, total_h, p.background_top, p.background_bottom)

    content_x = bx + safe
    content_w = tw - safe * 2
    center_x = bx + tw // 2
    safe_top = zones["total_y_safe_top"]
    safe_bot = zones["total_y_safe_bottom"]

    # ── Blurb text ──
    blurb_font = _load_font("regular", 13)
    blurb_lines = _wrap_lines(blurb, blurb_font, content_w)
    blurb_y = safe_top + pt_to_px(36)
    blurb_end_y = _draw_centered_text(draw, blurb_lines, blurb_font, p.back_blurb, center_x, blurb_y, line_spacing_pt=4)

    # ── Website ──
    web_font = _load_font("italic", 11)
    web_lines = _wrap_lines(website, web_font, content_w)
    web_y = blurb_end_y + pt_to_px(24)
    _draw_centered_text(draw, web_lines, web_font, p.subtitle, center_x, web_y)

    # ── ISBN barcode zone: white box, bottom-right of back cover ──
    barcode_w = in_to_px(BARCODE_W_IN)
    barcode_h = in_to_px(BARCODE_H_IN)
    barcode_margin = in_to_px(0.25)
    barcode_x = bx + tw - barcode_margin - barcode_w
    barcode_y = safe_bot - barcode_h
    draw.rectangle([barcode_x, barcode_y, barcode_x + barcode_w, barcode_y + barcode_h], fill=(255, 255, 255))
    # Subtle label
    label_font = _load_font("regular", 7)
    draw.text(
        (barcode_x + 4, barcode_y + 4),
        "ISBN / Barcode",
        font=label_font,
        fill=(180, 180, 180),
    )


def _render_spine(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    concept: CoverConcept,
    zones: dict[str, int],
    title: str,
    author: str,
) -> None:
    p = concept.palette
    sx = zones["spine_x"]
    sw = zones["spine_w"]
    total_h = zones["total_h"]

    # Fill spine background
    draw.rectangle([sx, 0, sx + sw, total_h], fill=p.spine_bg)

    if sw < pt_to_px(18):
        # Too thin for text — skip
        return

    # Spine text is rotated 90° (bottom-to-top, reading left-to-right when spine faces right)
    spine_font_size = max(8, min(14, sw / pt_to_px(1) * 0.55))
    spine_font = _load_font("italic", spine_font_size)

    spine_text = f"{title}  ·  {author}"
    # Create a temporary image for rotated text
    dummy_img = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.textbbox((0, 0), spine_text, font=spine_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Render text on a temporary surface, then rotate and paste
    tmp = Image.new("RGBA", (text_w + 10, text_h + 10), (0, 0, 0, 0))
    tmp_draw = ImageDraw.Draw(tmp)
    tmp_draw.text((5, 5), spine_text, font=spine_font, fill=p.spine_text)
    rotated = tmp.rotate(90, expand=True)

    # Center on spine
    rx = sx + (sw - rotated.width) // 2
    ry = (total_h - rotated.height) // 2

    img.paste(rotated, (rx, ry), mask=rotated)


# ── Photo overlay (Option A) ──────────────────────────────────────────────────

def _apply_photo_background(
    img: Image.Image,
    concept: CoverConcept,
    zones: dict[str, int],
) -> None:
    """Fetch an Unsplash photo and apply it as the front cover background with a color overlay."""
    fw = zones["trim_w"] + zones["bleed_px"]
    fh = zones["total_h"]
    photo = _fetch_unsplash_image(concept.unsplash_query or "", fw, fh)
    if photo is None:
        return  # graceful fallback — gradient already rendered

    photo = photo.resize((fw, fh), Image.LANCZOS)

    # Paste photo over gradient on front cover region
    fx = zones["front_x"]
    img.paste(photo, (fx, 0))

    # Color overlay to ensure text readability
    overlay_color = concept.palette.background_top
    overlay = Image.new("RGBA", (fw, fh), (*overlay_color, round(concept.photo_overlay_opacity * 255)))
    front_region = img.crop((fx, 0, fx + fw, fh)).convert("RGBA")
    blended = Image.alpha_composite(front_region, overlay).convert("RGB")
    img.paste(blended, (fx, 0))


# ── Public entry point ────────────────────────────────────────────────────────

def render_cover(
    concept: CoverConcept,
    *,
    title: str,
    subtitle: str,
    author: str,
    blurb: str,
    website: str = "sacredwhisperspublishing.com",
    page_count: int = 60,
    output_dir: Path,
) -> dict[str, Path]:
    """
    Render a full-wrap KDP cover for the given concept.

    Returns paths to the generated PNG and PDF.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    zones = cover_zones_px(page_count)
    total_w = zones["total_w"]
    total_h = zones["total_h"]

    img = Image.new("RGB", (total_w, total_h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Render regions
    _render_back_cover(img, draw, concept, zones, blurb=blurb, website=website)
    _render_spine(img, draw, concept, zones, title=title, author=author)
    _render_front_cover(img, draw, concept, zones, title=title, subtitle=subtitle, author=author)

    # Optionally replace front cover background with Unsplash photo
    if concept.unsplash_query:
        _apply_photo_background(img, concept, zones)
        # Re-draw text on top of photo
        draw2 = ImageDraw.Draw(img)
        _render_front_cover(img, draw2, concept, zones, title=title, subtitle=subtitle, author=author)

    # Save PNG (review copy)
    png_path = output_dir / f"cover_{concept.design_id}.png"
    img.save(str(png_path), "PNG", dpi=(300, 300))

    # Save PDF (KDP submission copy)
    import img2pdf  # type: ignore[import]
    pdf_path = output_dir / f"cover_{concept.design_id}.pdf"
    # img2pdf expects bytes or a file path; write PNG to temp file then convert
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    img.save(str(tmp_path), "PNG", dpi=(300, 300))
    pdf_bytes = img2pdf.convert(str(tmp_path), dpi=300)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    tmp_path.unlink(missing_ok=True)

    return {"png": png_path, "pdf": pdf_path}
