# Constitution — Devotional Generator System A

**Document Type**: Technical Boundary Definition (TC-04 Required)
**Version**: 1.3
**Date**: 2026-02-24
**Status**: APPROVED — Operator approval received 2026-02-24; Phase 003 decisions appended 2026-02-24

> **TC-04 Requirement**: Python and TypeScript responsibilities must be clearly
> separated in the architecture. The boundary between the two languages must be
> documented in `constitution.md` before Phase 001 begins.
>
> This document satisfies TC-04.
>
> **OPERATOR APPROVED 2026-02-24**: "The Python/TypeScript boundary is clear,
> responsibility-complete, and satisfies TC-04. The AC Scoring Harness isolation
> remains consistent with TC-06 deterministic requirements. Phase 001 may begin.
> No boundary revisions required at this time."

---

## 1. Governing Principle

The Devotional Generator is built in Python and TypeScript only (TC-01). These languages serve distinct, non-overlapping responsibilities. Code must not cross this boundary without an explicit interface contract. The boundary is defined by function, not by preference.

**Python governs:** all AI/LLM interaction, all retrieval and generation, all deterministic validation and scoring, and all persistent data management.

**TypeScript governs:** the local user interface, PDF document generation, and all presentation/rendering logic.

The interface between the two is a REST API (Python FastAPI → TypeScript frontend) for runtime communication and a shared JSON schema layer for data contracts.

---

## 2. Python Responsibilities

### 2.1 Core Generation Layer

| Responsibility | Notes |
|---------------|-------|
| LLM calls (all AI model interactions) | Provider-agnostic; no vendor hardcoded in contract layer |
| Exposition generation agent (TC-03) | Agentic RAG: plan → retrieve → reason → generate → validate → iterate |
| Grounding Map generation | Produced alongside every exposition; 4 entries, one per paragraph |
| Prayer Trace Map generation | Produced alongside every prayer; one entry per prayer element |
| Be Still section generation | 3–5 prompts, second-person, inward-to-outward |
| Action Steps generation | 1–3 items, active expectation framing |
| Prayer generation | 120–200 words, Trinity-addressed, pray-the-word |
| Quote selection and RAG | Semantic retrieval from Quote Catalog; no AI recall |
| Archaic language modernization (FR-56) | Applied to all retrieved text before use |
| Generation pipeline orchestrator | Coordinates all section generation for a devotional unit |

### 2.2 Retrieval Layer

| Responsibility | Notes |
|---------------|-------|
| Quote Catalog indexing and retrieval (TC-02) | Local semantic retrieval index; live fallback on cache miss |
| Exposition RAG source indexing (TC-03) | 10 approved sources (FR-17); passage reference + topic queries |
| Scripture retrieval (FR-57–FR-59) | Bolls.life primary → API.Bible secondary → operator import |
| Bolls.life book ID mapping table | Built and stored locally at setup |
| NASB full-translation local cache | Optional offline cache (Appendix A.8) |

### 2.3 Validation Layer (Deterministic)

| Responsibility | Notes |
|---------------|-------|
| Theological validation orchestrator (FR-73) | Runs after generation; triggers rewrite routing |
| Exposition validator (FR-74) | Structure, voice, word count, Grounding Map completeness |
| Be Still validator (FR-75) | Prompt count, sequence, second person |
| Action Steps validator (FR-76) | Connector phrase, item count, active expectation |
| Prayer validator (FR-77) | Address, word count, Prayer Trace Map completeness, untraceable elements |
| Doctrinal guardrail engine | Section 10.1/10.2 enforcement |
| Rewrite routing logic (FR-78) | One auto-rewrite → human review queue on second failure |

### 2.4 AC Scoring Harness (TC-06 — Isolated Layer)

