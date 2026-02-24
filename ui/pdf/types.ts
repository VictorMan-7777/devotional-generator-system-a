/**
 * types.ts — TypeScript types mirroring the Python DocumentRepresentation schema.
 *
 * This is the frozen Python→TypeScript interface contract.
 * Do NOT modify without updating src/models/document.py and constitution.md.
 *
 * Source: src/models/document.py (Phase 002, frozen contract)
 */

export type BlockType =
  | 'heading'
  | 'body_text'
  | 'block_quote'
  | 'footnote'
  | 'prompt_list'
  | 'action_list'
  | 'divider'
  | 'page_break'
  | 'title'
  | 'subtitle'
  | 'imprint'
  | 'toc_entry';

export type PageNumberStyle = 'roman' | 'arabic' | 'suppressed';

export interface DocumentBlock {
  block_type: BlockType;
  content: string;
  /**
   * @deprecated Reserved — not consumed by the Phase 003 PDF engine.
   * The engine reads page_number_style from DocumentPage only.
   * Do not remove: field is present in Python schema and may be used by Phase 004 UI.
   */
  page_number_style?: PageNumberStyle;
  /**
   * @deprecated Reserved — not consumed by the Phase 003 PDF engine.
   * Populated by Phase 002 renderers (e.g., {"heading_level": 2}, {"footnote_id": "tw"}).
   * Do not remove: Phase 004 UI may read heading level for display hierarchy.
   */
  metadata?: Record<string, unknown>;
}

export interface DocumentPage {
  blocks: DocumentBlock[];
  starts_new_page?: boolean;
  page_number_style?: PageNumberStyle;
}

export interface DocumentRepresentation {
  title: string;
  subtitle?: string | null;
  front_matter: DocumentPage[];
  content_pages: DocumentPage[];
  has_toc: boolean;
  has_day7: boolean;
  /**
   * @deprecated Reserved — not consumed by the Phase 003 PDF engine.
   * Currently always None/null from the Python renderer; the engine computes its
   * own page count from the two-pass layout. Do not use for layout decisions.
   */
  total_estimated_pages?: number | null;
}
