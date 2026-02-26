# Phase 004 — Validation, Review UI & AC Scoring Harness

**Project**: devotional-generator-system-a
**Phase**: 004
**Version**: 1.0
**Date**: 2026-02-24
**Status**: Draft — Awaiting Gatekeeper approval

---

## Objective

Build and integrate the four sub-systems that complete the Devotional Generator: the AC Scoring Harness (competition-critical), the theological validators, the human review UI, and the full integration layer (real RAG, export gate, encryption). This phase wires all previous phases into a working end-to-end system.

**Why this phase is last:** The validators and scoring harness require the complete schema definitions from Phase 001. The human review UI requires the PDF engine from Phase 003. The integration requires mock RAG to be replaced with real RAG — which requires the Quote Catalog and Exposition RAG sources to be indexed (parallel work that must complete before this phase's final integration step).

**Sub-phase execution order (strict — do not reorder):**
1. **Sub-phase A: AC Scoring Harness** — competition-critical; must be built first within this phase
2. **Sub-phase B: Theological Validators** — FR-73–77; deterministic rule checks
3. **Sub-phase C: Human Review UI** — TypeScript React; approval workflow; Grounding Map display
4. **Sub-phase D: Integration** — real RAG, export gate, encryption, end-to-end test

**Why AC Scoring Harness is first:** The harness is the structural foundation of the competition. It cannot be deferred to "last thing before delivery." Building it first ensures that its isolation requirements are met before the generation layer is wired in — and that integration testing includes harness verification.

---

## Prerequisites

- Phase 001 complete: all schemas final
- Phase 002 complete: DocumentRepresentation schema frozen
- Phase 003 complete: PDF engine operational; Python-TypeScript integration working
- Quote Catalog indexed (parallel work — must be complete before Sub-phase D)
- Exposition RAG sources indexed (parallel work — must be complete before Sub-phase D)
- Shared test specification path confirmed with operator (see Assumption A-01 in prd.md)

---

## Inputs

- All Phase 001–003 artifacts
- PRD v16: TC-06, Section 18.5 (AC Scoring Harness)
- PRD v16: FR-73–FR-77 (theological validators)
- PRD v16: FR-78 (rewrite routing)
- PRD v16: FR-79–FR-83 (human review and approval)
- PRD v16: FR-79a (Exposition Reference Artifact in UI)
- PRD v16: AC-01–AC-43 (full acceptance criteria)
- PRD v16: Section 18.1 (unit tests for validators)
- PRD v16: Section 18.4 (theological smoke tests)
- PRD v16: NFR-05 (encryption)
- PRD v16: NFR-02 (snapshot/restore)

---

## Sub-phase A: AC Scoring Harness

### Objective

Build the deterministic, isolated scoring harness that evaluates devotional content against AC-01 through AC-43. This is the competition's measurement instrument. It must be model-independent, version-locked, hash-verified, and completely isolated from generation state.

### Outputs (Sub-phase A)

| File | Description |
|------|-------------|
| `scoring/harness.py` | AC Scoring Harness — single public entry point; loads external spec at runtime |
| `scoring/spec_loader.py` | Loads and validates a canonical spec from an operator-provided path |
| `scoring/ac_checks.py` | AC-01 through AC-43 deterministic check function registry (functions only; rules loaded from spec) |
| `scoring/models.py` | ScoredContent, ScoringResult, ScoredSpec schemas |
| `scoring/spec_verifier.py` | Hash verification of external spec before each run |
| `scoring/draft_spec/provisional-dev-spec.yaml` | Provisional development spec (NOT the canonical evaluation spec — see governance note below) |
| `tests/scoring/test_harness.py` | Harness infrastructure tests — loader, verifier, check dispatch |
| `tests/scoring/test_spec_integrity.py` | Hash integrity tests |

### The AC Scoring Harness — Architecture and Governance

**Gatekeeper clarification (2026-02-24, APPROVE decision):**

> "The canonical Acceptance Criteria scoring specification will NOT be designed by Builder.
> It will be authored later by: PRD Designer + Operator, before competition evaluation begins.
> Builder must implement a deterministic validation architecture (TC-06 compliant) that is
> capable of loading an external canonical spec at evaluation time."

This is the governing constraint for all of Sub-phase A.

**What the Builder DOES build:**

The harness **infrastructure** — a spec-loading, hash-verifying, deterministic scoring engine that can evaluate any conformant spec against any `ScoredContent` instance. The Builder does not decide what the canonical rules say.

**What the Builder does NOT build:**

The canonical evaluation spec. That is authored by the PRD Designer + Operator and provided to the harness at evaluation time. The Builder has no authority over the final spec content.

**Architectural consequence:**

The harness is a generic engine. Scoring rules are data (YAML), not code. The harness maps rule definitions from the loaded spec to the registered check functions in `ac_checks.py`, applies them to the content, and returns deterministic results. Adding new or revised rules requires only spec changes — not code changes — as long as the check type is registered.

**Provisional development spec:**

Builder will create `scoring/draft_spec/provisional-dev-spec.yaml` for build-time quality checking during Phases 001–004. This spec is:
- Clearly labeled `authority: provisional-development-only` in its header
- Not submitted as the canonical evaluation spec
- Not stored in `../competition-2026/outputs/`
- Useful for building and testing the harness infrastructure before the canonical spec exists

The canonical spec will be delivered by the operator and will be loaded from whatever path the operator specifies at evaluation time.

**Runtime loading protocol:**

```python
def score(content: ScoredContent, spec_path: str) -> ScoringResult:
    """
    spec_path: operator-provided path to the canonical spec at evaluation time.
               During development: path to provisional-dev-spec.yaml.
               At competition scoring: path to canonical spec from PRD Designer + Operator.
    """
    spec = load_and_verify_spec(spec_path)   # Hash-verified; raises on mismatch
    results = run_all_checks(content, spec)   # Deterministic; no LLM inference
    return ScoringResult(
        spec_version=spec.version,
        spec_hash=spec.computed_hash,
        scored_at=utcnow(),
        results=results,
    )
```

**Spec file format (harness expects — fixed contract):**

```yaml
spec_version: "1.0.0"           # Semantic version; authority: provisional-development-only OR canonical
spec_date: "2026-02-24"
authority: "provisional-development-only"  # OR "canonical" when set by PRD Designer + Operator
source_document: "PRD_v16.md"
acceptance_criteria:
  AC-01:
    description: "..."
    check_type: "structural"    # Must match a registered check type in ac_checks.py
    required_elements: [...]
    failure_reason_code: "AC01_STRUCTURE_VIOLATION"
  AC-10:
    description: "..."
    check_type: "word_count"
    min_words: 500
    max_words: 700
    failure_reason_code: "AC10_WORD_COUNT_VIOLATION"
  # ... through AC-43
```

The spec format is the contract between the harness and the spec author. It must be documented clearly so the PRD Designer can author the canonical spec without needing to modify code.

### AC Check Implementation Categories

AC checks are categorized by check type. No check may use LLM inference:

| Check Type | Description | Examples |
|-----------|-------------|---------|
| `word_count` | Count words in text field; check bounds | AC-10 (exposition 500–700w), AC-31 (prayer 120–200w) |
| `structural` | Check presence of required paragraph roles or sections | AC-01 (4-paragraph structure), AC-12 (3–5 Be Still prompts) |
| `pronoun_check` | Scan text for prohibited pronouns (e.g., "you/your" in exposition) | AC-09 (communal voice) |
| `artifact_completeness` | Check Grounding Map / Prayer Trace Map present and non-empty | AC-19 (Grounding Map), AC-27 (Prayer Trace Map) |
| `field_presence` | Check required field is non-empty | AC-21 (prayer addressed to named Trinity person) |
| `keyword_check` | Check for presence/absence of required phrases or patterns | AC-18 (connector phrase in Action Steps) |
| `count_range` | Check list length within bounds | AC-12 (3–5 prompts), AC-19 (1–3 Action Steps) |
| `approval_status` | Check section approval_status == "approved" | AC-37 |
| `flag_from_validator` | Pass/fail mirrors FR-74–77 structured reason code result | AC-33 |

**AC checks for complex behavioral requirements (AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-11, AC-13–AC-17, AC-20a, AC-20b, AC-22–AC-26, AC-28–AC-30, AC-32):** These ACs require judgment about content quality that cannot be fully reduced to deterministic text checks without LLM inference. TC-06 prohibits LLM inference in validators.

**Resolution for complex ACs:** The harness scores these ACs by requiring them to carry an explicit `validator_assessment` field set by the FR-74–77 validators during generation. The validators assess these criteria at generation time (where they *are* allowed to use LLM inference as a heuristic, but they produce a deterministic pass/fail result with a reason code). The harness checks that: (a) the `validator_assessment` field is present, (b) the assessment result is "pass", (c) the reason_code is one of the defined valid codes. This preserves determinism in the harness while allowing the generation-time validators to use model output as evidence.

**This distinction is critical:** The generation-time validators (FR-74–77) may use model output to inform their judgment. The harness (TC-06) only checks the deterministic result of that judgment — it does not re-run model inference.

### Harness Public Interface

```python
# scoring/harness.py

@dataclass
class ScoredContent:
    """
    Content object passed to the harness.
    Contains only content fields — no generation state, no RAG context, no session info.
    """
    exposition_text: str
    exposition_word_count: int
    exposition_grounding_map: Optional[GroundingMap]
    exposition_validator_assessments: Dict[str, ValidatorAssessment]  # AC ID → assessment
    be_still_prompts: List[str]
    action_steps_items: List[str]
    action_steps_connector_phrase: str
    prayer_text: str
    prayer_word_count: int
    prayer_trace_map: Optional[PrayerTraceMap]
    prayer_validator_assessments: Dict[str, ValidatorAssessment]
    quote_public_domain: bool
    quote_verification_status: str
    quote_turabian_attribution: Optional[str]
    scripture_validated: bool
    all_sections_approved: bool     # True if all approval_status == "approved"
    day7_enabled: bool
    day6_sending_prompt_word_count: Optional[int]
    day7_after_service_word_count: Optional[int]
    day7_approved: Optional[bool]

@dataclass
class ACResult:
    ac_id: str           # e.g. "AC-01"
    status: str          # "pass" | "fail"
    reason_code: str     # e.g. "AC01_STRUCTURE_VIOLATION" (empty string on pass)
    explanation: str     # Plain-language explanation (empty on pass)

@dataclass
class ScoringResult:
    scored_at: str               # ISO 8601 timestamp
    spec_version: str            # e.g. "1.0.0"
    spec_hash: str               # SHA-256 of test spec file at scoring time
    authority: str               # spec authority identifier/source
    total_acs: int               # 43
    passed: int
    failed: int
    results: List[ACResult]      # One per AC-01 through AC-43
    overall_pass: bool           # True only if all 43 ACs pass

def score(content: ScoredContent, spec_path: str) -> ScoringResult:
    """
    Public entry point for the AC Scoring Harness.
    1. Load and hash-verify spec_path
    2. Run all AC checks deterministically
    3. Return ScoringResult with all 43 results + metadata
    Raises SpecIntegrityError if hash does not match stored hash.
    """
```

---

## Sub-phase B: Theological Validators

### Objective

Implement the FR-73–77 validators as deterministic rule checks. These validators run at generation time (after each section is generated) and produce structured `ValidatorAssessment` results that feed into the AC Scoring Harness.

### Outputs (Sub-phase B)

| File | Description |
|------|-------------|
| `src/validation/orchestrator.py` | FR-73 validation pass orchestrator |
| `src/validation/exposition.py` | FR-74 exposition validator |
| `src/validation/be_still.py` | FR-75 Be Still validator |
| `src/validation/action_steps.py` | FR-76 Action Steps validator |
| `src/validation/prayer.py` | FR-77 prayer validator |
| `src/validation/doctrinal.py` | Section 10.1/10.2 doctrinal guardrail engine |
| `src/validation/modernization.py` | FR-56 archaic language modernization function |
| `src/validation/rewrite_router.py` | FR-78 rewrite routing logic |
| `tests/validation/test_exposition_validator.py` | |
| `tests/validation/test_prayer_validator.py` | |
| `tests/validation/test_be_still_validator.py` | |
| `tests/validation/test_action_steps_validator.py` | |
| `tests/validation/test_doctrinal.py` | |
| `tests/validation/test_modernization.py` | |
| `tests/validation/smoke_tests.py` | Section 18.4 theological smoke tests |

### ValidatorAssessment Schema

```python
class ValidatorAssessment(BaseModel):
    ac_id: str                  # Which AC this assessment covers
    result: str                 # "pass" | "fail"
    reason_code: str            # Empty on pass; specific code on fail
    explanation: str            # Plain-language explanation
    evidence: Optional[str]     # Specific text evidence for the assessment
```

### FR-74 Exposition Validator (key checks)

All deterministic checks (no LLM inference):
- **Word count**: count words; fail if < 500 or > 700 (AC-10)
- **Voice check**: scan for "you" / "your" as subject; fail if present (AC-09)
- **Grounding Map completeness**: check exactly 4 entries, all non-empty (AC-19 proxy check)
- **Paragraph structure**: check exposition splits into 4 paragraphs with correct roles (may use structural heuristic based on paragraph count and length)

LLM-inference-informed checks (heuristic; produce deterministic pass/fail result):
- **Opening declaration** (AC-02): does paragraph 1 state one controlling idea as a declarative theological claim?
- **Context paragraph** (AC-03): does paragraph 2 identify literary and theological purpose?
- **Theological sequence** (AC-04): does paragraph 3 follow definition → close reading → cross-reference → character of God → summary?
- **Doctrinal support** (AC-05): are theological claims supported by the passage?
- **Cultural tension** (AC-06): does paragraph 4 open by naming a contemporary tension?
- **Christ-grounded** (AC-07): is application grounded in Christ's work or God's character?
- **Felt need** (AC-08): does paragraph 4 close by creating felt need rather than resolving tension?
- **Genre** (AC-11): does the passage's literary genre govern how it is handled?

### Archaic Language Modernization (FR-56)

**`src/validation/modernization.py`**

Applies before any retrieved text is used in generation (not after). Transformations:

```python
ARCHAIC_PRONOUNS = {
    r'\bthee\b': 'you',
    r'\bthou\b': 'you',
    r'\bthy\b': 'your',
    r'\bthine\b': 'yours',
    r'\bye\b': 'you',  # plural
}

ARCHAIC_VERBS = {
    r'\bhath\b': 'has',
    r'\bdoth\b': 'does',
    r'\bcometh\b': 'comes',
    r'\bsaith\b': 'says',
    r'\bsaieth\b': 'says',
    # ... complete list per FR-56
}

SHIFTED_MEANING_TERMS = {
    # Only replace when used in archaic sense (context-sensitive)
    r'\bcharity\b': 'love',       # When meaning "love" not "charitable giving"
    r'\bconversation\b': 'conduct',  # When meaning "way of life"
    r'\bprevent\b': 'precede',    # When meaning "go before"
}

# CRITICAL: Do NOT change modality
# "shall not" → NOT "may not"
# "will not" → NOT "might not"
# Test for this explicitly
```

Test cases (per PRD Section 18.1):
- Each pronoun substitution category tested
- Each verb substitution category tested
- Each shifted-meaning term tested
- Negation/modality preservation: "shall not" must remain "shall not"
- Conditional construction preservation: "if thou canst" → "if you can" (modal preserved)

### FR-78 Rewrite Routing

```python
class RewriteRouter:
    def handle_validation_failure(
        self,
        section_type: str,
        content: str,
        failures: List[ValidatorAssessment],
        attempt_number: int,
    ) -> RewriteDecision:
        """
        attempt_number == 1: trigger automatic rewrite
        attempt_number == 2: route to human review queue; no further auto-rewrite
        Returns: RewriteDecision(action="rewrite"|"human_review", failures=failures)
        """
```

---

## Sub-phase C: Human Review UI

### Objective

Build the local TypeScript/React web UI for human review, editing, and approval of all generated content. WCAG AA compliance required.

### Outputs (Sub-phase C)

| File | Description |
|------|-------------|
| `ui/src/App.tsx` | Root application component |
| `ui/src/pages/ReviewPage.tsx` | Main review page for a devotional book |
| `ui/src/components/DayCard.tsx` | Per-day review card with all sections |
| `ui/src/components/SectionEditor.tsx` | Editable section with approval control |
| `ui/src/components/GroundingMapPanel.tsx` | Grounding Map + retrieved excerpts display (FR-79a) |
| `ui/src/components/SnapshotManager.tsx` | Snapshot/restore UI (3 states per section) |
| `ui/src/components/DiversityReport.tsx` | Author diversity report display |
| `ui/src/components/AlertPanel.tsx` | Quote shortage and scripture shortage alerts |
| `ui/src/api/client.ts` | TypeScript API client for Python FastAPI |
| `ui/src/__tests__/` | Vitest unit tests; Playwright E2E tests |

### Review UI Requirements

**Per-section editing (FR-83):**
Each section is independently editable. Edits are saved on blur or explicit save action. Local change tracking shows original vs. edited state.

**Approval workflow (FR-80, FR-81):**
- Each section shows approval_status (PENDING / APPROVED)
- Approve button per section; approve-all-day shortcut
- In publish-ready mode: export is blocked until all sections APPROVED
- In personal mode: warning displayed for any PENDING sections but export allowed

**Grounding Map display (FR-79a):**
When exposition is open for review:
- Side panel shows Grounding Map with 4 entries
- Each entry: paragraph name, sources retrieved, excerpts used, how retrieval informed paragraph
- Operator can use this to evaluate theological fidelity

**Snapshot/restore (NFR-02):**
- On approval or manual edit: save current state as snapshot
- Show 3 most recent snapshots per section
- Restore button reverts to selected snapshot

**Day 7 review:**
- Before the Service and After the Service sections both editable
- Track A and Track B displayed with equal visual weight

**Quote shortage alert:**
- When fewer than 3 candidates returned: display structured alert
- Show available candidates (even if < 3)
- Allow operator selection or manual entry
- Manual entry requires Turabian attribution fields

**Scripture shortage alert:**
- When retrieval fails: display passage name and failure mode
- Empty field for operator manual entry
- Export blocked for that day until entry provided

**WCAG AA compliance (NFR-04):**
- All interactive elements keyboard accessible
- Sufficient color contrast (4.5:1 minimum for normal text)
- Screen reader labels on all form controls
- Focus management on modal dialogs

---

## Sub-phase D: Integration

### Objective

Replace mock RAG with real RAG implementations. Wire all layers into a complete end-to-end system. Implement encryption at rest. Validate the complete pipeline from topic input through PDF export.

### Outputs (Sub-phase D)

| File | Description |
|------|-------------|
| `src/rag/quote_catalog.py` | Real Quote Catalog: ChromaDB-backed, indexed from approved sources |
| `src/rag/exposition_rag.py` | Real Exposition RAG: 10 approved sources, agentic retrieval |
| `src/rag/setup.py` | Setup script: indexes Quote Catalog and Exposition RAG sources |
| `src/security/encryption.py` | At-rest encryption: OS keychain + passphrase fallback |
| `src/api/export_gate.py` | Approval status check; export authorization |
| `src/api/generation_pipeline.py` | End-to-end orchestrator: input → generation → validation → storage |
| `tests/integration/test_end_to_end.py` | End-to-end integration test |
| `tests/integration/test_rag_pipeline.py` | RAG integration tests (FR-52, FR-57–59) |

### Real RAG Implementation

**Quote Catalog (TC-02):**
- ChromaDB collection: `quote_catalog`
- Each document: `{text, author, source, url, year, public_domain: true}`
- Metadata filters: `date_range_filter(1483, 1952)`, `public_domain == true`
- Retrieval: `retrieve_quotes(topic, scripture_reference, author_weights, top_k=10)`
- Shortage: if < 3 candidates returned from cache → live retrieval from approved sites → shortage alert if still < 3

**Exposition RAG (TC-03):**
- ChromaDB collection: `exposition_rag`
- Separate collections or namespaces per source type (commentary vs. reference)
- Agentic orchestration:
  1. Plan retrieval: which sources and passage references to query
  2. Execute: query commentary sources for paragraph 2 (context); query for paragraph 3 (theological)
  3. Query reference works for historical context (paragraph 2)
  4. Retrieve and deduplicate results
  5. Generate exposition paragraphs in order
  6. Produce Grounding Map alongside each paragraph
  7. Run FR-74 validator; iterate if fails (one auto-rewrite)

**Setup script (`src/rag/setup.py`):**
- Crawls or downloads approved exposition RAG source texts (Matthew Henry, Pulpit Commentary, JFB, John Gill, Adam Clarke, ISBE, Easton's, Smith's, Strong's Hebrew, Strong's Greek)
- Indexes into ChromaDB with chunking strategy
- Indexes Quote Catalog from approved author whitelist sources
- Reports indexing progress and any source failures
- One-time setup; must complete before first use of Phase 004 Sub-phase D

### Encryption at Rest (NFR-05)

**Encrypted files:**
- Series Registry SQLite file
- Workspace directory (generated content drafts)
- Quote Catalog index (ChromaDB data directory)
- Operator-provided import files

**Not encrypted:**
- Exported PDFs (KDP deliverable)
- In-memory content during active session

**Implementation (`src/security/encryption.py`):**
- Primary: OS keychain (macOS Keychain Services) manages AES-256 key
- Fallback: operator-provided passphrase derives key via PBKDF2
- File-level encryption: encrypt on write, decrypt on read
- ChromaDB directory: encrypted at rest using file-system-level encryption or per-file encryption of the SQLite backing store

### End-to-End Export Gate

```python
class ExportGate:
    def check_exportability(
        self,
        book: DevotionalBook,
        output_mode: OutputMode,
    ) -> ExportabilityResult:
        """
        publish-ready mode:
          - All sections of all days must have approval_status = APPROVED
          - All quotes must have verification_status = human_approved or catalog_verified
          - All quotes must have public_domain = True
          - Scripture must be validated for all days
          Returns: ExportabilityResult(allowed=False, blocking_items=[...]) if any fail

        personal mode:
          - Returns warnings for any PENDING sections
          - Does not block export
          Returns: ExportabilityResult(allowed=True, warnings=[...])
        """
```

---

## Commit Points

### CP1: AC Scoring Harness

**Files to Stage:**
- `scoring/spec_loader.py`
- `scoring/models.py`
- `scoring/spec_verifier.py`
- `scoring/ac_checks.py`
- `scoring/harness.py`
- `tests/scoring/test_harness.py`
- `tests/scoring/test_spec_integrity.py`

**Commit Command:**
```bash
git add scoring/ tests/scoring/
git commit -m "feat(phase-004): ac scoring harness infrastructure — spec loader, hash verifier, check dispatch, provisional dev spec"
```

**Verification:**
- `scoring/draft_spec/provisional-dev-spec.yaml` exists; header contains `authority: provisional-development-only`
- `scoring/harness.py` loads provisional spec without errors
- `pytest tests/scoring/ -v` all pass
- Every registered check type (`word_count`, `structural`, `pronoun_check`, etc.) has at least one passing test case and one failing test case using provisional spec
- Hash verification: modify `provisional-dev-spec.yaml`, re-run harness → `SpecIntegrityError` raised; restore → scoring succeeds
- `ScoringResult` JSON contains `spec_version`, `spec_hash`, `authority`, `scored_at` fields
- `score()` function has zero imports from any generation module
- `spec_loader.py` accepts any file path — confirms harness is spec-agnostic (will accept canonical spec when delivered)

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP2: Theological Validators and Modernization

**Files to Stage:**
- `src/validation/orchestrator.py`
- `src/validation/exposition.py`
- `src/validation/be_still.py`
- `src/validation/action_steps.py`
- `src/validation/prayer.py`
- `src/validation/doctrinal.py`
- `src/validation/modernization.py`
- `src/validation/rewrite_router.py`
- `tests/validation/`

**Commit Command:**
```bash
git add src/validation/ tests/validation/
git commit -m "feat(phase-004): theological validators — fr-73 through fr-77, doctrinal guardrails, archaic modernization, rewrite routing"
```

**Verification:**
- `pytest tests/validation/ -v` all pass
- Exposition validator: word count 499 fails; 500 passes; 700 passes; 701 fails
- Prayer validator: word count 119 fails; 120 passes; 200 passes; 201 fails
- Grounding Map missing entry: exposition validator returns `AC19_GROUNDING_MAP_INCOMPLETE` code
- Prayer Trace Map untraceable element: prayer validator returns `AC27_UNTRACEABLE_ELEMENT` code
- Modernization: "thee" → "you"; "hath" → "has"; "shall not" → "shall not" (NOT "may not")
- Smoke test: prosperity gospel framing input → doctrinal validator flags
- Smoke test: works-based merit input → doctrinal validator flags

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP3: Human Review UI

**Files to Stage:**
- `ui/src/` (all UI source files)
- `ui/src/__tests__/`

**Commit Command:**
```bash
git add ui/src/
git commit -m "feat(phase-004): human review ui — section editing, approval workflow, grounding map display, snapshots"
```

**Verification:**
- `cd ui && pnpm test` all Vitest tests pass
- UI loads on localhost without errors
- All 6 daily sections visible and editable
- Approval button changes section status from PENDING to APPROVED
- Export blocked in publish-ready mode when any section PENDING
- Grounding Map panel appears alongside exposition with correct entries
- Snapshot list shows up to 3 saved states per section; restore reverts content
- WCAG AA: run `axe` or `lighthouse` accessibility audit; no AA violations

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP4: Real RAG Integration

**Files to Stage:**
- `src/rag/quote_catalog.py`
- `src/rag/exposition_rag.py`
- `src/rag/setup.py`
- `tests/integration/test_rag_pipeline.py`

**Commit Command:**
```bash
git add src/rag/ tests/integration/test_rag_pipeline.py
git commit -m "feat(phase-004): real rag integration — quote catalog and exposition rag from approved sources"
```

**Verification:**
- Setup script runs and indexes without errors (for at least one approved source — full index may take time)
- `QuoteCatalog.retrieve_quotes("grace", "Romans 5:8")` returns ≥1 candidate
- Shortage protocol: mock thin results → structured shortage alert produced
- Exposition RAG: `retrieve_for_paragraph("context", "Romans 8:15", "adoption")` returns at least one excerpt
- Agentic retrieval: agent produces Grounding Map with 4 non-empty entries

**Rollback:**
```bash
git reset --soft HEAD~1
# Note: RAG index (ChromaDB data) is separate from git; roll back index by re-running setup.py
```

---

### CP5: Encryption at Rest

**Files to Stage:**
- `src/security/encryption.py`
- `tests/security/test_encryption.py`

**Commit Command:**
```bash
git add src/security/encryption.py tests/security/test_encryption.py
git commit -m "feat(phase-004): encryption at rest — os keychain key management, workspace and registry encrypted"
```

**Verification:**
- Registry file is not readable as plain text after encryption applied
- Decrypt and read: returns original content
- OS keychain integration: key stored and retrieved from macOS Keychain
- Passphrase fallback: with keychain unavailable (mocked), passphrase correctly derives decryption key
- Exported PDFs: not encrypted (open in Preview without passphrase)

**Rollback:**
```bash
git reset --soft HEAD~1
# Note: if encryption was applied to existing data, must decrypt before rollback
# Use: python -c "from src.security.encryption import decrypt_workspace; decrypt_workspace()"
```

---

### CP6: Export Gate and Generation Pipeline

**Files to Stage:**
- `src/api/export_gate.py`
- `src/api/generation_pipeline.py`
- `tests/integration/test_end_to_end.py`

**Commit Command:**
```bash
git add src/api/export_gate.py src/api/generation_pipeline.py tests/integration/test_end_to_end.py
git commit -m "feat(phase-004): generation pipeline and export gate — end-to-end topic to pdf"
```

**Verification:**
- `pytest tests/integration/test_end_to_end.py -v` passes
- End-to-end: `generate_devotional(input=DevotionalInput(topic="grace", num_days=1))` → produces DailyDevotional with all 6 sections
- Export gate: PENDING section → `ExportabilityResult(allowed=False)` in publish-ready mode
- Export gate: all APPROVED → `ExportabilityResult(allowed=True)`
- Full export: approve all sections → generate PDF → compliance check passes
- AC Scoring Harness: score the generated devotional → receives ScoringResult with all 43 ACs evaluated
- Registry: after export, backup created at configured path

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP7: Theological Smoke Tests

**Files to Stage:**
- `tests/validation/smoke_tests.py` (finalized, operator-approved)

**Commit Command:**
```bash
git add tests/validation/smoke_tests.py
git commit -m "test(phase-004): theological smoke tests — operator-approved known-bad inputs for doctrinal guardrail validation"
```

**Verification:**
- Operator has reviewed all smoke test inputs and confirmed they correctly trigger guardrails
- All smoke tests pass (each known-bad input triggers expected validator flag)
- Smoke tests: prosperity gospel → flag; works-based merit → flag; prayer untraceable element → flag; fatalistic action steps → flag

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

### CP8 (Final): End-to-End System Test — Volume 1 Generation

**Files to Stage:**
- `tests/system/test_volume_1.py`
- Any fixes identified during full system test

**Commit Command:**
```bash
git add tests/system/test_volume_1.py
git commit -m "test(phase-004): full system test — volume 1 generation, all validators, scoring harness, pdf export"
```

**Verification:**
- Generate full 6-day devotional (all sections, with real RAG)
- All FR-74–77 validators pass for generated content
- AC Scoring Harness scores all 43 ACs; all pass
- PDF export generates KDP-compliant PDF; compliance check passes
- Registry updated with quotes and scriptures used
- Backup created
- Review UI shows all sections; operator can approve and export

**Rollback:**
```bash
git reset --soft HEAD~1
```

---

## Acceptance Criteria

Phase 004 is complete when:

### Sub-phase A — AC Scoring Harness
- [ ] Harness accepts any operator-provided spec path (spec-agnostic infrastructure)
- [ ] `scoring/spec_loader.py` loads and validates spec format from any path
- [ ] Provisional dev spec (`scoring/draft_spec/provisional-dev-spec.yaml`) exists with `authority: provisional-development-only` header
- [ ] Provisional spec is NOT stored in `../competition-2026/outputs/` (not a competition artifact)
- [ ] SHA-256 hash verification runs before every scoring run; modified spec → `SpecIntegrityError`
- [ ] All registered check types produce deterministic pass/fail with reason codes
- [ ] Every check type has at least one passing and one failing test case (using provisional spec)
- [ ] `ScoringResult` contains `spec_version`, `spec_hash`, `authority`, `scored_at`
- [ ] Harness module has zero imports from generation modules (verified)
- [ ] Harness scores content without knowledge of retrieval context or session state
- [ ] Spec format contract documented (so PRD Designer can author canonical spec without code changes)

### Sub-phase B — Validators
- [ ] FR-74–77 validators return structured `ValidatorAssessment` for all criteria
- [ ] Word count boundaries correct for exposition (500/700) and prayer (120/200)
- [ ] Grounding Map completeness check functional
- [ ] Prayer Trace Map completeness check functional
- [ ] Archaic modernization: all specified substitutions applied correctly
- [ ] Negation/modality preserved: "shall not" not changed to "may not"
- [ ] Doctrinal guardrails flag all Section 18.4 smoke test inputs
- [ ] Rewrite routing: one auto-rewrite then human review queue

### Sub-phase C — Review UI
- [ ] All 6 sections visible, editable, with individual approval controls
- [ ] Grounding Map displayed alongside exposition in review (FR-79a)
- [ ] Snapshot/restore: 3 states per section per day
- [ ] Export gate enforced in UI (publish-ready blocks on any PENDING)
- [ ] WCAG AA: no accessibility violations on `axe`/`lighthouse` audit
- [ ] Day 7 sections (when enabled) reviewable with equal weight for Track A/Track B

### Sub-phase D — Integration
- [ ] Real Quote Catalog retrieval returns candidates for test topic
- [ ] Real Exposition RAG retrieval returns excerpts from approved sources
- [ ] Shortage protocol triggers correctly (< 3 candidates → alert)
- [ ] Encryption at rest: workspace and registry encrypted; exported PDFs not encrypted
- [ ] Export gate: publish-ready blocks on PENDING sections; personal mode warns only
- [ ] End-to-end test passes: topic → generate → validate → approve → export PDF → compliance check passes → AC scoring harness scores all 43

---

## Rollback Notes

**Sub-phase A rollback:** `git reset --soft` to pre-CP1 commit. Scoring harness removed; no competition scoring possible until rebuilt.

**Sub-phase D rollback (encryption):** If encryption is applied to existing data before rollback, decryption must be run first:
```python
from src.security.encryption import decrypt_workspace
decrypt_workspace()
```
Then: `git reset --soft HEAD~1`

**Emergency rollback (all of Phase 004):**
```bash
git log --oneline  # Find last Phase 003 commit
git reset --soft <last-phase-003-commit-hash>
# Optionally: decrypt any encrypted workspace files before rollback
```

Returns to: PDF engine working, no validators, no UI, no real RAG, no encryption.

---

## Verification Steps (Phase Complete)

1. `pytest tests/ -v` → all tests pass (all phases)
2. `cd ui && pnpm test` → all TypeScript tests pass
3. Smoke tests: `pytest tests/validation/smoke_tests.py -v` → all pass
4. Spec integrity: modify `scoring/draft_spec/provisional-dev-spec.yaml` → `pytest tests/scoring/test_spec_integrity.py` → `SpecIntegrityError` raised
5. End-to-end: run `tests/system/test_volume_1.py` → all assertions pass
6. WCAG: run `axe` or `lighthouse` on review UI → no AA violations
7. KDP compliance: generate PDF → `compliance_check.passes == True`

---

## Gatekeeper Checklist

- [ ] AC Scoring Harness described as first within Phase 004 (not deferred)
- [ ] AC checks categorized correctly — no check type violates TC-06 (no LLM inference for pass/fail determination)
- [ ] Resolution for complex behavioral ACs is sound (validator_assessment field approach preserves TC-06 compliance)
- [ ] Harness isolation is enforced by structure (zero imports from generation modules)
- [ ] Shared test spec path assumption (A-01) is flagged as requiring operator confirmation
- [ ] Archaic modernization includes negation/modality preservation tests (PRD Section 18.1 requirement)
- [ ] Theological smoke tests require operator approval before commit
- [ ] Encryption rollback procedure is documented
- [ ] All 8 commit points have files, command, verification, rollback

**Decision**: APPROVE / REVISE / REJECT

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-24 | Initial phase plan — Iteration 1 |