| Responsibility | Notes |
|---------------|-------|
| Spec loader | Loads any operator-provided YAML spec from a given path |
| Spec hash verification | spec_hash = SHA256(spec file contents); verified before each scoring run |
| Check function registry | Deterministic check functions mapped to spec-defined check types; no LLM inference |
| Validator version recording | spec_version, spec_hash, authority field recorded in every scoring output |
| Isolation guarantee | Receives content as input only; no generation state accessible |
| Comparison output generation | Structured output; spec-agnostic format accommodates any conformant spec |

**Harness governance (Gatekeeper clarification 2026-02-24):**

The Builder implements the harness **infrastructure** only. The canonical evaluation spec is **not authored by the Builder**. It will be authored by the PRD Designer + Operator before competition evaluation begins.

Operational boundary:
- **Builder's scope**: spec loader, hash verifier, check function registry, deterministic scoring engine, `ScoredContent`/`ScoringResult` schemas, provisional development spec (labeled `authority: provisional-development-only`)
- **PRD Designer + Operator scope**: canonical evaluation spec content; authoritative `failure_reason_code` definitions; final `check_type` assignments per AC
- **At evaluation time**: operator provides path to canonical spec; harness loads, verifies, and scores

Builder must NOT treat its provisional dev spec as the competition scoring authority.

**Provisional development spec:**

`scoring/draft_spec/provisional-dev-spec.yaml` — used for build-time quality checking only. Must carry `authority: provisional-development-only` in its header. Must NOT be stored in `../competition-2026/outputs/`.

**Critical isolation rule:** The AC Scoring Harness module must have no import of, reference to, or dependency on any generation module, retrieval module, or LLM client. It receives content objects via its public API only.

### 2.5 Data and Persistence Layer

| Responsibility | Notes |
|---------------|-------|
| Series Registry (TC-05) | Persistent; survives restarts; backed up on volume export |
| De-duplication registry (FR-64–FR-72) | Within-volume and cross-volume; author distribution |
| Parent-child series inheritance (FR-70–FR-72) | Author distribution from parent to child |
| Workspace encryption at rest (NFR-05) | OS keychain key management; passphrase fallback |
| Version snapshot storage (NFR-02) | 3 states per section per day |
| Approval status persistence (FR-80) | Per section per day |

### 2.6 REST API (Python FastAPI)

| Responsibility | Notes |
|---------------|-------|
| Serve TypeScript frontend on localhost | Single-user; no network exposure |
| Expose generation endpoints | Trigger devotional generation |
| Expose validation endpoints | Return structured validation results |
| Expose registry endpoints | Quote shortage alerts, diversity report |
| Expose approval state endpoints | Read/write approval status |
| Expose snapshot endpoints | Save/restore section snapshots |
| Expose export gate endpoint | Returns exportability status per day |

---

## 3. TypeScript Responsibilities

### 3.1 Human Review UI

| Responsibility | Notes |
|---------------|-------|
| Local web application (React on localhost) | WCAG AA compliance (NFR-04) |
| Display all generated sections per day | Timeless Wisdom, Scripture, Reflection, Still Before God, Walk It Out, Prayer |
| Section editing | Local change tracking (FR-83) |
| Approval workflow | Per-section approve/pending controls (FR-80) |
| Grounding Map display (FR-79a) | Show retrieved sources and excerpts alongside exposition |
| Day 6 sending prompt review | When Day 7 enabled |
| Day 7 review | Before the Service / After the Service / Track A / Track B |
| Author diversity report display (FR-68) | Operator review before export |
| Quote shortage alert display (FR-52) | Operator manual substitution path |
| Scripture shortage alert display (FR-59) | Operator manual entry path |
| Snapshot/restore UI | 3 states per section per day |
| Export trigger | Calls Python API export gate; enforces approval gate |

### 3.2 PDF Export Layer

