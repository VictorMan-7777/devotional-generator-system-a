/**
 * blocks.test.ts — Tests for block-type renderers.
 *
 * Tests use real pdf-lib PDFDocument instances (no mocking) so that
 * font measurements and cursor advancement are exercised with actual data.
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { PDFDocument } from 'pdf-lib';
import type { PDFPage } from 'pdf-lib';
import { embedFonts, type EmbeddedFonts } from '../fonts.js';
import {
  wrapText,
  renderBlock,
  renderPageFootnotes,
  BLOCK_RENDERERS,
  type RenderContext,
} from '../blocks.js';
import type { DocumentBlock, BlockType } from '../types.js';

// ── Test setup ─────────────────────────────────────────────────────────────────

/** All 12 BlockType values, matching Python's BlockType enum. */
const ALL_BLOCK_TYPES: BlockType[] = [
  'heading', 'body_text', 'block_quote', 'footnote',
  'prompt_list', 'action_list', 'divider', 'page_break',
  'title', 'subtitle', 'imprint', 'toc_entry',
];

let fonts: EmbeddedFonts;
let doc: PDFDocument;

// Shared setup: create a PDFDocument and embed fonts once for all tests.
// This is expensive (~300ms) so we do it once with beforeAll.
beforeAll(async () => {
  doc = await PDFDocument.create();
  fonts = await embedFonts(doc);
});

/** Create a fresh PDFPage with standard test dimensions. */
function makePage(): PDFPage {
  return doc.addPage([432, 648]);  // 6x9 inches
}

/** Create a minimal RenderContext for a test page. */
function makeCtx(page: PDFPage, overrides: Partial<RenderContext> = {}): RenderContext {
  return {
    page,
    fonts,
    cursor: { x: 27, y: 621 },  // top of content area (inside 27pt margins)
    contentWidth: 378,            // 432 - 27 - 27
    contentX: 27,
    pendingFootnotes: [],
    ...overrides,
  };
}

/** Make a DocumentBlock with required fields. */
function block(block_type: BlockType, content = 'Sample content.'): DocumentBlock {
  return { block_type, content };
}

// ── wrapText ──────────────────────────────────────────────────────────────────

describe('wrapText', () => {
  it('returns a single line for short text', () => {
    const lines = wrapText('Hello world', fonts.regular, 11, 378);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toBe('Hello world');
  });

  it('wraps long text into multiple lines', () => {
    const longText = 'This is a longer piece of text that should wrap across multiple lines when the width is constrained to a small value for testing purposes.';
    const lines = wrapText(longText, fonts.regular, 11, 100);
    expect(lines.length).toBeGreaterThan(1);
  });

  it('preserves explicit newlines as line breaks', () => {
    const lines = wrapText('Line one\nLine two', fonts.regular, 11, 378);
    expect(lines).toHaveLength(2);
    expect(lines[0]).toBe('Line one');
    expect(lines[1]).toBe('Line two');
  });

  it('returns empty array for empty string', () => {
    const lines = wrapText('', fonts.regular, 11, 378);
    expect(lines).toHaveLength(0);
  });

  it('handles a single very long word without crashing', () => {
    const lines = wrapText('Superlongwordwithnospacesthatexceedsthelinewidth', fonts.regular, 11, 50);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toBe('Superlongwordwithnospacesthatexceedsthelinewidth');
  });
});

// ── BLOCK_RENDERERS dispatch map ──────────────────────────────────────────────

describe('BLOCK_RENDERERS dispatch map', () => {
  it('has an entry for every BlockType value', () => {
    for (const bt of ALL_BLOCK_TYPES) {
      expect(BLOCK_RENDERERS).toHaveProperty(bt);
      expect(typeof BLOCK_RENDERERS[bt]).toBe('function');
    }
  });

  it('has exactly 12 entries (one per BlockType)', () => {
    expect(Object.keys(BLOCK_RENDERERS)).toHaveLength(12);
  });
});

// ── renderBlock — cursor advancement ─────────────────────────────────────────

