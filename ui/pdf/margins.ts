/**
 * margins.ts — KDP margin calculation by page count.
 *
 * KDP specifies minimum inside (gutter) margins by page count bracket (FR-85).
 * Outside, top, and bottom margins use 0.375" (exceeds 0.250" minimum).
 *
 * Two-pass requirement: margins must be computed from the FINAL page count
 * after a first-pass layout. If first-pass count crosses a bracket boundary,
 * recalculate and re-render with corrected margins.
 */

/** Margin values in inches. Converted to points for pdf-lib: 1 inch = 72 points. */
export interface KDPMargins {
  inside: number;   // gutter (binding edge)
  outside: number;
  top: number;
  bottom: number;
}

/**
 * KDP page count brackets and their minimum inside margins (FR-85 table).
 *
 * page count range | min inside margin
 * 24–150           | 0.375"
 * 151–300          | 0.500"
 * 301–500          | 0.625"
 * 501–700          | 0.750"
 * 701–828          | 0.875"
 *
 * Outside, top, bottom: 0.375" (working default; exceeds 0.250" minimum).
 */
const INSIDE_MARGIN_BRACKETS: Array<{ maxPages: number; inside: number }> = [
  { maxPages: 150, inside: 0.375 },
  { maxPages: 300, inside: 0.500 },
  { maxPages: 500, inside: 0.625 },
  { maxPages: 700, inside: 0.750 },
  { maxPages: 828, inside: 0.875 },
];

const OUTSIDE_MARGIN_INCHES = 0.375;
const TOP_MARGIN_INCHES = 0.375;
const BOTTOM_MARGIN_INCHES = 0.375;

/**
 * Calculate KDP-compliant margins for a given page count.
 *
 * @param pageCount - Final page count from layout pass.
 * @returns KDPMargins with inside margin selected per FR-85 bracket.
 * @throws RangeError if pageCount exceeds KDP maximum of 828.
 */
export function calculateMargins(pageCount: number): KDPMargins {
  for (const bracket of INSIDE_MARGIN_BRACKETS) {
    if (pageCount <= bracket.maxPages) {
      return {
        inside: bracket.inside,
        outside: OUTSIDE_MARGIN_INCHES,
        top: TOP_MARGIN_INCHES,
        bottom: BOTTOM_MARGIN_INCHES,
      };
    }
  }
  throw new RangeError(
    `Page count ${pageCount} exceeds KDP maximum of 828 pages.`,
  );
}

/**
 * Convert margin inches to points (pdf-lib uses points: 1 inch = 72 pt).
 */
export function marginsToPoints(margins: KDPMargins): KDPMargins {
  return {
    inside: margins.inside * 72,
    outside: margins.outside * 72,
    top: margins.top * 72,
    bottom: margins.bottom * 72,
  };
}

/**
 * Describe the bracket for a given page count (for compliance reporting).
 *
 * @returns Human-readable bracket string, e.g. "24-150 pages: 0.375in gutter"
 */
export function describeMarginBracket(pageCount: number): string {
  const edges = [0, 150, 300, 500, 700, 828];
  const labels = [
    '24–150 pages: 0.375in gutter',
    '151–300 pages: 0.500in gutter',
    '301–500 pages: 0.625in gutter',
    '501–700 pages: 0.750in gutter',
    '701–828 pages: 0.875in gutter',
  ];
  for (let i = 0; i < INSIDE_MARGIN_BRACKETS.length; i++) {
    if (pageCount <= edges[i + 1]) {
      return labels[i];
    }
  }
  throw new RangeError(`Page count ${pageCount} exceeds KDP maximum.`);
}
