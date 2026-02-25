# Roadmap — Devotional Generator System A

**Project**: devotional-generator-system-a
**Version**: 1.0
**Date**: 2026-02-24
**Status**: Draft — Iteration 1

---

## Phase Overview

| Phase | Name | Key Deliverables | Dependency | Status |
|-------|------|-----------------|------------|--------|
| 001 | Data Model & Inputs | Input/output schemas, Series Registry, Mock RAG contract, Scripture retrieval, `constitution.md` | None | **COMPLETE — 2026-02-24** |
| 002 | Template System | Section templates, front matter, Day 7, rendering engine | Phase 001 schemas final | **COMPLETE — 2026-02-24** |
| 003 | KDP PDF Export | PDF engine, margins, fonts, KDP compliance checker | Phase 002 templates | Not started |
| 004 | Validation, Review UI & AC Scoring Harness | Validators, AC harness, human review UI, export gate, encryption | Phase 001 registry; Phase 003 PDF working | Not started |

---

## Phase 001 — Data Model & Inputs ✓ COMPLETE — 2026-02-24

**Goal:** Establish the foundational data contracts that all subsequent phases depend on. Define the Python/TypeScript boundary. Stand up scripture retrieval.

**Key Deliverables:**
- Python Pydantic schemas: `DevotionalInput`, `DailyDevotional`, `GroundingMap`, `PrayerTraceMap`, `SeriesRegistry`
- `constitution.md` (Python/TypeScript boundary — TC-04 required before Phase 001 closes)
- Mock RAG interface contract (quote retrieval + exposition RAG — allows Phase 002/003 to proceed without real RAG)
- Scripture retrieval module: Bolls.life primary → API.Bible secondary → operator import fallback
- Bolls.life book ID mapping table (local, build on setup)
- Series Registry initial implementation: persistence, de-duplication logic, author distribution tracking
- NASB full-translation local cache (optional download at setup per Appendix A.8)

**Milestones:**
- M1-001: All schemas defined and documented — ✓ 2026-02-24
- M1-002: Mock RAG interface contract finalized — ✓ 2026-02-24
- M1-003: Scripture retrieval passing integration tests — ✓ 2026-02-24
- M1-004: `constitution.md` complete and operator-reviewed — ✓ 2026-02-24 (v1.2)
- M1-005: Series Registry persisting across restarts — ✓ 2026-02-24

**Commit Points**: CP1–CP5 (see Phase 001 plan) — all complete

**Result**: 102 tests passing; CP1 `e70b22e` → CP2 `e0eb72e` → CP3 `c5b77bf` → CP4 `fdff29c` + fix `57615a1` → CP5 `baa7cc2`

---

## Phase 002 — Template System ✓ COMPLETE — 2026-02-24

**Goal:** Define all content templates for section rendering. No PDF generation yet — output to structured in-memory/file representation that Phase 003 consumes.

**Key Deliverables:**
- Section templates: Timeless Wisdom, Scripture Reading, Reflection, Still Before God, Walk It Out, Prayer
- Day 6 sending prompt template
- Day 7 template (Before the Service / After the Service with Track A/Track B)
- Front matter templates: title page, copyright page (Sacred Whispers Publishers imprint), introduction
- Sunday Worship Integration introduction block (static operator-authored template for when Day 7 enabled)
- Conditional TOC template (12+ days)
- Offer page template (fixed content, sacredwhisperspublishing.com)
- Rendering engine: takes `DailyDevotional` schema + templates → structured document representation

**Milestones:**
- M2-001: All 6 section templates producing correct output for mock data — ✓ 2026-02-24
- M2-002: Day 7 templates complete (sending prompt + Before/After/Track A/Track B) — ✓ 2026-02-24
- M2-003: Front matter templates complete — ✓ 2026-02-24
- M2-004: Rendering engine wired end-to-end (mock input → document representation) — ✓ 2026-02-24

**Commit Points**: CP1–CP4 (see Phase 002 plan) — all complete

**Result**: 123 tests passing (225 cumulative with Phase 001); CP1 `ddb8c28` → CP2 `1d2303e` → CP3 `a1e9bad` → CP4 `ba139ae`; `templates/introduction_sunday.md` operator-approved 2026-02-24

---

## Phase 003 — KDP PDF Export

**Goal:** Convert the document representation from Phase 002 into a KDP-compliant 6x9 PDF.

**Key Deliverables:**
- PDF engine (TypeScript): takes document representation → PDF
- Open-source font bundle (embedded in output): serif body font, heading font
- Margin calculation by page count (per FR-85 table)
- Block quote rendering (Quote and Scripture)
- Turabian footnote rendering (quote attribution at page bottom)
- Page numbering: Roman numerals/suppressed for front matter; Arabic for content
- Each day on new page (FR-91)
- KDP compliance checker: trim size, margin, font embedding, page count, 24-page minimum warning
- End-to-end test: known input → PDF → compliance check passes

