/**
 * blocks.ts — Block-type renderers for the KDP PDF engine.
 *
 * Each renderer takes a DocumentBlock and a RenderContext, draws onto the
 * current PDFPage, and returns the updated cursor position.
 *
 * Coordinate system (pdf-lib): origin at page bottom-left, y increases upward.
 * The cursor.y represents the current TOP of the next content to draw.
 * Renderers draw at cursor.y and return the new (lower) cursor.y.
 *
 * Footnote handling (FR-63):
 * Footnotes are collected via `pendingFootnotes` in RenderContext. The engine
 * (engine.ts) places them at the bottom of the page before closing it.
 */

import { PDFPage, PDFFont, rgb, LineCapStyle } from 'pdf-lib';
import type { DocumentBlock, BlockType } from './types.js';
import type { EmbeddedFonts } from './fonts.js';
import { FONT_SIZES } from './fonts.js';

// ── Constants ─────────────────────────────────────────────────────────────────

/** Leading multiplier: line height = font size * LEADING. */
const LEADING = 1.4;

/** Spacing after a block (points). Added below each rendered block. */
const BLOCK_SPACING = 8;

/** Indent for block quotes (points). Applied to left and right. */
const BLOCK_QUOTE_INDENT = 36; // 0.5"

/** Width of horizontal divider rule relative to content width. */
const DIVIDER_WIDTH_RATIO = 0.8;

/** Color constants. */
const COLOR_BLACK = rgb(0, 0, 0);
const COLOR_DARK_GRAY = rgb(0.3, 0.3, 0.3);

const HUMAN_SECTION_HEADINGS: Record<string, string> = {
  timeless_wisdom: 'Timeless Wisdom',
  scripture: 'Scripture Reading',
  exposition: 'Reflection',
  be_still: 'Still Before God',
  action_steps: 'Walk It Out',
  prayer: 'Prayer',
  sending_prompt: 'Sending Prompt',
  day7: 'Day 7 Reflection',
  title: 'Title',
};

/**
 * Defensive heading normalization:
 * convert internal section keys (e.g. `timeless_wisdom`) into reader-facing
 * labels before rendering into PDF.
 */
