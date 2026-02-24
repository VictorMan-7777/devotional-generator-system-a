/**
 * fonts.ts — Font loading and embedding for the KDP PDF engine.
 *
 * Loads EB Garamond TTF files bundled in ui/fonts/.
 * pdf-lib embeds fonts fully (not subsetted) to satisfy KDP requirements (FR-86).
 *
 * Font selection: EB Garamond Regular/Bold/Italic (OFL-licensed).
 * Operator-approved 2026-02-24.
 */

import { PDFDocument, PDFFont } from 'pdf-lib';
import fontkit from '@pdf-lib/fontkit';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const FONTS_DIR = resolve(__dirname, '../fonts');

export interface EmbeddedFonts {
  regular: PDFFont;
  bold: PDFFont;
  italic: PDFFont;
}

/**
 * Load EB Garamond font bytes from bundled TTF files.
 * Called once at the start of PDF generation.
 */
function loadFontBytes(): { regular: Uint8Array; bold: Uint8Array; italic: Uint8Array } {
  return {
    regular: new Uint8Array(readFileSync(resolve(FONTS_DIR, 'EBGaramond-Regular.ttf'))),
    bold: new Uint8Array(readFileSync(resolve(FONTS_DIR, 'EBGaramond-Bold.ttf'))),
    italic: new Uint8Array(readFileSync(resolve(FONTS_DIR, 'EBGaramond-Italic.ttf'))),
  };
}

/**
 * Embed EB Garamond fonts into a PDFDocument.
 *
 * pdf-lib embeds the full font (not subsetted) when subset=false.
 * Full embedding is required for KDP compliance (FR-86).
 *
 * Registers @pdf-lib/fontkit on the document before embedding custom TTF fonts.
 * This must be called before any custom font embedding.
 *
 * @param doc - The PDFDocument to embed fonts into.
 * @returns Embedded font references for Regular, Bold, and Italic.
 */
export async function embedFonts(doc: PDFDocument): Promise<EmbeddedFonts> {
  doc.registerFontkit(fontkit);
  const bytes = loadFontBytes();

  const [regular, bold, italic] = await Promise.all([
    doc.embedFont(bytes.regular, { subset: false }),
    doc.embedFont(bytes.bold, { subset: false }),
    doc.embedFont(bytes.italic, { subset: false }),
  ]);

  return { regular, bold, italic };
}

/**
 * Font size constants (in points).
 * KDP 6x9 body text at 11pt is within the comfortable 10–12pt reading range.
 */
export const FONT_SIZES = {
  TITLE: 24,
  SUBTITLE: 16,
  HEADING: 14,
  SUBHEADING: 12,
  BODY: 11,
  FOOTNOTE: 9,
  IMPRINT: 10,
} as const;

export type FontSizeKey = keyof typeof FONT_SIZES;
