# Phase 003 — KDP PDF Export

**Project**: devotional-generator-system-a
**Phase**: 003
**Version**: 1.0
**Date**: 2026-02-24
**Status**: APPROVED — operator decisions confirmed 2026-02-24; execution authorized

---

## Objective

Build the TypeScript PDF engine that converts a `DocumentRepresentation` (produced by the Phase 002 rendering engine) into a KDP-compliant 6x9 PDF. Stand up the KDP compliance checker. Verify PDF output against all FR-84 through FR-94 requirements.

**Why this phase is necessary:** PDF generation is a TypeScript responsibility (see `constitution.md`). Separating it from Phase 002 allows the Python rendering engine and the TypeScript PDF engine to be built and tested independently, with the `DocumentRepresentation` as the stable interface. Phase 004 UI will trigger PDF generation via the Python API, which delegates PDF rendering to this TypeScript layer.

**Success definition:** Given a `DocumentRepresentation` JSON payload, the TypeScript PDF engine produces a valid KDP-compliant PDF. The KDP compliance checker programmatically verifies: 6x9 trim size, correct inside margin for the book's page count, all fonts embedded, Arabic/Roman page numbering, 24-page minimum warning issued when applicable, offer page present as final page.

---

## Prerequisites

- Phase 001 complete and verified
- Phase 002 complete and verified (`DocumentRepresentation` schema frozen and JSON-serializable)
- PDF library selected (spike test from Phase 001 concluded)
- TypeScript/Node.js environment set up (Node.js 20 LTS, pnpm or npm)
- Open-source font files identified and licensed for embedding

---

## Inputs

- Phase 002 `DocumentRepresentation` JSON schema (exported from Python via JSON Schema)
- PRD v16: FR-84–FR-94 (KDP requirements)
- PRD v16: FR-85 table (margin by page count)
- PRD v16: FR-63 (Turabian footnote placement)
- Selected open-source fonts (see Step 2)

---

## Outputs

| File | Description |
|------|-------------|
| `ui/pdf/engine.ts` | TypeScript PDF engine: DocumentRepresentation → PDF bytes |
| `ui/pdf/margins.ts` | KDP margin calculation by page count |
| `ui/pdf/fonts.ts` | Font loading and embedding |
| `ui/pdf/blocks.ts` | Block-type renderers (heading, body text, block quote, footnote, etc.) |
| `ui/pdf/compliance.ts` | KDP compliance checker |
| `ui/fonts/` | Bundled open-source font files (TTF or OTF) |
| `ui/pdf/__tests__/engine.test.ts` | PDF engine unit and integration tests |
| `ui/pdf/__tests__/compliance.test.ts` | KDP compliance checker tests |
| `docs/system/outputs/<date>__01__planner__pdf-library-spike-result.md` | PDF library selection decision document (if not already created in Phase 001) |

---

## Steps

### Step 1: PDF Library Selection Confirmation

Before any implementation begins, confirm the PDF library selection from the Phase 001 spike test.

**Criteria for selection:**
- Must embed TTF/OTF fonts in the output PDF (FR-86)
- Must support precise margin control per page (FR-85)
- Must support footnotes placed at page bottom (FR-63)
- Must support block quotes with distinct indentation (FR-61, FR-62)
- Must produce PDFs with correct trim size (6x9 / 432x648 points) (FR-84)
- Must be actively maintained with TypeScript support

**Candidates (from spike test):**
- `pdf-lib`: Lower-level; full layout control; widely used; TypeScript native
- `React-PDF/renderer` (`@react-pdf/renderer`): Component-based; auto-pagination; TTF embedding; WCAG-aware

**If spike test result is not available:** Run the spike before proceeding. Spike must test font embedding, footnote placement, and dynamic margin setting.

**Decision to document:** Selected library name, version pinned, rationale. This is a one-way door — changing libraries in Phase 003 is expensive.

### Step 2: Font Selection and Bundling

Select two open-source fonts for embedding:
1. **Body text font (serif):** Must be readable at 10–12pt for book-length reading. Candidates: Libre Baskerville, EB Garamond, Lora (Google Fonts, OFL licensed).
2. **Heading font (can be same or different):** Must be elegant; pairs with body font.

**Requirements:**
- Both fonts must be OFL (Open Font License) or equivalent open-source license compatible with commercial PDF distribution
- Font files (TTF or OTF) must be bundled in `ui/fonts/` within the application, not downloaded at runtime
- Both fonts must be fully embedded in PDF output (not subsetted, to avoid KDP rejection)

