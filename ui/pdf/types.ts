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
  page_number_style?: PageNumberStyle;
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
  total_estimated_pages?: number | null;
}
