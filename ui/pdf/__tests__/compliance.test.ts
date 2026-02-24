/**
 * compliance.test.ts — Tests for margin calculation and KDP compliance checker.
 */

import { describe, it, expect } from 'vitest';
import { calculateMargins, marginsToPoints, describeMarginBracket } from '../margins.js';
import {
  checkCompliance,
  TRIM_WIDTH_PT,
  TRIM_HEIGHT_PT,
  KDP_MIN_PAGE_COUNT,
  type KDPComplianceInput,
} from '../compliance.js';

// ── calculateMargins ──────────────────────────────────────────────────────────

describe('calculateMargins', () => {
  it('returns 0.375in inside for 24 pages (lower bound of bracket)', () => {
    expect(calculateMargins(24).inside).toBe(0.375);
  });

  it('returns 0.375in inside for 100 pages', () => {
    expect(calculateMargins(100).inside).toBe(0.375);
  });

  it('returns 0.375in inside for 150 pages (upper bound of bracket)', () => {
    expect(calculateMargins(150).inside).toBe(0.375);
  });

  it('returns 0.500in inside for 151 pages (lower bound of second bracket)', () => {
    expect(calculateMargins(151).inside).toBe(0.500);
  });

  it('returns 0.500in inside for 200 pages', () => {
    expect(calculateMargins(200).inside).toBe(0.500);
  });

  it('returns 0.500in inside for 300 pages (upper bound)', () => {
    expect(calculateMargins(300).inside).toBe(0.500);
  });

  it('returns 0.625in inside for 400 pages', () => {
    expect(calculateMargins(400).inside).toBe(0.625);
  });

  it('returns 0.750in inside for 600 pages', () => {
    expect(calculateMargins(600).inside).toBe(0.750);
  });

  it('returns 0.875in inside for 800 pages', () => {
    expect(calculateMargins(800).inside).toBe(0.875);
  });

  it('returns 0.875in inside for 828 pages (KDP maximum)', () => {
    expect(calculateMargins(828).inside).toBe(0.875);
  });

  it('throws RangeError for page count > 828', () => {
    expect(() => calculateMargins(829)).toThrow(RangeError);
  });

  it('returns 0.375in outside for all brackets', () => {
    expect(calculateMargins(50).outside).toBe(0.375);
    expect(calculateMargins(500).outside).toBe(0.375);
  });

  it('returns 0.375in top and bottom for all brackets', () => {
    const m = calculateMargins(200);
    expect(m.top).toBe(0.375);
    expect(m.bottom).toBe(0.375);
  });
});

// ── marginsToPoints ───────────────────────────────────────────────────────────

describe('marginsToPoints', () => {
  it('converts 0.375in to 27pt', () => {
    const pts = marginsToPoints({ inside: 0.375, outside: 0.375, top: 0.375, bottom: 0.375 });
    expect(pts.inside).toBeCloseTo(27);
    expect(pts.outside).toBeCloseTo(27);
  });

  it('converts 0.500in to 36pt', () => {
    const pts = marginsToPoints({ inside: 0.5, outside: 0.375, top: 0.375, bottom: 0.375 });
    expect(pts.inside).toBeCloseTo(36);
  });
});

// ── describeMarginBracket ─────────────────────────────────────────────────────

describe('describeMarginBracket', () => {
  it('returns correct description for bracket 1', () => {
    expect(describeMarginBracket(100)).toBe('24–150 pages: 0.375in gutter');
  });

  it('returns correct description for bracket 2', () => {
    expect(describeMarginBracket(200)).toBe('151–300 pages: 0.500in gutter');
  });
});

// ── checkCompliance ───────────────────────────────────────────────────────────

/** Build a valid compliance input (all checks pass). */
function validInput(overrides: Partial<KDPComplianceInput> = {}): KDPComplianceInput {
  return {
    pageDimensions: [[TRIM_WIDTH_PT, TRIM_HEIGHT_PT]],
    pageCount: 30,
    insideMarginIn: 0.375,
    outsideMarginIn: 0.375,
    topMarginIn: 0.375,
    bottomMarginIn: 0.375,
    fontsEmbedded: true,
    offerPagePresent: true,
    outputMode: 'publish-ready',
    ...overrides,
  };
}

describe('checkCompliance — passing cases', () => {
  it('passes a fully valid input', () => {
    const result = checkCompliance(validInput());
    expect(result.passes).toBe(true);
    expect(result.violations).toHaveLength(0);
  });

  it('passes with personal mode (offer page not enforced)', () => {
    const result = checkCompliance(validInput({ outputMode: 'personal', offerPagePresent: false }));
    expect(result.passes).toBe(true);
  });
});