**Operator review:** Operator selects fonts. Builder presents 2–3 options per role.

### Step 3: TypeScript Project Scaffold

Set up TypeScript project for the UI layer:

```
ui/
├── package.json
├── tsconfig.json
├── fonts/           # Bundled font files
├── pdf/
│   ├── engine.ts
│   ├── margins.ts
│   ├── fonts.ts
│   ├── blocks.ts
│   ├── compliance.ts
│   └── __tests__/
└── src/             # Review UI source (Phase 004)
```

TypeScript configuration:
- Target: ES2022 (Node.js 20 LTS)
- Strict mode enabled
- ESM modules
- Vitest for testing

### Step 4: KDP Margin Calculation Module

**`ui/pdf/margins.ts`**

```typescript
interface KDPMargins {
  inside: number;    // inches
  outside: number;   // inches
  top: number;       // inches
  bottom: number;    // inches
}

/**
 * Calculate KDP-compliant margins for a given page count.
 * Per FR-85 table:
 * 24–150 pages:   inside 0.375"
 * 151–300 pages:  inside 0.500"
 * 301–500 pages:  inside 0.625"
 * 501–700 pages:  inside 0.750"
 * 701–828 pages:  inside 0.875"
 * outside/top/bottom: 0.375" working default (exceeds 0.250" minimum)
 */
export function calculateMargins(pageCount: number): KDPMargins {
  let insideMargin: number;
  if (pageCount <= 150) insideMargin = 0.375;
  else if (pageCount <= 300) insideMargin = 0.500;
  else if (pageCount <= 500) insideMargin = 0.625;
  else if (pageCount <= 700) insideMargin = 0.750;
  else insideMargin = 0.875;

  return {
    inside: insideMargin,
    outside: 0.375,
    top: 0.375,
    bottom: 0.375,
  };
}
```

**Critical note:** Margins must be calculated from the **final page count** after a first-pass layout. If the first-pass page count crosses a margin bracket boundary, margins must be recalculated and layout re-run. This may require two layout passes.

### Step 5: Block-Type Renderers

**`ui/pdf/blocks.ts`** — renders each `DocumentBlock` type into PDF primitives:

```typescript
type BlockRenderer = (block: DocumentBlock, context: PDFContext) => void;

const renderers: Record<BlockType, BlockRenderer> = {
  heading: renderHeading,
  body_text: renderBodyText,
  block_quote: renderBlockQuote,      // FR-61, FR-62: indented, distinct visual treatment
  footnote: renderFootnote,           // FR-63: placed at page bottom
  prompt_list: renderPromptList,      // Be Still prompts
  action_list: renderActionList,      // Walk It Out items
  divider: renderDivider,             // Typographic rule (e.g., before sending prompt)
  page_break: renderPageBreak,
  title: renderTitle,
  subtitle: renderSubtitle,
  imprint: renderImprint,
  toc_entry: renderTocEntry,
};
```

**Footnote handling note:** Turabian footnotes (FR-63) must appear at the bottom of the page on which the quote appears — not at the end of the document. This requires tracking which page each block is on and placing footnotes before that page closes. This is the most technically complex rendering requirement. The implementation must handle the case where the block quote flows to a new page (footnote follows to new page).

### Step 6: PDF Engine

**`ui/pdf/engine.ts`** — main entry point:

```typescript
interface PDFEngineResult {
  pdfBytes: Uint8Array;
  pageCount: number;
  marginsBracket: string;  // e.g., "24-150 pages: 0.375in gutter"
  complianceResult: KDPComplianceResult;
}

export async function generatePDF(
  document: DocumentRepresentation,
  outputMode: 'personal' | 'publish-ready'
): Promise<PDFEngineResult> {
  // 1. First pass: render all blocks, count pages
  // 2. Calculate margins from page count
  // 3. If margin bracket changed from default, re-render with correct margins
  // 4. Embed fonts
  // 5. Apply page numbering (Roman for front matter, Arabic for content)
  // 6. Run KDP compliance check
  // 7. Return PDF bytes + compliance result
}
```

### Step 7: KDP Compliance Checker

**`ui/pdf/compliance.ts`**

