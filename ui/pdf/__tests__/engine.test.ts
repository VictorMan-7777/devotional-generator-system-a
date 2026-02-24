/**
 * engine.test.ts — End-to-end tests for the PDF engine.
 *
 * Uses a TypeScript fixture derived from Phase 002's SAMPLE_BOOK
 * (7 days, Day 6 has sending_prompt, Day 7 has day7 section).
 *
 * Tests verify PDF bytes, page count, margin bracket, and compliance.
 */

import { describe, it, expect } from 'vitest';
import { PDFDocument } from 'pdf-lib';
import { generatePDF } from '../engine.js';
import type { DocumentRepresentation } from '../types.js';

// ── SAMPLE_DOCUMENT fixture ───────────────────────────────────────────────────

/**
 * Minimal DocumentRepresentation fixture for testing.
 * Structure matches Phase 002 SAMPLE_BOOK output (7 days, Day 7, offer page).
 *
 * Front matter: title (SUPPRESSED) + copyright (ROMAN) + introduction (ROMAN)
 * Content pages: 7 day pages + Day 7 integration page + offer page = 9 pages
 * Total estimated PDF pages: 12
 */
const SAMPLE_DOCUMENT: DocumentRepresentation = {
  title: 'Grace in the Ordinary: A Seven-Day Devotional',
  subtitle: 'Finding God in the Everyday Moments',
  front_matter: [
    {
      blocks: [
        { block_type: 'title', content: 'Grace in the Ordinary' },
        { block_type: 'subtitle', content: 'A Seven-Day Devotional' },
        { block_type: 'imprint', content: 'Sacred Whispers Publishers\nAll rights reserved.' },
      ],
      starts_new_page: false,
      page_number_style: 'suppressed',
    },
    {
      blocks: [
        { block_type: 'title', content: 'Copyright' },
        {
          block_type: 'body_text',
          content:
            'Copyright © 2026 Sacred Whispers Publishers. All rights reserved. No part of this publication may be reproduced without written permission.',
        },
        { block_type: 'imprint', content: 'Sacred Whispers Publishers\nPrinted in the United States of America' },
      ],
      starts_new_page: true,
      page_number_style: 'roman',
    },
    {
      blocks: [
        { block_type: 'heading', content: 'Introduction' },
        {
          block_type: 'body_text',
          content:
            'This devotional invites you into seven days of quiet reflection. Each day begins with Scripture, moves through wisdom, and invites your response. May you find grace in the ordinary.',
        },
        {
          block_type: 'body_text',
          content:
            '*If Day 7 falls on a Sunday, you may choose to join your congregation in worship and use the Sunday Worship Integration page as a bridge.*',
        },
      ],
      starts_new_page: true,
      page_number_style: 'roman',
    },
  ],
  content_pages: [
    // Days 1–5: standard structure
    ...Array.from({ length: 5 }, (_, i) => ({
      blocks: [
        { block_type: 'heading' as const, content: `Day ${i + 1} — Grace in Ordinary Moments` },
        {
          block_type: 'block_quote' as const,
          content: `"For by grace you have been saved through faith. And this is not your own doing; it is the gift of God." — Ephesians 2:8–9`,
        },
        {
          block_type: 'footnote' as const,
          content: `The Holy Bible, English Standard Version. Crossway, 2001. Ephesians 2:8–9.`,
        },
        {
          block_type: 'heading' as const,
          content: 'Reflection',
        },
        {
          block_type: 'body_text' as const,
          content: `Grace meets us precisely where we do not deserve it. Day ${i + 1} invites us to sit with the reality that God's love is not conditional upon our performance or our preparation. It simply is — steady, unfailing, and offered freely.`,
        },
        {
          block_type: 'heading' as const,
          content: 'Still Before God',
        },
        {
          block_type: 'prompt_list' as const,
          content: `Where did you notice grace today?\nWhat does it feel like to receive something you did not earn?\nHow might you extend that same grace to someone else this week?`,
        },
        {
          block_type: 'heading' as const,
          content: 'Walk It Out',
        },
        {
          block_type: 'action_list' as const,
          content: `Write one sentence about a moment of grace you experienced today.\nTell someone about what you are learning.\nPray: "Lord, open my eyes to Your grace today."`,
        },
      ],
      starts_new_page: true,
      page_number_style: 'arabic' as const,
    })),
    // Day 6: with sending_prompt
    {
      blocks: [
        { block_type: 'heading', content: 'Day 6 — Grace That Sustains' },
        {
          block_type: 'block_quote',
          content: '"My grace is sufficient for you, for my power is made perfect in weakness." — 2 Corinthians 12:9',
        },
        { block_type: 'footnote', content: 'The Holy Bible, English Standard Version. Crossway, 2001. 2 Corinthians 12:9.' },
        { block_type: 'heading', content: 'Reflection' },
        {
          block_type: 'body_text',
          content:
            'The apostle Paul asked three times for the thorn to be removed. Three times grace was the answer — not the removal, but the sufficiency. Today we sit with that tension.',
        },
        { block_type: 'heading', content: 'Still Before God' },
        {
          block_type: 'prompt_list',
          content: 'Where do you feel weak today?\nHow have you experienced sufficiency in that weakness?\nWhat would it mean to boast in your weaknesses?',
        },
        { block_type: 'heading', content: 'Walk It Out' },
        {
          block_type: 'action_list',
          content: 'Name one area of weakness and write it down.\nThank God for His grace in that exact place.\nShare your experience with a trusted friend.',
        },
        // Sending prompt (DIVIDER + BODY_TEXT, no HEADING per FR-95)
        { block_type: 'divider', content: '' },
        {
          block_type: 'body_text',
          content:
            'As you close this week of reflection, carry this truth with you: grace is not something you earn or lose. It is the very nature of the One who made you. Go, and live in that freedom.',
        },
      ],
      starts_new_page: true,
      page_number_style: 'arabic',
    },
    // Day 7: standard day
    {
      blocks: [
        { block_type: 'heading', content: 'Day 7 — Grace That Completes' },
        {
          block_type: 'block_quote',
          content: '"And I am sure of this, that he who began a good work in you will bring it to completion at the day of Jesus Christ." — Philippians 1:6',
        },
        { block_type: 'footnote', content: 'The Holy Bible, English Standard Version. Crossway, 2001. Philippians 1:6.' },
        { block_type: 'heading', content: 'Reflection' },
        {
          block_type: 'body_text',
          content: 'Seven days. Seven invitations to look for grace in the ordinary. What have you found? What surprised you? The work God began in you continues.',
        },
        { block_type: 'heading', content: 'Still Before God' },
        {
          block_type: 'prompt_list',
          content:
            'What is one thing you learned about grace this week?\nWhere did you most clearly see God at work?\nHow has this week changed how you will live going forward?',
        },
        { block_type: 'heading', content: 'Walk It Out' },
        {
          block_type: 'action_list',
          content: 'Write a brief letter to yourself about what you discovered.\nShare what you learned with your small group or a friend.\nCommit to one ongoing practice from this week.',
        },
      ],
      starts_new_page: true,
      page_number_style: 'arabic',
    },
    // Day 7 integration page
    {
      blocks: [
        { block_type: 'heading', content: 'Before the Service' },
        {
          block_type: 'body_text',
          content: 'Before you join your congregation, take five minutes in silence. Review the theme of this week. Bring one word or phrase with you into worship.',
        },
        {
          block_type: 'prompt_list',
          content:
            'Track A: What Scripture stayed with you this week?\nTrack B: What did you notice about grace in daily life?',
        },
        { block_type: 'heading', content: 'After the Service' },
        {
          block_type: 'body_text',
          content: 'After worship, return to this page. What did you hear that resonated with your week? How did the community reinforce what you received in solitude?',
        },
        {
          block_type: 'prompt_list',
          content:
            'Track A: How did the sermon connect to this week\'s theme?\nTrack B: What moment of corporate worship moved you?',
        },
      ],
      starts_new_page: true,
      page_number_style: 'arabic',
    },
    // Offer page (FR-94: must be final page)
    {
      blocks: [
        { block_type: 'heading', content: 'Continue Your Journey' },
        {
          block_type: 'body_text',
          content:
            'Discover more devotionals in the Sacred Whispers series at sacredwhisperspublishing.com. Each title is crafted to guide you deeper into Scripture and closer to the God who meets you in the ordinary.',
        },
      ],
      starts_new_page: true,
      page_number_style: 'arabic',
    },
  ],
  has_toc: false,
  has_day7: true,
  total_estimated_pages: null,
};

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('generatePDF — basic output', () => {
  it('returns PDF bytes with length > 0', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    expect(result.pdfBytes.length).toBeGreaterThan(0);
  }, 30000);

  it('produces a valid PDF (loadable by pdf-lib)', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    const loadedDoc = await PDFDocument.load(result.pdfBytes);
    expect(loadedDoc.getPageCount()).toBeGreaterThan(0);
  }, 30000);

  it('page count matches loaded PDF page count', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    const loadedDoc = await PDFDocument.load(result.pdfBytes);
    expect(loadedDoc.getPageCount()).toBe(result.pageCount);
  }, 30000);

  it('page count is at least 12 (3 front matter + 9 content pages)', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    expect(result.pageCount).toBeGreaterThanOrEqual(12);
  }, 30000);
});

