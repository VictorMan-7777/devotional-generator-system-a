# Phase 002 — Template System

**Project**: devotional-generator-system-a
**Phase**: 002
**Version**: 1.0
**Date**: 2026-02-24
**Status**: Draft — Awaiting Gatekeeper approval

---

## Objective

Define and implement all content templates and the rendering engine that converts `DailyDevotional` schema instances into a structured `DocumentRepresentation` ready for Phase 003 PDF export. This phase produces no PDF output — it produces a serializable document model.

**Why this phase is necessary:** Separating template logic from PDF rendering allows both to be developed and tested independently. The rendering engine can be unit-tested with fixture data without requiring a running PDF library. Phase 003 consumes the `DocumentRepresentation`; any template logic issues are caught here before PDF complications are introduced.

**Success definition:** Given a mock `DevotionalBook` (using Phase 001 schemas), the rendering engine produces a complete `DocumentRepresentation` that includes all sections, all front matter, all optional elements (Day 7, sending prompt, TOC, offer page), and correct Turabian attribution metadata. Rendering engine output is validated against the document spec before Phase 003 begins.

---

## Prerequisites

- Phase 001 complete and all commit points verified
- All Pydantic schemas final and operator-approved
- `constitution.md` operator-approved
- Mock RAG interface operational
- TypeScript environment set up (Node.js, npm/pnpm, Vite)

---

## Inputs

- Phase 001 schemas: `DevotionalBook`, `DailyDevotional`, all section schemas
- PRD v16: Section 5 (daily structure), Section 9.12 (PDF layout), Section 9.13 (Day 7), FR-87–FR-97
- Reader-facing header strings: Timeless Wisdom, Scripture Reading, Reflection, Still Before God, Walk It Out, Prayer, Before the Service, After the Service (PRD D016, D061)

---

## Outputs

| File | Description |
|------|-------------|
| `src/models/document.py` | DocumentRepresentation and DocumentBlock schemas |
| `src/rendering/engine.py` | Python rendering engine: DevotionalBook → DocumentRepresentation |
| `src/rendering/sections.py` | Section-level renderers (one per section type) |
| `src/rendering/front_matter.py` | Front matter renderers (title, copyright, introduction, TOC, offer page) |
| `src/rendering/day7.py` | Day 7 and sending prompt renderers |
| `templates/introduction_sunday.md` | Static Sunday Worship Integration introduction block |
| `templates/offer_page.md` | Static offer page content (sacredwhisperspublishing.com) |
| `tests/test_rendering.py` | Rendering engine unit tests |
| `tests/fixtures/sample_devotional.py` | Complete mock DevotionalBook fixture for testing |

---

## Steps

### Step 1: DocumentRepresentation Schema

Define the intermediate representation that the rendering engine produces and the PDF engine consumes.

**`src/models/document.py`**

```python
class BlockType(str, Enum):
    # Content blocks
    HEADING = "heading"           # Section headers
    BODY_TEXT = "body_text"       # Regular paragraph text
    BLOCK_QUOTE = "block_quote"   # Indented block quote (FR-61, FR-62)
    FOOTNOTE = "footnote"         # Turabian attribution (FR-63)
    PROMPT_LIST = "prompt_list"   # Be Still prompts (bullet or numbered)
    ACTION_LIST = "action_list"   # Action Steps (bulleted)
    DIVIDER = "divider"           # Typographic rule (e.g., between sections, Day 6 sending prompt)
    PAGE_BREAK = "page_break"     # Each day on new page (FR-91)

    # Front matter blocks
    TITLE = "title"
    SUBTITLE = "subtitle"
    IMPRINT = "imprint"           # Sacred Whispers Publishers
    TOC_ENTRY = "toc_entry"

class PageNumberStyle(str, Enum):
    ROMAN = "roman"               # Front matter (or suppressed)
    ARABIC = "arabic"             # Content pages
    SUPPRESSED = "suppressed"

class DocumentBlock(BaseModel):
    block_type: BlockType
    content: str                  # Text content
    page_number_style: PageNumberStyle = PageNumberStyle.ARABIC
    metadata: Dict[str, Any] = {}  # e.g., {"footnote_id": "1", "author": "Spurgeon"}

class DocumentPage(BaseModel):
    blocks: List[DocumentBlock]
    starts_new_page: bool = False
    page_number_style: PageNumberStyle = PageNumberStyle.ARABIC

class DocumentRepresentation(BaseModel):
    title: str
    subtitle: Optional[str]
    front_matter: List[DocumentPage]
    content_pages: List[DocumentPage]
    has_toc: bool                 # True for 12+ days (FR-89)
    has_day7: bool
    total_estimated_pages: Optional[int] = None  # Set by PDF engine after rendering
```