**Milestones:**
- M3-001: PDF engine generating valid file from mock content
- M3-002: Fonts embedded; trim size correct
- M3-003: Margins calculated correctly for all page count brackets
- M3-004: KDP compliance checker passing automated checks
- M3-005: Offer page rendering correctly as final page

**Commit Points**: CP1–CP5 (see Phase 003 plan)

---

## Phase 004 — Validation, Review UI & AC Scoring Harness

**Goal:** Build the deterministic validation and scoring layer, the human review UI, and wire all layers into a working end-to-end system.

**Sub-phases (execution order within Phase 004):**

**Sub-phase A — AC Scoring Harness (competition-critical; first)**
- Immutable shared test specification (YAML/JSON; hash-verified before each run)
- AC-01 through AC-43 deterministic scoring functions
- Validator version recording in all scoring outputs
- Isolation guarantee: harness receives content as input only; no generation state

**Sub-phase B — Theological Validators**
- FR-73: Validation pass orchestrator
- FR-74: Exposition validator (structure, voice, word count, Grounding Map completeness)
- FR-75: Be Still validator (prompt count, inward-to-outward sequence, second person)
- FR-76: Action Steps validator (connector phrase, item count, active expectation)
- FR-77: Prayer validator (address, word count, Prayer Trace Map completeness, no untraceable elements)
- FR-78: Rewrite routing logic (one auto-rewrite attempt → human review queue)
- Archaic language modernization function (all retrieved text)

**Sub-phase C — Human Review UI**
- Local web UI (TypeScript/React on localhost)
- Per-section display with edit capability
- Approval status tracking (pending | approved) per section per day
- Grounding Map and retrieved excerpts displayed alongside exposition (FR-79a)
- Snapshot/restore: 3 states per section per day
- Author diversity report view
- WCAG AA compliance

**Sub-phase D — Integration & Export Gate**
- Generation pipeline integration (RAG → validators → UI queue)
- Export gate: publish-ready mode blocks unless all sections `approval_status = approved`
- Personal mode: warning on unapproved content, does not block
- De-duplication enforcement at generation time
- Quote shortage alert routing
- Encryption at rest for workspace and registry

**Milestones:**
- M4-001: AC Scoring Harness scoring all AC-01–AC-43 with passing + failing test cases
- M4-002: All FR-74–FR-77 validators passing unit tests (pass + fail cases)
- M4-003: Review UI functional (all sections editable, approval tracked)
- M4-004: End-to-end test: topic → generation → validation → UI → approve → PDF → compliance check
- M4-005: Encryption at rest operational

**Commit Points**: CP1–CP10 (see Phase 004 plan)

---

## Cross-Cutting Concerns

### Quote Catalog Indexing (TC-02)
May proceed in parallel with Phase 001 but must be complete before Phase 004 integration testing. Not a blocking dependency for Phases 001–003 because the Mock RAG interface abstracts it.

### Exposition RAG Source Indexing (TC-03)
Same as Quote Catalog: parallel with Phase 001, required before Phase 004 integration.

### Real RAG Integration Point
The Mock RAG interface defined in Phase 001 is replaced with real RAG implementations in Phase 004 Sub-phase D. This is the only integration point.

---

## Dependencies Summary

```
Phase 001
    │
    ├──→ Phase 002 (schemas complete)
    │         │
    │         └──→ Phase 003 (templates complete)
    │                   │
    └──────────────────→ Phase 004 (registry schema complete + Phase 003 working)
         (AC Scoring Harness first within Phase 004)
```

---

## Risk Register

| Risk | Phase | Mitigation |
|------|-------|-----------|
| NASB copyright limits | All | Human legal review before publication; track Lockman Foundation quotation limits |
| PDF library selection | 003 | Test two PDF libraries early; select before Phase 003 begins |
| Bolls.life unavailability | 001 | Download full NASB translation locally at setup (Appendix A.8) |
| Quote Catalog thin coverage | 004 | Live retrieval fallback + shortage alert (FR-52) |
| Validator drift between systems | 004 | Immutable hash-verified test spec (TC-06); same YAML used by both systems |
| AC Scoring Harness spec location | 004 | Confirm shared path with operator before Phase 004 (see Assumption A-01) |
| sacredwhisperspublishing.com not live | 003/004 | Site must be live before publish-ready export released; human action required |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-24 | Initial roadmap — Iteration 1 |
| 1.1 | 2026-02-24 | Phase 001 marked COMPLETE; Phase 002 in planning |
| 1.2 | 2026-02-24 | Phase 002 marked COMPLETE; Phase 003 in planning |