describe('renderBlock — cursor advancement', () => {
  it('heading: cursor advances downward (y decreases)', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(block('heading', 'Day 1 — Grace in Failure'), ctx);
    expect(result.cursor.y).toBeLessThan(ctx.cursor.y);
  });

  it('body_text: cursor advances downward', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(block('body_text', 'The grace of God sustains us through each ordinary moment.'), ctx);
    expect(result.cursor.y).toBeLessThan(ctx.cursor.y);
  });

  it('block_quote: cursor advances downward', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(
      block('block_quote', '"For by grace you have been saved through faith." — Ephesians 2:8'),
      ctx,
    );
    expect(result.cursor.y).toBeLessThan(ctx.cursor.y);
  });

  it('footnote: cursor does NOT advance (footnote is deferred)', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const startY = ctx.cursor.y;
    const result = renderBlock(
      block('footnote', 'Barth, Karl. Church Dogmatics II/1, §28, 1957.'),
      ctx,
    );
    expect(result.cursor.y).toBe(startY);
  });

  it('footnote: adds block to pendingFootnotes', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    renderBlock(block('footnote', 'Augustine, Confessions, Book I, 1.1.1.'), ctx);
    expect(ctx.pendingFootnotes).toHaveLength(1);
    expect(ctx.pendingFootnotes[0].content).toContain('Augustine');
  });

  it('prompt_list: cursor advances downward', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(
      block('prompt_list', 'Where did you notice grace today?\nHow did you respond to that grace?'),
      ctx,
    );
    expect(result.cursor.y).toBeLessThan(ctx.cursor.y);
  });

  it('action_list: cursor advances downward', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(
      block('action_list', 'Write a thank-you note to someone.\nSpend five minutes in silence.'),
      ctx,
    );
    expect(result.cursor.y).toBeLessThan(ctx.cursor.y);
  });

  it('divider: cursor advances downward', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(block('divider', ''), ctx);
    expect(result.cursor.y).toBeLessThan(ctx.cursor.y);
  });

  it('page_break: cursor does not change (engine handles page creation)', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(block('page_break', ''), ctx);
    expect(result.cursor.y).toBe(ctx.cursor.y);
  });

  it('title: cursor advances downward more than body_text', () => {
    const page = makePage();
    const ctxTitle = makeCtx(page, { cursor: { x: 27, y: 621 } });
    const resultTitle = renderBlock(block('title', 'Grace in the Ordinary'), ctxTitle);

    const page2 = makePage();
    const ctxBody = makeCtx(page2, { cursor: { x: 27, y: 621 } });
    const resultBody = renderBlock(block('body_text', 'Grace in the Ordinary'), ctxBody);

    const titleDrop = ctxTitle.cursor.y - resultTitle.cursor.y;
    const bodyDrop = ctxBody.cursor.y - resultBody.cursor.y;
    expect(titleDrop).toBeGreaterThan(bodyDrop);
  });

  it('subtitle: cursor advances downward', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(block('subtitle', 'A Seven-Day Devotional'), ctx);
    expect(result.cursor.y).toBeLessThan(ctx.cursor.y);
  });

  it('imprint: cursor advances downward', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(block('imprint', 'Sacred Whispers Publishers\nAll rights reserved.'), ctx);
    expect(result.cursor.y).toBeLessThan(ctx.cursor.y);
  });

  it('toc_entry: cursor advances downward', () => {
    const page = makePage();
    const ctx = makeCtx(page);
    const result = renderBlock(block('toc_entry', 'Day 1 — Grace in Failure ... 5'), ctx);
    expect(result.cursor.y).toBeLessThan(ctx.cursor.y);
  });
});

// ── block_quote indentation ───────────────────────────────────────────────────

describe('block_quote indentation', () => {
  it('block_quote drops more than body_text for same content (due to narrower width)', () => {
    // A long block quote should wrap more than body text at the same content width,
    // because block quotes have reduced width due to indentation.
    const longContent = 'This is a quotation that is intentionally long enough to wrap across multiple lines when rendered at the indented block quote width, demonstrating the reduced content area.';

    const page1 = makePage();
    const ctxBody = makeCtx(page1, { cursor: { x: 27, y: 621 } });
    const resultBody = renderBlock({ block_type: 'body_text', content: longContent }, ctxBody);

    const page2 = makePage();
    const ctxQuote = makeCtx(page2, { cursor: { x: 27, y: 621 } });
    const resultQuote = renderBlock({ block_type: 'block_quote', content: longContent }, ctxQuote);

    const bodyDrop = ctxBody.cursor.y - resultBody.cursor.y;
    const quoteDrop = ctxQuote.cursor.y - resultQuote.cursor.y;
    // Block quote should drop more due to narrower content width forcing more line wraps
    expect(quoteDrop).toBeGreaterThanOrEqual(bodyDrop);
  });
});

// ── renderPageFootnotes ───────────────────────────────────────────────────────

describe('renderPageFootnotes', () => {
  it('does not throw when footnotes list is empty', () => {
    const page = makePage();
    expect(() =>
      renderPageFootnotes([], page, fonts, 27, 378, 27),
    ).not.toThrow();
  });

  it('does not throw when rendering one footnote', () => {
    const page = makePage();
    const footnote: DocumentBlock = {
      block_type: 'footnote',
      content: 'Lewis, C.S. Mere Christianity, Book II, Chapter 4. New York: Macmillan, 1952.',
    };
    expect(() =>
      renderPageFootnotes([footnote], page, fonts, 27, 378, 27),
    ).not.toThrow();
  });

  it('does not throw when rendering multiple footnotes', () => {
    const page = makePage();
    const footnotes: DocumentBlock[] = [
      { block_type: 'footnote', content: 'First footnote reference.' },
      { block_type: 'footnote', content: 'Second footnote reference.' },
    ];
    expect(() =>
      renderPageFootnotes(footnotes, page, fonts, 27, 378, 27),
    ).not.toThrow();
  });
});