describe('checkCompliance — trim size', () => {
  it('fails when width is wrong', () => {
    const result = checkCompliance(validInput({ pageDimensions: [[400, 648]] }));
    expect(result.trim_size_correct).toBe(false);
    expect(result.passes).toBe(false);
    expect(result.violations[0]).toMatch(/Trim size/);
  });

  it('fails when height is wrong', () => {
    const result = checkCompliance(validInput({ pageDimensions: [[432, 600]] }));
    expect(result.trim_size_correct).toBe(false);
  });

  it('allows 1pt tolerance in trim size check', () => {
    const result = checkCompliance(validInput({ pageDimensions: [[432.5, 648.5]] }));
    expect(result.trim_size_correct).toBe(true);
  });
});

describe('checkCompliance — inside margin', () => {
  it('fails when inside margin is too small for page count', () => {
    // 200 pages requires 0.500", providing 0.375"
    const result = checkCompliance(validInput({ pageCount: 200, insideMarginIn: 0.375 }));
    expect(result.inside_margin_correct).toBe(false);
    expect(result.passes).toBe(false);
    expect(result.violations[0]).toMatch(/Inside margin/);
  });

  it('passes when inside margin exactly meets bracket requirement', () => {
    const result = checkCompliance(validInput({ pageCount: 200, insideMarginIn: 0.500 }));
    expect(result.inside_margin_correct).toBe(true);
  });
});

describe('checkCompliance — outside/top/bottom margins', () => {
  it('fails when outside margin is below minimum', () => {
    const result = checkCompliance(validInput({ outsideMarginIn: 0.200 }));
    expect(result.outside_margin_correct).toBe(false);
    expect(result.passes).toBe(false);
  });

  it('fails when top margin is below minimum', () => {
    const result = checkCompliance(validInput({ topMarginIn: 0.100 }));
    expect(result.top_margin_correct).toBe(false);
  });

  it('fails when bottom margin is below minimum', () => {
    const result = checkCompliance(validInput({ bottomMarginIn: 0.100 }));
    expect(result.bottom_margin_correct).toBe(false);
  });
});

describe('checkCompliance — font embedding', () => {
  it('fails when fonts are not embedded', () => {
    const result = checkCompliance(validInput({ fontsEmbedded: false }));
    expect(result.fonts_embedded).toBe(false);
    expect(result.passes).toBe(false);
    expect(result.violations.some(v => v.includes('FR-86'))).toBe(true);
  });
});

describe('checkCompliance — page count warning (FR-93)', () => {
  it('raises warning when page count < 24', () => {
    const result = checkCompliance(validInput({ pageCount: 20 }));
    expect(result.page_count_warning).toBe(true);
  });

  it('does NOT block export for page count < 24 (warning only)', () => {
    // All other fields valid; only page count < 24
    const result = checkCompliance(validInput({ pageCount: 20 }));
    expect(result.passes).toBe(true);  // warning ≠ violation
    expect(result.violations).toHaveLength(0);
  });

  it('does not raise warning when page count == 24', () => {
    const result = checkCompliance(validInput({ pageCount: KDP_MIN_PAGE_COUNT }));
    expect(result.page_count_warning).toBe(false);
  });
});

describe('checkCompliance — offer page (FR-94)', () => {
  it('fails in publish-ready mode when offer page absent', () => {
    const result = checkCompliance(validInput({ offerPagePresent: false, outputMode: 'publish-ready' }));
    expect(result.offer_page_present).toBe(false);
    expect(result.passes).toBe(false);
    expect(result.violations.some(v => v.includes('FR-94'))).toBe(true);
  });

  it('passes in personal mode even when offer page absent', () => {
    const result = checkCompliance(validInput({ offerPagePresent: false, outputMode: 'personal' }));
    expect(result.offer_page_present).toBe(true);  // not enforced in personal mode
    expect(result.passes).toBe(true);
  });
});

describe('checkCompliance — multiple violations', () => {
  it('reports all violations when multiple checks fail', () => {
    const result = checkCompliance(validInput({
      pageDimensions: [[400, 600]],
      fontsEmbedded: false,
      offerPagePresent: false,
    }));
    expect(result.passes).toBe(false);
    expect(result.violations.length).toBeGreaterThanOrEqual(3);
  });
});
