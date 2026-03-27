# DevG Library Catalog Spec

## Purpose

The DevG library catalog is the general librarian's working inventory.

Live catalog:
- `data/library/resource-catalog.json`

Example cards only:
- `data/library/resource-catalog.examples.json`

It does not store passage answers. It stores the resources that make passage
answers possible:
- commentaries
- reference works
- dictionaries
- encyclopedias
- outline-capable resources
- quote-capable resources

The research librarian uses this catalog to answer worker requests for a
specific passage.

## Role split

### General librarian
- acquires resources
- studies the resource enough to build a usable card catalog entry
- normalizes metadata
- catalogs and shelves resources
- marks resources ready for worker use

### Research librarian
- answers passage-specific research requests
- searches within the cataloged library
- prepares shared resource bundles for workers
- raises acquisition requests when the library is too thin

## Catalog unit

The catalog unit is a resource, not a passage.

Examples:
- a commentary on Luke
- a commentary on Habakkuk
- a Bible dictionary
- a whole-Bible commentary
- a public-domain sermon collection

This keeps acquisition durable and reusable across many future passages.

## Card catalog principle

The catalog entry is the librarian's card for that resource.

Only resources that are actually in the library should have live cards.
Examples and training cards should stay out of the live catalog.

It may begin with obvious metadata, but it should not be limited to the table
of contents. A good card may require the general librarian to inspect:
- the introduction
- section headings
- sample pages
- article lists
- indexes
- the TOC

The goal is not full summarization. The goal is enough understanding that the
research librarian can ask:
- does this help with outline work?
- does this help with term/background work?
- does this help with exposition work?
- does this mainly help with quote/citation work?

## Minimum catalog fields

Each catalog entry should carry:

- `resource_id`
  - stable identifier
- `title`
  - normalized resource title
- `author_or_editor`
  - primary author/editor label
- `resource_type`
  - one of:
    - `book_commentary`
    - `whole_bible_commentary`
    - `dictionary`
    - `encyclopedia`
    - `sermon_collection`
    - `reference_work`
    - `outline_resource`
    - `quote_source`
- `scope`
  - one of:
    - `book`
    - `testament`
    - `whole_bible`
    - `topical`
- `covered_books`
  - explicit biblical books covered
- `covered_topics`
  - optional future topical coverage
- `supports_workers`
  - likely consumers such as:
    - `acquisition_librarian`
    - `research_librarian`
    - `outliner`
    - `exposition_writer`
    - `quote_selector`
    - `exposition_retriever`
- `capabilities`
  - which workers commonly use this resource
- `contains`
  - what the resource actually contains, such as:
    - `section_outlines`
    - `table_of_contents_outline`
    - `verse_commentary`
    - `book_introduction`
    - `term_articles`
    - `historical_articles`
    - `background_articles`
    - `page_images`
    - `publication_metadata`
- `serves_needs`
  - what kinds of questions it usually helps answer, such as:
    - `outline`
    - `structure`
    - `exposition`
    - `background`
    - `terms`
    - `quotes`
    - `citation`
    - `genre_help`
- `source_form`
  - one of:
    - `local`
    - `url`
    - `api`
    - `manual_import`
- `source_locator`
  - path, URL, or acquisition handle
- `citation_quality`
  - one of:
    - `high`
    - `medium`
    - `low`
    - `unknown`
- `approved_for_validator`
  - boolean
- `preferred_order`
  - integer priority within its category
- `acquisition_status`
  - one of:
    - `planned`
    - `acquired`
    - `cataloged`
    - `ready`
    - `retired`
- `catalog_status`
  - one of:
    - `draft`
    - `verified`
    - `deprecated`
- `notes`
  - freeform operational note

## Priority rules

For commentary help:
1. book-specific commentary
2. testament or genre help
3. whole-Bible commentary fallback

For quote work:
1. sources with proven full-citation yield
2. sources with partial yield
3. weak sources left available for validator lanes when possible

## Proactive acquisition

The general librarian should be able to acquire resources ahead of immediate
need.

Example:
- once Series 1 Volume 1 clarifies the next likely volumes,
- the general librarian can expand the library for those future books or
  themes over time,
- so the research librarian is not always starting from scarcity.

## Starter operating questions

Before acquisition, the general librarian should ask:
- what biblical books are likely next?
- which workers will need this resource?
- what does this resource actually contain beyond the TOC?
- is this better for outline help, exposition help, quotes, or reference use?
- is the citation quality high enough for competition work?
- is the resource shelf-ready or still raw?

## Immediate next use

The live catalog should be used to:
1. track resources actually in the library
2. support research-librarian bundle preparation
3. reduce ad hoc source guessing by workers

The example catalog should be used to:
1. teach the librarians what a good card can look like
2. provide training patterns without pretending the books are already owned