```typescript
interface KDPComplianceResult {
  passes: boolean;
  trim_size_correct: boolean;       // 6x9 = 432x648 points
  inside_margin_correct: boolean;   // >= minimum for page count bracket
  outside_margin_correct: boolean;  // >= 0.250"
  top_margin_correct: boolean;      // >= 0.250"
  bottom_margin_correct: boolean;   // >= 0.250"
  fonts_embedded: boolean;
  page_count: number;
  page_count_warning: boolean;      // True if < 24 pages (FR-93)
  page_count_warning_acknowledged: boolean;  // Set by operator
  offer_page_present: boolean;      // Last page is offer page (FR-94)
  violations: string[];             // Descriptions of any compliance failures
}
```

The compliance checker must run automatically on every PDF export. In publish-ready mode, compliance violations block export. The 24-page minimum is a warning, not a hard block, but requires operator acknowledgment (FR-93).

### Step 8: Integration with Python API

The Python FastAPI server exposes a PDF export endpoint that calls the TypeScript PDF engine. Two integration patterns are viable:

**Option A: TypeScript subprocess**
Python spawns a TypeScript/Node.js process, passes `DocumentRepresentation` as JSON stdin, receives PDF bytes on stdout.

**Option B: TypeScript micro-server**
TypeScript runs a small localhost server on a fixed port. Python calls it via HTTP.

Both options must be documented in `constitution.md` before implementation. Recommendation: **Option A** (subprocess) for simplicity — no additional server process to manage.

The integration point must be tested end-to-end in this phase:
- Python rendering engine produces `DocumentRepresentation`
- Python API serializes to JSON, spawns TypeScript engine
- TypeScript returns PDF bytes
- Python stores PDF to disk

---

## Commit Points

### CP1: TypeScript Project Scaffold and Font Bundle

**Files to Stage:**
- `ui/package.json`
- `ui/tsconfig.json`
- `ui/fonts/` (selected font TTF/OTF files)
- `ui/pdf/fonts.ts`

**Commit Command:**
```bash
git add ui/package.json ui/tsconfig.json ui/fonts/ ui/pdf/fonts.ts
git commit -m "feat(phase-003): typescript project scaffold and bundled open-source fonts"
```

**Verification:**
- `cd ui && pnpm install` (or npm install) completes without error
- `npx tsc --noEmit` passes (no type errors in scaffold)
- Font files present in `ui/fonts/`; licenses documented in `ui/fonts/LICENSE.md`

**Rollback:**
```bash
git reset --soft HEAD~1
rm -rf ui/node_modules  # remove installed deps
```

---

### CP2: Margin Calculation and Compliance Checker

**Files to Stage:**
- `ui/pdf/margins.ts`
- `ui/pdf/compliance.ts`
- `ui/pdf/__tests__/compliance.test.ts`

**Commit Command:**
```bash
git add ui/pdf/margins.ts ui/pdf/compliance.ts "ui/pdf/__tests__/compliance.test.ts"
git commit -m "feat(phase-003): kdp margin calculation and compliance checker"
```

**Verification:**
- `cd ui && pnpm test` compliance tests pass:
  - `calculateMargins(100)` → inside 0.375"
  - `calculateMargins(200)` → inside 0.500"
  - `calculateMargins(400)` → inside 0.625"
  - `calculateMargins(600)` → inside 0.750"
  - `calculateMargins(800)` → inside 0.875"
  - Compliance check on mock PDF: page count < 24 → `page_count_warning: true`

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP3: Block-Type Renderers

**Files to Stage:**
- `ui/pdf/blocks.ts`
- `ui/pdf/__tests__/blocks.test.ts`

**Commit Command:**
```bash
git add ui/pdf/blocks.ts "ui/pdf/__tests__/blocks.test.ts"
git commit -m "feat(phase-003): block-type pdf renderers — all DocumentBlock types"
```

**Verification:**
- Block quote renders with visible indentation distinct from body text
- Footnote is associated with correct quote block (not floating)
- Heading renders at correct size/weight distinct from body text
- DIVIDER renders as a horizontal rule
- All BlockType values have a renderer (no "unhandled type" at runtime)

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP4: PDF Engine End-to-End

**Files to Stage:**
- `ui/pdf/engine.ts`
- `ui/pdf/__tests__/engine.test.ts`

**Commit Command:**
```bash
git add ui/pdf/engine.ts "ui/pdf/__tests__/engine.test.ts"
git commit -m "feat(phase-003): pdf engine — document representation to kdp-compliant 6x9 pdf"
```