describe('generatePDF — margins and compliance', () => {
  it('returns correct margin bracket for a short devotional', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    // A 7-day devotional fits comfortably in the 24–150 page bracket
    expect(result.marginsBracket).toBe('24–150 pages: 0.375in gutter');
  }, 30000);

  it('compliance check passes for valid SAMPLE_DOCUMENT in publish-ready mode', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    expect(result.complianceResult.passes).toBe(true);
    expect(result.complianceResult.violations).toHaveLength(0);
  }, 30000);

  it('compliance: trim size correct (6x9)', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    expect(result.complianceResult.trim_size_correct).toBe(true);
  }, 30000);

  it('compliance: inside margin correct', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    expect(result.complianceResult.inside_margin_correct).toBe(true);
  }, 30000);

  it('compliance: fonts embedded', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    expect(result.complianceResult.fonts_embedded).toBe(true);
  }, 30000);

  it('compliance: page_count_warning is raised (7-day devotional < 24 pages KDP minimum, FR-93)', async () => {
    // A 7-day devotional produces ~12 PDF pages, which is below the KDP commercial
    // minimum of 24 pages. FR-93 specifies this as a WARNING, not a hard block.
    // The compliance check still PASSES (warning ≠ violation).
    const result = await generatePDF(SAMPLE_DOCUMENT, 'publish-ready');
    expect(result.complianceResult.page_count_warning).toBe(true);
    expect(result.complianceResult.passes).toBe(true); // warning does not block
  }, 30000);
});

describe('generatePDF — personal mode', () => {
  it('personal mode also produces valid PDF bytes', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'personal');
    expect(result.pdfBytes.length).toBeGreaterThan(0);
  }, 30000);

  it('personal mode compliance passes (offer page not enforced)', async () => {
    const result = await generatePDF(SAMPLE_DOCUMENT, 'personal');
    expect(result.complianceResult.passes).toBe(true);
  }, 30000);
});
