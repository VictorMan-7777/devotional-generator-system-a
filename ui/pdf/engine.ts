/**
 * engine.ts — KDP PDF engine: DocumentRepresentation → 6x9 PDF bytes.
 *
 * Two-pass layout:
 *   Pass 1: render with default margins (0.375" gutter), count pages.
 *   Pass 2: if page count falls in a higher bracket, re-render with correct margins.
 *
 * Footnotes (FR-63): deferred via RenderContext.pendingFootnotes; placed at
 * page bottom before each page is finalized.
 *
 * Entry point: when invoked as a subprocess, reads JSON from stdin and writes
 * PDF bytes to stdout.
 *   stdin: { "document": <DocumentRepresentation>, "output_mode": "personal" | "publish-ready" }
 *   stdout: raw PDF bytes
 */

import { PDFDocument, rgb } from 'pdf-lib';
import { fileURLToPath } from 'url';
import { embedFonts, FONT_SIZES, type EmbeddedFonts } from './fonts.js';
import { calculateMargins, marginsToPoints, describeMarginBracket } from './margins.js';
import { checkCompliance, TRIM_WIDTH_PT, TRIM_HEIGHT_PT, type KDPComplianceResult } from './compliance.js';
import { renderBlock, renderPageFootnotes, type RenderContext } from './blocks.js';
import type { DocumentRepresentation, DocumentPage, DocumentBlock, PageNumberStyle } from './types.js';

// ── Constants ─────────────────────────────────────────────────────────────────

/** Default inside margin (points): first bracket (≤150 pages). */
const DEFAULT_INSIDE_PT = 0.375 * 72;

/** Height reserved at page bottom for page number and footnote separator. */
const PAGE_NUMBER_HEIGHT_PT = 20;

// ── Result type ───────────────────────────────────────────────────────────────

export interface PDFEngineResult {
  pdfBytes: Uint8Array;
  pageCount: number;
  /** Human-readable margin bracket, e.g. "24–150 pages: 0.375in gutter". */
  marginsBracket: string;
  complianceResult: KDPComplianceResult;
}

// ── Roman numeral conversion ──────────────────────────────────────────────────

function toRoman(n: number): string {
  if (n <= 0) return '';
  const vals = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1];
  const syms = ['m', 'cm', 'd', 'cd', 'c', 'xc', 'l', 'xl', 'x', 'ix', 'v', 'iv', 'i'];
  let result = '';
  let rem = n;
  for (let i = 0; i < vals.length; i++) {
    while (rem >= vals[i]) { result += syms[i]; rem -= vals[i]; }
  }
  return result;
}

// ── Page number rendering ─────────────────────────────────────────────────────

function drawPageNumber(
  page: ReturnType<PDFDocument['addPage']>,
  style: PageNumberStyle,
  numDisplay: number,
  fonts: EmbeddedFonts,
  contentX: number,
  contentWidth: number,
  y: number,
): void {
  if (style === 'suppressed') return;
  const text = style === 'roman' ? toRoman(numDisplay) : String(numDisplay);
  const font = fonts.regular;
  const size = FONT_SIZES.IMPRINT;
  const textWidth = font.widthOfTextAtSize(text, size);
  const x = contentX + (contentWidth - textWidth) / 2;
  page.drawText(text, { x, y, font, size, color: rgb(0, 0, 0) });
}

// ── Core layout engine ────────────────────────────────────────────────────────

interface LayoutResult {
  doc: PDFDocument;
  pageCount: number;
  /** All page dimensions used, for compliance check. */
  pageDimensions: Array<[number, number]>;
  /** Actual inside margin used, in inches. */
  insideMarginIn: number;
  outsideMarginIn: number;
  topMarginIn: number;
  bottomMarginIn: number;
}

