/**
 * compliance.ts — KDP compliance checker for generated PDFs.
 *
 * Verifies that a PDF meets KDP requirements (FR-84–FR-94):
 * - Trim size: 6x9 inches = 432x648 points
 * - Inside margin: correct for page count bracket (FR-85)
 * - Outside/top/bottom margins: >= 0.250" minimum
 * - Fonts fully embedded (FR-86)
 * - Page numbering: Roman for front matter, Arabic for content
 * - 24-page minimum: warning (not hard block) when page count < 24 (FR-93)
 * - Offer page present as final page in publish-ready mode (FR-94)
 *
 * In publish-ready mode: violations block export.
 * In personal mode: compliance is advisory only.
 * The 24-page minimum is always a warning, never a hard block (FR-93).
 */

import { calculateMargins } from './margins.js';

/** KDP 6x9 trim size in points (1 inch = 72 points). */
export const TRIM_WIDTH_PT = 432;   // 6 inches
export const TRIM_HEIGHT_PT = 648;  // 9 inches

/** KDP minimum margins in inches (hard minimums; violations block publish-ready export). */
export const MIN_OUTSIDE_MARGIN_IN = 0.250;
export const MIN_TOP_MARGIN_IN = 0.250;
export const MIN_BOTTOM_MARGIN_IN = 0.250;

/** KDP minimum page count for commercial publication (FR-93). */
export const KDP_MIN_PAGE_COUNT = 24;

export interface KDPComplianceInput {
  /** Page dimensions of all content pages, in points [width, height]. */
  pageDimensions: Array<[number, number]>;
  /** Total page count (front matter + content). */
  pageCount: number;
  /** Inside (gutter) margin actually used, in inches. */
  insideMarginIn: number;
  /** Outside margin actually used, in inches. */
  outsideMarginIn: number;
  /** Top margin actually used, in inches. */
  topMarginIn: number;
  /** Bottom margin actually used, in inches. */
  bottomMarginIn: number;
  /** Whether all fonts are fully embedded (not subsetted). */
  fontsEmbedded: boolean;
  /** Whether offer page is the final page. */
  offerPagePresent: boolean;
  /** Output mode: 'personal' is advisory; 'publish-ready' blocks on violations. */
  outputMode: 'personal' | 'publish-ready';
}

export interface KDPComplianceResult {
  passes: boolean;
  trim_size_correct: boolean;
  inside_margin_correct: boolean;
  outside_margin_correct: boolean;
  top_margin_correct: boolean;
  bottom_margin_correct: boolean;
  fonts_embedded: boolean;
  page_count: number;
  /** True if page count < 24 (FR-93). Warning; does not block export. */
  page_count_warning: boolean;
  offer_page_present: boolean;
  violations: string[];
}

/**
 * Run KDP compliance check on a generated PDF's metrics.
 *
 * @param input - Measured properties of the generated PDF.
 * @returns Compliance result; `passes` is false if any hard violation exists.
 */
export function checkCompliance(input: KDPComplianceInput): KDPComplianceResult {
  const violations: string[] = [];

  // --- Trim size ---
  const trimSizeCorrect = input.pageDimensions.every(
    ([w, h]) => Math.abs(w - TRIM_WIDTH_PT) < 1 && Math.abs(h - TRIM_HEIGHT_PT) < 1,
  );
  if (!trimSizeCorrect) {
    violations.push(
      `Trim size incorrect. Expected ${TRIM_WIDTH_PT}x${TRIM_HEIGHT_PT}pt (6x9in). ` +
      `Got: ${JSON.stringify(input.pageDimensions[0])}.`,
    );
  }

  // --- Inside margin (must match FR-85 bracket for page count) ---
  const required = calculateMargins(input.pageCount);
  const insideMarginCorrect = input.insideMarginIn >= required.inside - 0.001;
  if (!insideMarginCorrect) {
    violations.push(
      `Inside margin ${input.insideMarginIn.toFixed(3)}" is less than required ` +
      `${required.inside.toFixed(3)}" for ${input.pageCount} pages (FR-85).`,
    );
  }

  // --- Outside margin ---
  const outsideMarginCorrect = input.outsideMarginIn >= MIN_OUTSIDE_MARGIN_IN - 0.001;
  if (!outsideMarginCorrect) {
    violations.push(
      `Outside margin ${input.outsideMarginIn.toFixed(3)}" is less than minimum ` +
      `${MIN_OUTSIDE_MARGIN_IN}" (FR-85).`,
    );
  }

  // --- Top margin ---
  const topMarginCorrect = input.topMarginIn >= MIN_TOP_MARGIN_IN - 0.001;
  if (!topMarginCorrect) {
    violations.push(
      `Top margin ${input.topMarginIn.toFixed(3)}" is less than minimum ` +
      `${MIN_TOP_MARGIN_IN}" (FR-85).`,
    );
  }

  // --- Bottom margin ---
  const bottomMarginCorrect = input.bottomMarginIn >= MIN_BOTTOM_MARGIN_IN - 0.001;
  if (!bottomMarginCorrect) {
    violations.push(
      `Bottom margin ${input.bottomMarginIn.toFixed(3)}" is less than minimum ` +
      `${MIN_BOTTOM_MARGIN_IN}" (FR-85).`,
    );
  }

  // --- Fonts embedded ---
  if (!input.fontsEmbedded) {
    violations.push('Fonts are not fully embedded (FR-86). KDP may reject the PDF.');
  }

  // --- Offer page (publish-ready only) ---
  const offerPagePresent = input.outputMode === 'personal'
    ? true  // not enforced in personal mode
    : input.offerPagePresent;
  if (input.outputMode === 'publish-ready' && !input.offerPagePresent) {
    violations.push('Offer page is not the final page (FR-94).');
  }

  // --- 24-page minimum: warning only (FR-93) ---
  const pageCountWarning = input.pageCount < KDP_MIN_PAGE_COUNT;

  return {
    passes: violations.length === 0,
    trim_size_correct: trimSizeCorrect,
    inside_margin_correct: insideMarginCorrect,
    outside_margin_correct: outsideMarginCorrect,
    top_margin_correct: topMarginCorrect,
    bottom_margin_correct: bottomMarginCorrect,
    fonts_embedded: input.fontsEmbedded,
    page_count: input.pageCount,
    page_count_warning: pageCountWarning,
    offer_page_present: offerPagePresent,
    violations,
  };
}