| Responsibility | Notes |
|---------------|-------|
| PDF document generation | Takes structured document representation from Python API |
| Open-source font bundling and embedding (FR-86) | Serif body + heading font |
| Trim size: 6x9 inches (FR-84) | |
| Margin calculation by page count (FR-85) | Must recalculate if page count crosses bracket boundary |
| Block quote rendering (FR-61–FR-62) | Quote and Scripture |
| Turabian footnote rendering (FR-63) | Author + title + year + page/URL at page bottom |
| Front matter rendering | Title page, copyright page (Sacred Whispers Publishers), introduction |
| Day 7 and sending prompt rendering | When enabled |
| Conditional TOC (FR-89) | 12+ days |
| Offer page rendering (FR-94) | sacredwhisperspublishing.com; final page |
| Page numbering (FR-92) | Roman/suppressed for front matter; Arabic for content |
| Each day on new page (FR-91) | |
| KDP compliance check output | Reports margin, trim size, page count, font embedding |

---

## 4. Interface Contracts

### 4.1 Python → TypeScript API

The Python FastAPI server is the single source of truth for all application state. TypeScript calls Python; Python does not call TypeScript.

**API contract principles:**
- All communication via HTTP REST on localhost (127.0.0.1)
- All payloads in JSON
- Schemas are defined in Python (Pydantic) and exported as JSON Schema for TypeScript consumption
- TypeScript generates typed client from JSON Schema (or manual typing from schema)
- No shared in-memory state; all state lives in Python layer