async function renderLayout(
  document: DocumentRepresentation,
  outputMode: 'personal' | 'publish-ready',
  insideIn: number,
  outsideIn: number,
  topIn: number,
  bottomIn: number,
): Promise<LayoutResult> {
  const doc = await PDFDocument.create();
  const fonts = await embedFonts(doc);

  const insidePt = insideIn * 72;
  const outsidePt = outsideIn * 72;
  const topPt = topIn * 72;
  const bottomPt = bottomIn * 72;

  const contentX = insidePt;
  const contentWidth = TRIM_WIDTH_PT - insidePt - outsidePt;
  const contentTopY = TRIM_HEIGHT_PT - topPt;
  /** Lowest y the cursor may reach before a new page is started. */
  const contentFloorY = bottomPt + PAGE_NUMBER_HEIGHT_PT + 10;

  const pageDimensions: Array<[number, number]> = [];

  // Mutable state
  let currentPage = doc.addPage([TRIM_WIDTH_PT, TRIM_HEIGHT_PT]);
  pageDimensions.push([TRIM_WIDTH_PT, TRIM_HEIGHT_PT]);
  let pdfPageCount = 1;
  let cursor = { x: contentX, y: contentTopY };
  let pendingFootnotes: DocumentBlock[] = [];
  let currentStyle: PageNumberStyle = 'suppressed';
  let romanCounter = 0;
  let arabicCounter = 0;

  function finalizeCurrentPage(): void {
    const footnotesY = bottomPt + PAGE_NUMBER_HEIGHT_PT + 4;
    renderPageFootnotes(pendingFootnotes, currentPage, fonts, contentX, contentWidth, footnotesY);
    pendingFootnotes = [];
    const numDisplay = currentStyle === 'roman' ? romanCounter : arabicCounter;
    drawPageNumber(currentPage, currentStyle, numDisplay, fonts, contentX, contentWidth, bottomPt / 2);
  }

  function advancePage(style: PageNumberStyle, incrementCounter: boolean): void {
    finalizeCurrentPage();
    currentPage = doc.addPage([TRIM_WIDTH_PT, TRIM_HEIGHT_PT]);
    pageDimensions.push([TRIM_WIDTH_PT, TRIM_HEIGHT_PT]);
    pdfPageCount++;
    cursor = { x: contentX, y: contentTopY };
    currentStyle = style;
    if (incrementCounter) {
      if (style === 'roman') romanCounter++;
      else if (style === 'arabic') arabicCounter++;
    }
  }

  const allDocPages: DocumentPage[] = [...document.front_matter, ...document.content_pages];

  for (let di = 0; di < allDocPages.length; di++) {
    const docPage = allDocPages[di];
    const pageStyle = docPage.page_number_style ?? 'arabic';

    if (di === 0) {
      // First page: already created; just initialize style and counter
      currentStyle = pageStyle;
      if (pageStyle === 'roman') romanCounter = 1;
      else if (pageStyle === 'arabic') arabicCounter = 1;
    } else {
      advancePage(pageStyle, true);
    }

    cursor = { x: contentX, y: contentTopY };

    for (const block of docPage.blocks) {
      if (block.block_type === 'page_break') {
        // Explicit page break: new PDF page, same style, no counter increment
        advancePage(pageStyle, false);
        cursor = { x: contentX, y: contentTopY };
        continue;
      }

      // Overflow check: start a new page before rendering if cursor is too low
      if (cursor.y < contentFloorY) {
        advancePage(pageStyle, false);
        if (pageStyle === 'roman') romanCounter++;
        else if (pageStyle === 'arabic') arabicCounter++;
        cursor = { x: contentX, y: contentTopY };
      }

      const ctx: RenderContext = {
        page: currentPage,
        fonts,
        cursor,
        contentWidth,
        contentX,
        pendingFootnotes,
      };

      const result = renderBlock(block, ctx);
      cursor = result.cursor;
    }
  }

  // Finalize the last page
  finalizeCurrentPage();

  return {
    doc,
    pageCount: pdfPageCount,
    pageDimensions,
    insideMarginIn: insideIn,
    outsideMarginIn: outsideIn,
    topMarginIn: topIn,
    bottomMarginIn: bottomIn,
  };
}

// ── Public entry point ────────────────────────────────────────────────────────

/**
 * Generate a KDP-compliant PDF from a DocumentRepresentation.
 *
 * Implements the two-pass margin calculation:
 * 1. Pass 1 with default margins (smallest bracket) → count pages.
 * 2. Calculate correct margins for that page count.
 * 3. Pass 2 only if margins differ from Pass 1 margins.
 *
 * @param document - DocumentRepresentation from the Python rendering engine.
 * @param outputMode - 'personal' or 'publish-ready' (affects compliance enforcement).
 */
export async function generatePDF(
  document: DocumentRepresentation,
  outputMode: 'personal' | 'publish-ready',
): Promise<PDFEngineResult> {
  // --- Pass 1: default margins (0.375" gutter) ---
  const defaultIn = 0.375;
  const pass1 = await renderLayout(document, outputMode, defaultIn, defaultIn, defaultIn, defaultIn);

  // --- Calculate correct margins for pass 1 page count ---
  const finalMargins = calculateMargins(pass1.pageCount);
  const bracket = describeMarginBracket(pass1.pageCount);

  // --- Pass 2: only if inside margin changed ---
  const usePass1 = Math.abs(finalMargins.inside - defaultIn) < 0.001;
  const layout = usePass1
    ? pass1
    : await renderLayout(
        document,
        outputMode,
        finalMargins.inside,
        finalMargins.outside,
        finalMargins.top,
        finalMargins.bottom,
      );

  const pdfBytes = new Uint8Array(await layout.doc.save());

  // --- KDP compliance check ---
  const complianceResult = checkCompliance({
    pageDimensions: layout.pageDimensions,
    pageCount: layout.pageCount,
    insideMarginIn: layout.insideMarginIn,
    outsideMarginIn: layout.outsideMarginIn,
    topMarginIn: layout.topMarginIn,
    bottomMarginIn: layout.bottomMarginIn,
    fontsEmbedded: true, // pdf-lib with subset:false guarantees full embedding
    offerPagePresent: hasOfferPage(document),
    outputMode,
  });

  return {
    pdfBytes,
    pageCount: layout.pageCount,
    marginsBracket: bracket,
    complianceResult,
  };
}

/** Check whether the document's last content page contains offer page content (FR-94). */
function hasOfferPage(document: DocumentRepresentation): boolean {
  const lastPage = document.content_pages[document.content_pages.length - 1];
  if (!lastPage) return false;
  return lastPage.blocks.some(
    (b) => b.content.includes('sacredwhisperspublishing.com') || b.content.includes('offer'),
  );
}

// ── Subprocess entry point ────────────────────────────────────────────────────

interface SubprocessInput {
  document: DocumentRepresentation;
  output_mode: 'personal' | 'publish-ready';
}

async function runSubprocess(): Promise<void> {
  const chunks: Buffer[] = [];
  process.stdin.on('data', (chunk: Buffer) => chunks.push(chunk));
  process.stdin.on('end', async () => {
    try {
      const json = Buffer.concat(chunks).toString('utf8');
      const input = JSON.parse(json) as SubprocessInput;
      const result = await generatePDF(input.document, input.output_mode ?? 'publish-ready');
      process.stdout.write(result.pdfBytes);
    } catch (err) {
      process.stderr.write(`PDF engine error: ${String(err)}\n`);
      process.exit(1);
    }
  });
}

// Run as subprocess when invoked directly (e.g. npx tsx ui/pdf/engine.ts)
const isMain = process.argv[1] === fileURLToPath(import.meta.url);
if (isMain) {
  runSubprocess();
}