This schema is the frozen contract between Python rendering engine and TypeScript PDF engine. It must be stable before Phase 003 begins.

### Step 2: Section Renderers

**`src/rendering/sections.py`** — one renderer per section type:

Each renderer takes the section schema object and returns a list of `DocumentBlock` instances:

```python
def render_timeless_wisdom(section: TimelessWisdomSection) -> List[DocumentBlock]:
    """
    Returns:
    - HEADING block: "Timeless Wisdom"
    - BLOCK_QUOTE block: quote_text
    - FOOTNOTE block: Turabian attribution (author, source_title, year, page/url)
    Note: footnote is associated with the BLOCK_QUOTE block via metadata["footnote_id"]
    """

def render_scripture(section: ScriptureSection) -> List[DocumentBlock]:
    """
    Returns:
    - HEADING block: "Scripture Reading"
    - BODY_TEXT block: reference (e.g., "Romans 8:15, NASB")
    - BLOCK_QUOTE block: scripture text
    """

def render_exposition(section: ExpositionSection) -> List[DocumentBlock]:
    """
    Returns:
    - HEADING block: "Reflection"
    - BODY_TEXT block: exposition text (full 500–700 word text)
    Note: Grounding Map is NOT included in DocumentRepresentation — it is a UI artifact (FR-79a)
    """

def render_be_still(section: BeStillSection) -> List[DocumentBlock]:
    """
    Returns:
    - HEADING block: "Still Before God"
    - PROMPT_LIST block: each prompt as list item
    """

def render_action_steps(section: ActionStepsSection) -> List[DocumentBlock]:
    """
    Returns:
    - HEADING block: "Walk It Out"
    - BODY_TEXT block: connector phrase
    - ACTION_LIST block: each action step as list item
    """

def render_prayer(section: PrayerSection) -> List[DocumentBlock]:
    """
    Returns:
    - HEADING block: "Prayer"
    - BODY_TEXT block: prayer text
    """

def render_sending_prompt(section: SendingPromptSection) -> List[DocumentBlock]:
    """
    Returns:
    - DIVIDER block (typographic rule — no section header per FR-95)
    - BODY_TEXT block: sending prompt text
    """

def render_day7(section: Day7Section) -> List[DocumentBlock]:
    """
    Returns:
    - HEADING block: "Before the Service"
    - BODY_TEXT block: before_service text
    - DIVIDER block
    - HEADING block: "After the Service"
    - HEADING block (sub): "Track A — When the sermon connected with this week's theme"
    - PROMPT_LIST block: track_a prompts
    - HEADING block (sub): "Track B — When the sermon went somewhere else"
    - PROMPT_LIST block: track_b prompts
    """
```

### Step 3: Front Matter Renderers

**`src/rendering/front_matter.py`**

```python
def render_title_page(title: str, subtitle: Optional[str]) -> DocumentPage:
    """
    Blocks: TITLE, optional SUBTITLE
    Page number style: SUPPRESSED
    """

def render_copyright_page(publication_year: int) -> DocumentPage:
    """
    Blocks: IMPRINT ("Sacred Whispers Publishers"), copyright notice
    No personal author name on published output (PRD D010)
    Page number style: ROMAN (page ii)
    """

def render_introduction(has_day7: bool, sunday_integration_text: Optional[str]) -> DocumentPage:
    """
    Renders the book introduction.
    If has_day7, appends the Sunday Worship Integration section (FR-97):
    - Static text from templates/introduction_sunday.md
    - 150–250 words; explains both movements, sending prompt purpose,
      states convergence and divergence equally valid
    Page number style: ROMAN
    """

def render_toc(days: List[DailyDevotional]) -> List[DocumentPage]:
    """
    Only for books with 12+ days (FR-89)
    TOC_ENTRY blocks: "Day N: [day_focus or topic]" with page references
    (Page references are placeholders until PDF engine assigns actual pages)
    """

def render_offer_page() -> DocumentPage:
    """
    Fixed content from templates/offer_page.md
    Must appear as the final page of every publish-ready export (FR-94)
    Content: sacredwhisperspublishing.com, call to action, personalized devotional offering
    """
```

### Step 4: Static Template Files

**`templates/introduction_sunday.md`** — operator-authored static content for Sunday Worship Integration introduction section (FR-97). Content:
- Explains Days 1–6 are private daily reading; Day 7 is different
- Describes two-movement Day 7 format (before and after worship)
- Explains Day 6 sending prompt purpose
- States convergence and divergence are equally valid
- Approximately 150–250 words
- Written by operator (Planner drafts; operator reviews and finalizes)

