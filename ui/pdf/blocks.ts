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
 * Wrap text into lines that fit within maxWidth at the given font/size.
 * Preserves explicit newlines in content.
 */
export function wrapText(
  text: string,
  font: PDFFont,
  fontSize: number,
  maxWidth: number,
): string[] {
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

// ── Block renderers ─────────────────────────────────────────────────────────

function renderHeading(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.bold;
  const size = FONT_SIZES.HEADING;
  const lineHeight = size * LEADING;
  const lines = wrapText(block.content, font, size, ctx.contentWidth);
  const cursor = drawLines(lines, ctx.page, font, size, ctx.contentX, ctx.cursor.y, lineHeight);
  return { cursor: { ...cursor, y: cursor.y - BLOCK_SPACING } };
}

function renderBodyText(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.regular;
  const size = FONT_SIZES.BODY;
  const lineHeight = size * LEADING;
  const lines = wrapText(block.content, font, size, ctx.contentWidth);
  const cursor = drawLines(lines, ctx.page, font, size, ctx.contentX, ctx.cursor.y, lineHeight);
  return { cursor: { ...cursor, y: cursor.y - BLOCK_SPACING } };
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
  const cursor = drawLines(lines, ctx.page, font, size, ctx.contentX, ctx.cursor.y, lineHeight);
  return { cursor: { ...cursor, y: cursor.y - BLOCK_SPACING * 2 } };
}

function renderSubtitle(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.italic;
  const size = FONT_SIZES.SUBTITLE;
  const lineHeight = size * LEADING;
  const lines = wrapText(block.content, font, size, ctx.contentWidth);
  const cursor = drawLines(lines, ctx.page, font, size, ctx.contentX, ctx.cursor.y, lineHeight);
  return { cursor: { ...cursor, y: cursor.y - BLOCK_SPACING } };
}

function renderImprint(block: DocumentBlock, ctx: RenderContext): RenderResult {
  const font = ctx.fonts.regular;
  const size = FONT_SIZES.IMPRINT;
  const lineHeight = size * LEADING;
  const lines = wrapText(block.content, font, size, ctx.contentWidth);
  const cursor = drawLines(lines, ctx.page, font, size, ctx.contentX, ctx.cursor.y, lineHeight);
  return { cursor: { ...cursor, y: cursor.y - BLOCK_SPACING } };
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