export function normalizeHeadingText(raw: string): string {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return raw;
  const normalizedKey = trimmed.toLowerCase().replace(/[\s-]+/g, '_');
  if (HUMAN_SECTION_HEADINGS[normalizedKey]) {
    return HUMAN_SECTION_HEADINGS[normalizedKey];
  }
  return raw;
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface RenderContext {
  page: PDFPage;
  fonts: EmbeddedFonts;
  /** Cursor in pdf-lib points (origin = bottom-left). y decreases as content fills down. */
  cursor: { x: number; y: number };
  /** Width of content area (page width minus left and right margins), in points. */
  contentWidth: number;
  /** Left x coordinate of content area (inside/outside margin, depending on page side). */
  contentX: number;
  /** Footnotes accumulated for the current page; engine places them at page bottom. */
  pendingFootnotes: DocumentBlock[];
}

export interface RenderResult {
  /** New cursor position after rendering the block. */
  cursor: { x: number; y: number };
}

// ── Text utilities ─────────────────────────────────────────────────────────────

/**
 * Normalize Unicode typographic ligature codepoints to plain ASCII sequences,
 * then insert ZWNJ (U+200C) between common ligature pairs (fi, fl, ff) to
 * prevent PDF viewers from applying OT GSUB substitution during rendering.
 *
 * Problem: pdf-lib/fontkit measures word widths using OT-aware shaping (fi → ﬁ
 * ligature advance), but the PDF content stream stores individual character
 * codes. Viewers then apply OT GSUB again during render, producing a glyph
 * whose advance width differs from the original f+i measured sum — creating
 * visible mid-word gaps ("specifi c", "Refl ection").
 *
 * Fix: ZWNJ (U+200C) has zero advance in EB Garamond so it does not shift
 * following characters, but it signals to OT shapers that the surrounding
 * characters must NOT be joined into a ligature. This keeps measurement and
 * rendering consistent.
 */
export function sanitizeText(text: string): string {
  return text
    .replace(/\uFB00/g, 'ff')   // ﬀ → ff
    .replace(/\uFB01/g, 'fi')   // ﬁ → fi
    .replace(/\uFB02/g, 'fl')   // ﬂ → fl
    .replace(/\uFB03/g, 'ffi')  // ﬃ → ffi
    .replace(/\uFB04/g, 'ffl')  // ﬄ → ffl
    .replace(/\uFB05/g, 'st')   // ﬅ → st
    .replace(/\uFB06/g, 'st')   // ﬆ → st
    // Insert ZWNJ to suppress viewer-side OT GSUB ligature substitution.
    .replace(/fi/g, 'f\u200Ci') // fi → f‌i (no fi ligature)
    .replace(/fl/g, 'f\u200Cl') // fl → f‌l (no fl ligature)
    .replace(/ff/g, 'f\u200Cf'); // ff → f‌f (no ff ligature)
}

/**
 * Wrap text into lines that fit within maxWidth at the given font/size.
 * Preserves explicit newlines in content.
 */
export function wrapText(
  text: string,
  font: PDFFont,
  fontSize: number,
  maxWidth: number,
): string[] {
  text = sanitizeText(text);
  if (text.length === 0) return [];
  const lines: string[] = [];

  for (const paragraph of text.split('\n')) {
    const words = paragraph.split(' ').filter((w) => w.length > 0);
    if (words.length === 0) {
      lines.push('');
      continue;
    }

    let current = '';
    for (const word of words) {
      const candidate = current.length === 0 ? word : `${current} ${word}`;
      if (font.widthOfTextAtSize(candidate, fontSize) <= maxWidth) {
        current = candidate;
      } else {
        if (current.length > 0) lines.push(current);
        current = word;
      }
    }
    if (current.length > 0) lines.push(current);
  }

  return lines;
}

/**
 * Draw a series of text lines and advance the cursor.
 * Returns the new cursor position.
 */
function drawLines(
  lines: string[],
  page: PDFPage,
  font: PDFFont,
  fontSize: number,
  startX: number,
  startY: number,
  lineHeight: number,
): { x: number; y: number } {
  let y = startY;
  for (const line of lines) {
    page.drawText(line, { x: startX, y: y - fontSize, font, size: fontSize, color: COLOR_BLACK });
    y -= lineHeight;
  }
  return { x: startX, y };
}

function blockAlign(block: DocumentBlock): 'left' | 'center' {
  const align = String(block.metadata?.align ?? '').toLowerCase();
  return align === 'center' ? 'center' : 'left';
}

// ── Block renderers ─────────────────────────────────────────────────────────

function renderHeading(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.bold;
  const size = FONT_SIZES.HEADING;
  const lineHeight = size * LEADING;
  const lines = wrapText(normalizeHeadingText(block.content), font, size, ctx.contentWidth);
  let y = ctx.cursor.y;
  for (const line of lines) {
    const textWidth = font.widthOfTextAtSize(line, size);
    const x = blockAlign(block) === 'center'
      ? ctx.contentX + (ctx.contentWidth - textWidth) / 2
      : ctx.contentX;
    ctx.page.drawText(line, { x, y: y - size, font, size, color: COLOR_BLACK });
    y -= lineHeight;
  }
  return { cursor: { x: ctx.contentX, y: y - BLOCK_SPACING } };
}

function renderBodyText(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.regular;
  const size = FONT_SIZES.BODY;
  const lineHeight = size * LEADING;
  const lines = wrapText(block.content, font, size, ctx.contentWidth);
  let y = ctx.cursor.y;
  for (const line of lines) {
    const textWidth = font.widthOfTextAtSize(line, size);
    const x = blockAlign(block) === 'center'
      ? ctx.contentX + (ctx.contentWidth - textWidth) / 2
      : ctx.contentX;
    ctx.page.drawText(line, { x, y: y - size, font, size, color: COLOR_BLACK });
    y -= lineHeight;
  }
  return { cursor: { x: ctx.contentX, y: y - BLOCK_SPACING } };
}

function renderBlockQuote(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.italic;
  const size = FONT_SIZES.BODY;
  const lineHeight = size * LEADING;
  const indentedX = ctx.contentX + BLOCK_QUOTE_INDENT;
  const indentedWidth = ctx.contentWidth - BLOCK_QUOTE_INDENT * 2;
  const lines = wrapText(block.content, font, size, indentedWidth);
  const cursor = drawLines(lines, ctx.page, font, size, indentedX, ctx.cursor.y, lineHeight);
  return { cursor: { ...cursor, y: cursor.y - BLOCK_SPACING } };
}

function renderFootnote(block: DocumentBlock, ctx: RenderContext): RenderResult {
  // Footnotes are deferred: add to pendingFootnotes for engine to place at page bottom.
  ctx.pendingFootnotes.push(block);
  // No cursor advancement here — footnotes don't occupy inline flow space.
  return { cursor: ctx.cursor };
}

function renderPromptList(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.regular;
  const size = FONT_SIZES.BODY;
  const lineHeight = size * LEADING;
  // Each prompt item on its own line with a bullet prefix.
  const items = block.content
    .split('\n')
    .filter((line) => line.trim().length > 0)
    .map((line) => `• ${line.trim()}`);
  const allLines: string[] = [];
  for (const item of items) {
    allLines.push(...wrapText(item, font, size, ctx.contentWidth));
  }
  const cursor = drawLines(allLines, ctx.page, font, size, ctx.contentX, ctx.cursor.y, lineHeight);
  return { cursor: { ...cursor, y: cursor.y - BLOCK_SPACING } };
}

function renderActionList(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.regular;
  const size = FONT_SIZES.BODY;
  const lineHeight = size * LEADING;
  const items = block.content
    .split('\n')
    .filter((line) => line.trim().length > 0)
    .map((line) => `→ ${line.trim()}`);
  const allLines: string[] = [];
  for (const item of items) {
    allLines.push(...wrapText(item, font, size, ctx.contentWidth));
  }
  const cursor = drawLines(allLines, ctx.page, font, size, ctx.contentX, ctx.cursor.y, lineHeight);
  return { cursor: { ...cursor, y: cursor.y - BLOCK_SPACING } };
}

function renderDivider(_block: DocumentBlock, ctx: RenderContext): RenderResult {
  const ruleWidth = ctx.contentWidth * DIVIDER_WIDTH_RATIO;
  const ruleX = ctx.contentX + (ctx.contentWidth - ruleWidth) / 2;
  const ruleY = ctx.cursor.y - 8; // 8pt below current cursor
  ctx.page.drawLine({
    start: { x: ruleX, y: ruleY },
    end: { x: ruleX + ruleWidth, y: ruleY },
    thickness: 0.5,
    color: COLOR_DARK_GRAY,
    lineCap: LineCapStyle.Round,
  });
  return { cursor: { x: ctx.contentX, y: ruleY - 8 - BLOCK_SPACING } };
}

function renderPageBreak(_block: DocumentBlock, ctx: RenderContext): RenderResult {
  // Page breaks signal the engine to start a new page.
  // The cursor is not meaningful after a page break; engine handles it.
  return { cursor: ctx.cursor };
}

function renderTitle(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.bold;
  const size = FONT_SIZES.TITLE;
  const lineHeight = size * LEADING;
  const lines = wrapText(block.content, font, size, ctx.contentWidth);
  let y = ctx.cursor.y;
  for (const line of lines) {
    const textWidth = font.widthOfTextAtSize(line, size);
    const x = blockAlign(block) === 'center'
      ? ctx.contentX + (ctx.contentWidth - textWidth) / 2
      : ctx.contentX;
    ctx.page.drawText(line, { x, y: y - size, font, size, color: COLOR_BLACK });
    y -= lineHeight;
  }
  return { cursor: { x: ctx.contentX, y: y - BLOCK_SPACING * 2 } };
}

function renderSubtitle(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.italic;
  const size = FONT_SIZES.SUBTITLE;
  const lineHeight = size * LEADING;
  const lines = wrapText(block.content, font, size, ctx.contentWidth);
  let y = ctx.cursor.y;
  for (const line of lines) {
    const textWidth = font.widthOfTextAtSize(line, size);
    const x = blockAlign(block) === 'center'
      ? ctx.contentX + (ctx.contentWidth - textWidth) / 2
      : ctx.contentX;
    ctx.page.drawText(line, { x, y: y - size, font, size, color: COLOR_BLACK });
    y -= lineHeight;
  }
  return { cursor: { x: ctx.contentX, y: y - BLOCK_SPACING } };
}

function renderImprint(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.regular;
  const size = FONT_SIZES.IMPRINT;
  const lineHeight = size * LEADING;
  const lines = wrapText(block.content, font, size, ctx.contentWidth);
  let y = ctx.cursor.y;
  for (const line of lines) {
    const textWidth = font.widthOfTextAtSize(line, size);
    const x = blockAlign(block) === 'center'
      ? ctx.contentX + (ctx.contentWidth - textWidth) / 2
      : ctx.contentX;
    ctx.page.drawText(line, { x, y: y - size, font, size, color: COLOR_BLACK });
    y -= lineHeight;
  }
  return { cursor: { x: ctx.contentX, y: y - BLOCK_SPACING } };
}

function renderTocEntry(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.regular;
  const size = FONT_SIZES.BODY;
  const lineHeight = size * LEADING;
  // TOC entries: content format "Day N — Focus Title ... pageNumber"
  const lines = wrapText(block.content, font, size, ctx.contentWidth);
  const cursor = drawLines(lines, ctx.page, font, size, ctx.contentX, ctx.cursor.y, lineHeight);
  return { cursor: { ...cursor, y: cursor.y - 4 } }; // tighter spacing for TOC
}

// ── Block height measurement ───────────────────────────────────────────────────

/**
 * Measure the vertical height (in points) a block will consume when rendered.
 *
 * Mirrors each renderer's wrapText + line-height + spacing logic exactly, so
 * the engine can decide whether to advance the page BEFORE drawing. Returns 0
 * for block types that don't consume vertical space in the normal flow (footnote,
 * page_break).
 */
export function measureBlockHeight(
  block: DocumentBlock,
  fonts: EmbeddedFonts,
  contentWidth: number,
): number {
  const lh = (size: number) => size * LEADING;
  switch (block.block_type) {
    case 'heading': {
      const size = FONT_SIZES.HEADING;
      const lines = wrapText(normalizeHeadingText(block.content), fonts.bold, size, contentWidth);
      return lines.length * lh(size) + BLOCK_SPACING;
    }
    case 'body_text': {
      const size = FONT_SIZES.BODY;
      const lines = wrapText(block.content, fonts.regular, size, contentWidth);
      return lines.length * lh(size) + BLOCK_SPACING;
    }
    case 'block_quote': {
      const size = FONT_SIZES.BODY;
      const indentedWidth = contentWidth - BLOCK_QUOTE_INDENT * 2;
      const lines = wrapText(block.content, fonts.italic, size, indentedWidth);
      return lines.length * lh(size) + BLOCK_SPACING;
    }
    case 'prompt_list': {
      const size = FONT_SIZES.BODY;
      const items = block.content
        .split('\n')
        .filter((l) => l.trim().length > 0)
        .map((l) => `• ${l.trim()}`);
      const totalLines = items.reduce(
        (n, item) => n + wrapText(item, fonts.regular, size, contentWidth).length,
        0,
      );
      return totalLines * lh(size) + BLOCK_SPACING;
    }
    case 'action_list': {
      const size = FONT_SIZES.BODY;
      const items = block.content
        .split('\n')
        .filter((l) => l.trim().length > 0)
        .map((l) => `→ ${l.trim()}`);
      const totalLines = items.reduce(
        (n, item) => n + wrapText(item, fonts.regular, size, contentWidth).length,
        0,
      );
      return totalLines * lh(size) + BLOCK_SPACING;
    }
    case 'divider':
      return 8 + 8 + BLOCK_SPACING; // offset above + below + spacing
    case 'title': {
      const size = FONT_SIZES.TITLE;
      const lines = wrapText(block.content, fonts.bold, size, contentWidth);
      return lines.length * lh(size) + BLOCK_SPACING * 2;
    }
    case 'subtitle': {
      const size = FONT_SIZES.SUBTITLE;
      const lines = wrapText(block.content, fonts.italic, size, contentWidth);
      return lines.length * lh(size) + BLOCK_SPACING;
    }
    case 'imprint': {
      const size = FONT_SIZES.IMPRINT;
      const lines = wrapText(block.content, fonts.regular, size, contentWidth);
      return lines.length * lh(size) + BLOCK_SPACING;
    }
    case 'toc_entry': {
      const size = FONT_SIZES.BODY;
      const lines = wrapText(block.content, fonts.regular, size, contentWidth);
      return lines.length * lh(size) + 4;
    }
    case 'footnote':
    case 'page_break':
    default:
      return 0;
  }
}

// ── Renderer dispatch map ──────────────────────────────────────────────────────

type BlockRenderer = (block: DocumentBlock, ctx: RenderContext) => RenderResult;

export const BLOCK_RENDERERS: Record<BlockType, BlockRenderer> = {
  heading: renderHeading,
  body_text: renderBodyText,
  block_quote: renderBlockQuote,
  footnote: renderFootnote,
  prompt_list: renderPromptList,
  action_list: renderActionList,
  divider: renderDivider,
  page_break: renderPageBreak,
  title: renderTitle,
  subtitle: renderSubtitle,
  imprint: renderImprint,
  toc_entry: renderTocEntry,
};

/**
 * Render a DocumentBlock onto the current page.
 *
 * @param block - The block to render.
 * @param ctx - Rendering context (page, fonts, cursor, footnote accumulator).
 * @returns Updated cursor position.
 */
export function renderBlock(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const renderer = BLOCK_RENDERERS[block.block_type];
  return renderer(block, ctx);
}

/**
 * Render accumulated footnotes at the bottom of the page (FR-63).
 * Called by the engine before closing a page that has footnotes.
 *
 * @param footnotes - Footnote blocks accumulated for this page.
 * @param page - The PDFPage to draw on.
 * @param fonts - Embedded font references.
 * @param contentX - Left x coordinate of content area.
 * @param contentWidth - Width of content area.
 * @param bottomY - Y coordinate of bottom margin (footnotes drawn above this).
 */
export function renderPageFootnotes(
  footnotes: DocumentBlock[],
  page: PDFPage,
  fonts: EmbeddedFonts,
  contentX: number,
  contentWidth: number,
  bottomY: number,
): void {
  if (footnotes.length === 0) return;

  const font = fonts.regular;
  const size = FONT_SIZES.FOOTNOTE;
  const lineHeight = size * LEADING;

  // Draw a short separator rule above footnotes.
  const ruleWidth = contentWidth * 0.3;
  const ruleY = bottomY + footnotes.length * lineHeight * 2 + 8;
  page.drawLine({
    start: { x: contentX, y: ruleY },
    end: { x: contentX + ruleWidth, y: ruleY },
    thickness: 0.5,
    color: COLOR_DARK_GRAY,
    lineCap: LineCapStyle.Round,
  });

  let y = ruleY - lineHeight;
  for (const footnote of footnotes) {
    const lines = wrapText(footnote.content, font, size, contentWidth);
    for (const line of lines) {
      page.drawText(line, { x: contentX, y: y - size, font, size, color: COLOR_DARK_GRAY });
      y -= lineHeight;
    }
  }
}