**`templates/offer_page.md`** — fixed offer page content (FR-94):
- Brief description of personalized devotional offering
- URL: https://sacredwhisperspublishing.com
- Call to action directing reader to website

**Note:** These templates are static; they do not vary by topic, theme, or day. Operator must review and approve both before Phase 002 closes.

### Step 5: Rendering Engine

**`src/rendering/engine.py`** — orchestrates section renderers into complete document:

```python
class DocumentRenderer:
    def render(
        self,
        book: DevotionalBook,
        output_mode: OutputMode,
    ) -> DocumentRepresentation:
        """
        1. Build front matter (title, copyright, introduction, optional TOC)
        2. For each day: render all 6 sections into a DocumentPage (new page per day)
        3. If Day 7 enabled: render sending prompt (appended after Day 6 prayer) and Day 7 page
        4. Append offer page (publish-ready mode only)
        5. Return DocumentRepresentation
        """
```

Logic notes:
- TOC is conditional: only if `len(book.days) >= 12` (FR-89)
- Sending prompt appended after Day 6 prayer block (not a new page — same Day 6 page)
- Day 7 is a new page (same as days 1–6)
- Offer page is the final page in publish-ready mode
- Personal mode: offer page may be omitted (operator preference — not specified in PRD; default to included)

### Step 6: Test Fixtures and Rendering Tests

**`tests/fixtures/sample_devotional.py`** — complete mock `DevotionalBook`:
- 6 days of mock content (using Phase 001 schemas with fixture data)
- Day 7 enabled (to test sending prompt and Day 7 rendering)
- All sections populated with valid mock strings at correct word counts

**`tests/test_rendering.py`**:
- Test: 6-day book renders correct number of content pages
- Test: TOC not rendered for books with fewer than 12 days
- Test: TOC rendered for books with 12+ days
- Test: Day 7 not rendered when num_days < 7
- Test: Day 7 page contains correct heading blocks ("Before the Service", "After the Service")
- Test: Sending prompt appears on Day 6 page, not on a new page
- Test: Sending prompt has no heading block (DIVIDER then BODY_TEXT)
- Test: Turabian footnote block appears in Timeless Wisdom render
- Test: Exposition render produces HEADING "Reflection" (not "Exposition")
- Test: Be Still render produces HEADING "Still Before God"
- Test: Action Steps render produces HEADING "Walk It Out"
- Test: Offer page appears as final page in DocumentRepresentation
- Test: Front matter uses ROMAN/SUPPRESSED page number style; content uses ARABIC

---

## Commit Points

### CP1: DocumentRepresentation Schema

**Files to Stage:**
- `src/models/document.py`
- `tests/test_document_schema.py` (schema-level validation tests)

**Commit Command:**
```bash
git add src/models/document.py tests/test_document_schema.py
git commit -m "feat(phase-002): document representation schema — frozen contract for PDF engine"
```

**Verification:**
- `pytest tests/test_document_schema.py -v` all pass
- All `BlockType` values present and consistent with PRD layout requirements
- `DocumentRepresentation` can be serialized to/from JSON (needed for Python → TypeScript handoff)

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP2: Section Renderers

**Files to Stage:**
- `src/rendering/sections.py`
- `tests/test_section_renderers.py`

**Commit Command:**
```bash
git add src/rendering/sections.py tests/test_section_renderers.py
git commit -m "feat(phase-002): section renderers — all 6 daily sections plus sending prompt and day 7"
```

**Verification:**
- `pytest tests/test_section_renderers.py -v` all pass
- `render_timeless_wisdom()` returns BLOCK_QUOTE + FOOTNOTE blocks
- `render_be_still()` returns HEADING "Still Before God" + PROMPT_LIST
- `render_action_steps()` returns HEADING "Walk It Out" + ACTION_LIST
- `render_sending_prompt()` returns DIVIDER + BODY_TEXT (no HEADING)
- `render_day7()` returns correct heading structure for both tracks

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP3: Front Matter and Static Templates

**Files to Stage:**
- `src/rendering/front_matter.py`
- `templates/introduction_sunday.md`
- `templates/offer_page.md`
- `tests/test_front_matter.py`

**Commit Command:**
```bash
git add src/rendering/front_matter.py templates/introduction_sunday.md templates/offer_page.md tests/test_front_matter.py
git commit -m "feat(phase-002): front matter renderers and static templates — title, copyright, introduction, toc, offer page"
```