**Verification:**
- Generate PDF from `SAMPLE_DOCUMENT` fixture (derived from Phase 002 sample)
- Open resulting PDF in Preview/Acrobat: confirm visual layout correct
- `compliance.check(pdfResult)` returns `passes: true` for valid input
- Page count is correct (6 days + front matter ≈ expected count)
- All fonts embedded (check with PDF inspector or `pdffonts` CLI)

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP5: Python-TypeScript Integration

**Files to Stage:**
- `src/api/pdf_export.py` (Python integration: serializes DocumentRepresentation, calls TypeScript engine)
- `tests/test_pdf_integration.py`
- Updated `constitution.md` if subprocess approach modified the boundary definition

**Commit Command:**
```bash
git add src/api/pdf_export.py tests/test_pdf_integration.py
git commit -m "feat(phase-003): python-typescript pdf integration — api serializes document, typescript renders pdf"
```

**Verification:**
- `python -c "from src.api.pdf_export import export_pdf; from tests.fixtures.sample_devotional import SAMPLE_BOOK; from src.rendering.engine import DocumentRenderer; doc = DocumentRenderer().render(SAMPLE_BOOK, 'publish-ready'); pdf_bytes = export_pdf(doc); print(f'PDF size: {len(pdf_bytes)} bytes')"` — prints non-zero byte count
- PDF is readable (open file, confirm first page shows title)
- Compliance check result returned alongside PDF bytes

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

## Acceptance Criteria

Phase 003 is complete when:

- [ ] PDF trim size is 6x9 inches (432x648 points)
- [ ] Inside margin is correct for page count bracket (all 5 brackets tested)
- [ ] Outside, top, bottom margins at least 0.375"
- [ ] Selected open-source fonts are embedded in PDF (verified by `pdffonts` or equivalent)
- [ ] Turabian footnote appears at bottom of the page where the quote appears
- [ ] Scripture and Quote blocks render as visually distinct block quotes
- [ ] Front matter uses Roman numerals or suppressed page numbers; content uses Arabic
- [ ] Each day begins on a new page
- [ ] Conditional TOC present for 12+ day book; absent for < 12 day book
- [ ] Offer page is final page of PDF in publish-ready mode
- [ ] 24-page minimum: warning correctly raised when page count < 24 (FR-93)
- [ ] KDP compliance checker passes on all valid test inputs
- [ ] Python-TypeScript integration: Python can call TypeScript engine and receive PDF bytes
- [ ] All commit points (CP1–CP5) executed and verified
- [ ] Font licenses documented; operator confirms fonts are acceptable

---

## Rollback Notes

**Emergency rollback (all of Phase 003):**
```bash
git log --oneline  # Find last Phase 002 commit
git reset --soft <last-phase-002-commit-hash>
rm -rf ui/node_modules  # Clean TypeScript dependencies
```

Phase 003 introduces no database state. Rollback is clean. Phase 004 integration testing depends on Phase 003; if Phase 003 is rolled back, Phase 004 cannot proceed.

**PDF library replacement risk:** If the selected PDF library proves incompatible with KDP requirements (e.g., cannot embed fonts correctly), the library must be replaced. This is a Phase 003 internal decision — replacing the library should not require changes to `DocumentRepresentation` schema (which is the interface contract). Changing the PDF library is expensive but contained within Phase 003.

---

## Verification Steps

1. `cd ui && pnpm test` → all TypeScript tests pass
2. `npx tsc --noEmit` → no TypeScript type errors
3. Generate PDF: confirm file is valid PDF (open in Preview)
4. Font check: `pdffonts output.pdf` (if `poppler-utils` available) → shows fonts as embedded
5. Trim size: confirm dimensions in PDF metadata or via inspector
6. Margin check: measure visible margin in rendered PDF at 100% zoom
7. Compliance check: `complianceResult.passes === true` for a valid 6-day book

---

## Gatekeeper Checklist

- [ ] PDF library selection is documented with rationale (not left implicit)
- [ ] Font licenses are documented and compatible with commercial PDF distribution
- [ ] Footnote handling approach for cross-page quotes is addressed (not deferred)
- [ ] Two-pass margin calculation is implemented (not just applying default margin)
- [ ] Python-TypeScript integration approach is documented in `constitution.md`
- [ ] All 5 commit points have files, command, verification, rollback

**Decision**: APPROVE / REVISE / REJECT

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-24 | Initial phase plan — Iteration 1 |
| 1.1 | 2026-02-24 | Operator approved: pdf-lib, EB Garamond, tsx invocation |