**Core endpoints (to be formally specified in Phase 001):**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/generate` | Generate devotional for given input |
| GET | `/devotional/{id}` | Retrieve generated devotional state |
| PUT | `/devotional/{id}/section/{section}/approve` | Set section approval status |
| GET | `/devotional/{id}/section/{section}/snapshots` | List snapshots |
| POST | `/devotional/{id}/section/{section}/restore` | Restore snapshot |
| GET | `/devotional/{id}/export-gate` | Check exportability |
| POST | `/export/{id}/pdf` | Trigger PDF generation (returns PDF bytes) |
| GET | `/scoring/run/{id}` | Run AC Scoring Harness on a devotional |
| GET | `/registry/diversity-report/{series_id}` | Author diversity report |

### 4.2 Python → PDF Export Contract

The PDF export flow passes through Python's export gate before TypeScript renders the PDF:

1. TypeScript requests export via `/export/{id}/pdf`
2. Python export gate checks all sections `approval_status = approved` (publish-ready mode)
3. Python serializes the approved `DailyDevotional` records to a `DocumentRepresentation` JSON
4. TypeScript PDF engine receives `DocumentRepresentation` and renders PDF
5. PDF bytes returned to Python, stored to disk, path returned to TypeScript

The `DocumentRepresentation` schema must be defined and frozen before Phase 003 begins.

### 4.3 AC Scoring Harness Interface

The AC Scoring Harness is a standalone Python module with a single public entry point:

```
score(content: ScoredContent, spec_path: str) -> ScoringResult
```

Where:
- `ScoredContent` is a typed representation of one devotional unit's content (no generation state)
- `spec_path` is the path to the immutable test specification YAML file
- `ScoringResult` contains: `{ac_id: {status: pass|fail, reason_code: str, explanation: str}}` for all AC-01–AC-43, plus `spec_hash`, `spec_version`, `scored_at`

**The harness module must have zero imports from any other application module.**

---

## 5. Technology Choices (Implementation Decisions for System A)

These are System A's implementation choices. They satisfy the PRD's behavioral requirements using specific technologies. They are not PRD requirements — the PRD is technology-agnostic.

| Component | Technology Choice | Rationale |
|-----------|------------------|-----------|
| Python version | 3.11+ | Long-term support; modern typing |
| Data validation | Pydantic v2 | Type-safe schemas; JSON Schema export |
| API server | FastAPI | Async-native; OpenAPI spec auto-generation |
| Local semantic retrieval index (Quote Catalog) | ChromaDB (embedded) | Local-first; no server process; Python-native |
| Local semantic retrieval index (Exposition RAG) | ChromaDB (embedded) | Same instance; different collection |
| Embedding model | sentence-transformers (local) | No API calls for embeddings; offline capable |
| Registry persistence | SQLite (via SQLAlchemy) | Local-first; file-based; survives restarts |
| Encryption at rest | cryptography library + macOS Keychain | NFR-05 compliance |
| TypeScript version | 5.x | Current LTS |
| Frontend framework | React + Vite | WCAG AA tooling; component-based |
| PDF library | pdf-lib 1.17.1 (TypeScript) | Selected in Phase 003; operator-approved 2026-02-24 |
| Test framework (Python) | pytest | Unit + integration |
| Test framework (TypeScript) | Vitest | Unit; Playwright for UI |

**Phase 003 selections (operator-approved 2026-02-24):**
- PDF library: `pdf-lib 1.17.1` (full layout control; required for FR-63 footnote placement and FR-85 two-pass margins)
- Body font: EB Garamond Regular/Bold/Italic, OFL licensed, bundled in `ui/fonts/`
- TypeScript invocation: `tsx` subprocess (Python spawns `npx tsx ui/pdf/engine.ts`; no compile step required)

**Python → TypeScript subprocess contract (Phase 003, Option A):**

Python (`src/api/pdf_export.py`) spawns the TypeScript engine as a subprocess:
- stdin: `{ "document": <DocumentRepresentation JSON>, "output_mode": "personal" | "publish-ready" }`
- stdout: raw PDF bytes
- stderr: error messages (non-zero exit on failure)

The TypeScript engine is invoked as: `npx tsx ui/pdf/engine.ts`
CWD for subprocess: project root (where `ui/` directory is located).

This approach requires `tsx` in `ui/package.json` devDependencies and `pnpm install`
to have been run in `ui/` before calling `export_pdf()`.

---

## 6. What Does NOT Cross the Boundary

The following must never be implemented in the wrong layer:

| Item | Must Stay In | Must NOT Be In |
|------|-------------|---------------|
| LLM calls | Python | TypeScript |
| Vector/embedding operations | Python | TypeScript |
| Validation logic (FR-73–77) | Python | TypeScript |
| AC Scoring Harness | Python | TypeScript |
| Series Registry state | Python | TypeScript |
| Approval state persistence | Python | TypeScript |
| PDF rendering | TypeScript | Python |
| UI state management | TypeScript | Python |
| Font files (bundled) | TypeScript (in app bundle) | Python |

The UI may display validation results received from Python, but it must not re-implement validation logic.

---

## 7. Approval

**Status**: APPROVED — 2026-02-24

**Review criteria:**
- [x] Python/TypeScript boundary is clear and complete
- [x] Technology choices are acceptable
- [x] REST API approach is acceptable
- [x] AC Scoring Harness isolation rule is understood
- [x] PDF library spike test approach is acceptable
- [x] `sacredwhisperspublishing.com` live requirement noted
- [x] AC spec extraction protocol from PRD (v1.1 addition)

**Operator note (2026-02-24):** "The Python/TypeScript boundary is clear, responsibility-complete, and satisfies TC-04. The AC Scoring Harness isolation remains consistent with TC-06 deterministic requirements. Phase 001 may begin. No boundary revisions required at this time."

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.3 | 2026-02-24 | Phase 003 decisions appended: pdf-lib selected, EB Garamond fonts, tsx subprocess invocation. Python→TypeScript subprocess contract documented in Section 5. |
| 1.2 | 2026-02-24 | Gatekeeper APPROVE — Section 2.4 updated: Builder implements harness infrastructure only; canonical spec authored by PRD Designer + Operator at evaluation time; provisional dev spec clearly labeled; `spec_extractor.py` removed from Builder scope |
| 1.1 | 2026-02-24 | Operator APPROVED; updated AC Scoring Harness section — spec derived from PRD_v16.md, materialized to competition-2026/outputs/, spec_hash = SHA256(extracted_yaml); PRD gap documented |
| 1.0 | 2026-02-24 | Initial boundary definition — TC-04 compliance |