**Verification:**
- `pytest tests/test_front_matter.py -v` all pass
- Copyright page contains "Sacred Whispers Publishers" and no personal author name
- TOC renders for 12-day book; does not render for 6-day book
- Introduction with Day 7 enabled includes Sunday Worship Integration text
- Offer page content contains `sacredwhisperspublishing.com`
- Operator must review and sign off on `templates/introduction_sunday.md` content (WCAG and theological accuracy)

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP4: Rendering Engine End-to-End

**Files to Stage:**
- `src/rendering/engine.py`
- `tests/fixtures/sample_devotional.py`
- `tests/test_rendering.py`

**Commit Command:**
```bash
git add src/rendering/engine.py tests/fixtures/sample_devotional.py tests/test_rendering.py
git commit -m "feat(phase-002): rendering engine — end-to-end document representation from mock devotional book"
```

**Verification:**
- `pytest tests/test_rendering.py -v` all pass (all rendering tests listed in Step 6)
- Engine produces `DocumentRepresentation` that is JSON-serializable
- Offer page is the final page in publish-ready mode
- Day 7 pages render correctly with equal weight for Track A and Track B
- Day 6 sending prompt appears within Day 6 page (not as new page)
- `python -c "from src.rendering.engine import DocumentRenderer; from tests.fixtures.sample_devotional import SAMPLE_BOOK; import json; r = DocumentRenderer(); doc = r.render(SAMPLE_BOOK, 'publish-ready'); print(json.dumps(doc.dict(), indent=2, default=str))"` — produces valid JSON output

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

## Acceptance Criteria

Phase 002 is complete when:

- [ ] `DocumentRepresentation` schema is JSON-serializable (Python → TypeScript handoff)
- [ ] All 6 daily section renderers produce correct `DocumentBlock` types with correct heading strings
- [ ] Sending prompt produces DIVIDER + BODY_TEXT with no section heading
- [ ] Day 7 renders both movements with Track A and Track B headings
- [ ] Front matter renderers produce: title page, copyright page (Sacred Whispers Publishers), introduction
- [ ] Sunday Worship Integration introduction section present when Day 7 enabled (FR-97)
- [ ] TOC renders for 12+ day books; absent for < 12 days (FR-89)
- [ ] Offer page renders as final page in publish-ready mode (FR-94)
- [ ] Page number style: ROMAN/SUPPRESSED for front matter; ARABIC for content
- [ ] `pytest tests/ -v` passes all rendering tests
- [ ] Both static templates (`introduction_sunday.md`, `offer_page.md`) operator-reviewed and finalized
- [ ] All commit points (CP1–CP4) executed and verified

---

## Rollback Notes

**Emergency rollback (all of Phase 002):**
```bash
git log --oneline  # Find last Phase 001 commit
git reset --soft <last-phase-001-commit-hash>
```

Phase 002 produces no database state. Rollback is clean — removes schema and rendering files, returns to Phase 001 state.

Phase 003 depends on `DocumentRepresentation` being stable. If the schema changes after Phase 003 begins, Phase 003 must be paused and updated.

---

## Verification Steps

1. `pytest tests/ -v --tb=short` → all tests pass
2. `mypy src/models/document.py src/rendering/` → no type errors
3. End-to-end render: `python -c "from src.rendering.engine import DocumentRenderer; from tests.fixtures.sample_devotional import SAMPLE_BOOK; doc = DocumentRenderer().render(SAMPLE_BOOK, 'publish-ready'); print(f'Pages: {len(doc.front_matter) + len(doc.content_pages)}')"` → prints page count
4. Offer page check: last content page contains offer page content
5. Manual review: read `templates/introduction_sunday.md` — operator confirms content is correct (150–250 words, explains Day 7, states convergence/divergence equal)

---

## Gatekeeper Checklist

- [ ] `DocumentRepresentation` is a complete, frozen contract — all rendering variation is expressed through block types and metadata, not through additional schema fields
- [ ] Reader-facing section headers are exactly as specified in PRD D016: "Timeless Wisdom", "Scripture Reading", "Reflection", "Still Before God", "Walk It Out", "Prayer"
- [ ] Sending prompt has no section header (per FR-95) — only DIVIDER then body text
- [ ] Day 7 Track A and Track B given equal structural weight (per FR-96, D056)
- [ ] Copyright page has no personal author name (PRD D010)
- [ ] Operator review of static templates is a required condition for phase completion
- [ ] All 4 commit points have files, command, verification, rollback

**Decision**: APPROVE / REVISE / REJECT

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-24 | Initial phase plan — Iteration 1 |
