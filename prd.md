# Product Requirements Document — System A Build Plan

**Project**: devotional-generator-system-a
**Version**: 1.0
**Date**: 2026-02-24
**Author**: Planner (Claude Code / automated-builder)
**Authoritative Source**: [../competition-2026/input/PRD_v16.md](../competition-2026/input/PRD_v16.md)
**Status**: Draft — Iteration 1

---

> **Source-of-Truth Rule**: The authoritative product requirements are defined in
> `../competition-2026/input/PRD_v16.md` (read-only). This document is the
> **System A build plan** — it defines what System A must build, in what order,
> and how it will be verified. It does not redefine product requirements; it maps
> them to a phased implementation plan. Any conflict between this document and
> the authoritative PRD must be resolved in favor of the authoritative PRD.

---

## 1. Goals

### 1.1 Primary Goal

Build the FaithJourney.ai Devotional Generator to production quality as System A in the two-system competition architecture. Produce a local, single-user application that generates KDP-ready devotional books with:

- A deterministic AC Scoring Harness (TC-06) — the foundation of the competition
- Fully isolated, model-independent validators (FR-73–77)
- A local human review/edit UI with approval gates
- KDP-compliant 6x9 PDF export

### 1.2 Competition Integrity Goal

The AC Scoring Harness must be built such that it can score both System A's output and Agent Zero's output using the same immutable, hash-verified test specification, producing identical pass/fail results for identical inputs. Without this, the competition cannot produce a valid result.

### 1.3 Implementation-Agnostic Stance

System A must not bake model-provider assumptions, specific LLM vendors, or framework-specific patterns into the contract layer or the AC Scoring Harness. The scoring harness and validators must be model-independent (TC-06).

---

## 2. Scope

### 2.1 In Scope (V1.0)

All Functional Requirements (FR-01 through FR-97) defined in PRD v16 as non-deferred.

Key areas:
- Complete devotional unit generation: Quote → Scripture → Exposition → Be Still → Walk It Out → Prayer
- Agentic RAG for exposition with Grounding Map
- Cached RAG for Quote Catalog with live fallback
- Scripture retrieval with Bolls.life primary / API.Bible secondary / operator import tertiary
- Day 6 sending prompt and Day 7 Sunday worship integration (when enabled)
- Series Registry (persistent, encrypted at rest)
- Parent-child volume architecture
- Human review/edit UI with per-section approval tracking
- Snapshot/version history (3 states per section per day)
- KDP-compliant PDF: 6x9, margins by page count, embedded fonts, front matter, TOC (12+ days), offer page
- Doctrinal guardrails and theological validation pass
- AC Scoring Harness (AC-01 through AC-43, deterministic, isolated, hash-verified)
- Archaic language modernization for all retrieved text

### 2.2 Out of Scope (V1.0)

Per PRD Section 14:
- Ebook export (EPUB/MOBI)
- Cover design
- Bowker ISBN integration
- Print-on-demand integration
- Web-based or cloud UI
- Database backend
- Multi-language support
- Multi-user access
- Logos Bible Software integration
- Personalized devotional system (Section 14.1)

---

## 3. Functional Requirements Summary

All FRs are authoritatively defined in PRD v16. This section provides a navigable summary by phase.

### 3.1 Phase 001 — Data Model & Inputs (FR mapping)

| FR | Description |
|----|-------------|
| FR-01–FR-16 | Exposition four-paragraph structure requirements |
| FR-20–FR-28 | Be Still section requirements |
| FR-29–FR-34 | Action Steps requirements |
| FR-35–FR-48 | Prayer requirements |
| FR-49–FR-56 | Quote sourcing and Turabian attribution |
| FR-57–FR-60 | Scripture retrieval |
| FR-64–FR-72 | Quality control, de-duplication, series registry |
| TC-01 through TC-06 | Technical constraints |

Schema deliverables:
- `DevotionalInput` schema (topic, num_days, scripture_version, output_mode)
- `DailyDevotional` schema (all 6 sections + approval_status)
- `GroundingMap` schema (4 entries, one per exposition paragraph)
- `PrayerTraceMap` schema (one entry per prayer element)
- `SeriesRegistry` schema (quotes, scriptures, author distribution)
- `MockRAGInterface` contract (swap real/mock without code changes)

### 3.2 Phase 002 — Template System (FR mapping)

| FR | Description |
|----|-------------|
| FR-87–FR-94 | Front matter: title page, copyright, introduction, TOC, offer page |
| FR-95–FR-97 | Day 6 sending prompt, Day 7 structure, introduction Sunday worship guidance |
| FR-61–FR-63 | Block quote and footnote rendering patterns |

### 3.3 Phase 003 — KDP PDF Export (FR mapping)

| FR | Description |
|----|-------------|
| FR-84 | 6x9 inch trim size |
| FR-85 | Margins keyed to page count |
| FR-86 | Open-source bundled embedded fonts |
| FR-91 | Each day on new page |
| FR-92 | Roman numerals for front matter; Arabic for content |
| FR-93 | 24-page minimum warning |
| FR-94 | Back-of-book offer page |

### 3.4 Phase 004 — Validation, Review UI & AC Scoring Harness (FR mapping)

| FR | Description |
|----|-------------|
| FR-73–FR-77 | Theological validation pass (exposition, Be Still, Action Steps, Prayer) |
| FR-78 | Automatic rewrite attempt on validation failure |
| FR-79–FR-83 | Human review and approval gate |
| FR-79a | Exposition Reference Artifact in review UI |
| AC-01–AC-43 | Acceptance criteria — all must be met for publication-ready output |
| TC-06 | Deterministic Validator Isolation Layer |
| Section 18.5 | AC Scoring Harness — immutable hash-verified test spec |

---

## 4. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | Generation under 30s; PDF export under 2 minutes |
| NFR-02 | 95%+ PDF generation success rate; 3 snapshot states per section per day |
| NFR-03 | Modular architecture: generation / template / PDF separated |
| NFR-04 | WCAG AA compliance for local review UI |
| NFR-05 | Workspace and registry encrypted at rest (OS keychain or passphrase); PDFs unencrypted |
| NFR-06 | Single-user local operation only |

---

## 5. Technical Constraints

All constraints from PRD Section 12 are binding. Key constraints:

| TC | Constraint |
|----|-----------|
| TC-01 | Python and TypeScript only |
| TC-02 | Quote retrieval via cached RAG against verified Quote Catalog; no AI recall |
| TC-03 | Exposition via agentic RAG; plan retrieval → retrieve → reason → generate → Grounding Map → validate → iterate |
| TC-04 | Python/TypeScript boundary in `constitution.md` before Phase 001 closes |
| TC-05 | Series Registry persistent, backed up with each generated volume |
| TC-06 | Validators model-independent, version-locked, isolated; scorer hash-verified; version recorded in all scoring output |

**TC-01 scope clarification (from PRD D052):** TC-01 through TC-05 are constraints on the **deliverable** (the Devotional Generator application), not on the builder agent (Claude Code). System A uses Claude Code to build; the produced application must satisfy TC-01 through TC-05.

---

## 6. PRD Implementation-Prescription Flags

Per Planner Instruction #3, the following PRD statements appear to prescribe implementation rather than behavior. These are flagged for operator review. They do not block planning but should be corrected in PRD v17 if both systems are to remain fully implementation-agnostic.

### Flag 1 — "Vector Database" Language (TC-02, TC-03, FR-17, FR-19, FR-51)

**Occurrences:**
- TC-02: "vector-indexed corpus"
- TC-03: "local vector database"
- FR-17: "indexed in a local vector database"
- FR-19: "local vector database"
- FR-51: "local vector database"

**Issue:** "Vector database" prescribes a specific implementation technology. A valid implementation could use BM25 full-text search, a different embedding store, or any semantic retrieval mechanism. The PRD should specify the behavioral requirement (semantic similarity retrieval against a local corpus) rather than the technology.

**Recommendation:** Replace "vector database" with "local semantic retrieval index" throughout. Both systems may implement this with any compliant technology.

**Impact on System A:** None — System A will implement a vector database (the most practical approach). This is a flag for competition integrity, not a block.

### Flag 2 — Exposition RAG Source Specification (FR-17, FR-18)

**Issue:** FR-17 lists ten specific commentary and reference works by name and states they must be queried. This is a behavioral requirement (both systems must ground exposition in these sources), not an implementation prescription. The flag is that the phrase "indexed in a local vector database and queried by passage reference and topic" within FR-17 adds implementation detail.

**Recommendation:** Separate the source list (binding behavioral requirement) from the retrieval mechanism (implementation choice). Source list stays; "local vector database" becomes "local semantic retrieval system."

### Flag 3 — Bolls.life API Contract Detail (Section 10.6, Appendix A)

**Issue:** The PRD includes full API contract detail for Bolls.life (specific endpoint URLs, request format, response fields). This is unusually implementation-specific for a behavioral PRD.

**Assessment:** This is **justified** because: (a) Bolls.life is the only free NASB source, (b) both systems must use the same primary source for scripture retrieval consistency, (c) the contract detail serves as a shared interface specification, not a library constraint. This flag is informational only; no change recommended for this item.

### Flag 4 — Section 19 (Agent Zero Escalation System)

**Issue:** Section 19 defines a human escalation system specific to Agent Zero's autonomous operation. It has no applicability to System A (which has a human operator actively present). Including it in the PRD creates an asymmetric requirement that only applies to one system.

**Assessment:** Section 19 is Agent Zero's operational requirement, not a product requirement of the Devotional Generator itself. System A does not need to implement an escalation notification system. The PRD should ideally separate product requirements (applicable to both systems) from Agent Zero operational requirements (applicable only to System B).

**Impact on System A:** None — System A does not implement Section 19. This flag is for PRD structural clarity.

---

## 7. Acceptance Criteria — Project-Level

The System A build is complete when:

### 7.1 Generation Pipeline
- [ ] Generates a complete 6-day devotional with all 6 sections for a given topic
- [ ] Generates Day 7 (sending prompt + Before/After the Service) when enabled
- [ ] All section word count validators pass (Exposition: 500–700w; Prayer: 120–200w; etc.)
- [ ] Grounding Map produced for every exposition (4 non-empty entries)
- [ ] Prayer Trace Map produced for every prayer (one entry per prayer element, no untraceable elements)
- [ ] Quote retrieved from local catalog; Turabian attribution attached
- [ ] Scripture retrieved via Bolls.life → API.Bible → operator import fallback chain
- [ ] Archaic language modernization applied to all retrieved text
- [ ] Series Registry persists across restarts and backs up on volume export

### 7.2 Validation Layer
- [ ] FR-73 through FR-77 validators return structured reason codes for all violations
- [ ] One automatic rewrite attempt on validation failure; route to human review queue on second failure
- [ ] Grounding Map completeness validated (FR-74)
- [ ] Prayer Trace Map completeness validated (FR-77)
- [ ] Doctrinal guardrails flagging known-bad theological inputs (smoke tests per Section 18.4)

### 7.3 AC Scoring Harness (Competition-Critical)
- [ ] Immutable shared test specification exists and is hash-verified before each run
- [ ] AC-01 through AC-43 deterministic pass/fail scoring with reason codes
- [ ] Validator version recorded in every scoring output
- [ ] Harness runs in isolation from generation state
- [ ] Comparison output format defined (accommodates both System A and Agent Zero inputs)

### 7.4 Human Review UI
- [ ] All sections visible and editable per day
- [ ] Per-section approval_status tracked (pending | approved)
- [ ] Grounding Map and retrieved excerpts displayed alongside exposition (FR-79a)
- [ ] Snapshot/restore: 3 states per section per day
- [ ] WCAG AA compliance

### 7.5 PDF Export
- [ ] KDP-compliant 6x9 trim size
- [ ] Margins applied per page-count bracket (FR-85 table)
- [ ] Open-source fonts embedded
- [ ] Front matter: title page, copyright (Sacred Whispers Publishers), introduction
- [ ] TOC present for 12+ day books
- [ ] Block quote rendering for Quote and Scripture
- [ ] Turabian footnotes on quote pages
- [ ] Offer page (sacredwhisperspublishing.com) as final page
- [ ] 24-page minimum warning surfaced to operator
- [ ] KDP compliance check passes on every export

### 7.6 Encryption and Security
- [ ] Workspace directory encrypted at rest
- [ ] Series Registry backups encrypted at rest
- [ ] Exported PDFs unencrypted (KDP deliverable)

---

## 8. MVP-First Execution Order

The following execution order delivers working output as early as possible without compromising deterministic scoring equivalence.

**Principle**: The AC Scoring Harness is non-negotiable and must not be deferred. It must be the first deliverable within Phase 004 — before the full UI is built — because it is the structural foundation of the competition.

| Order | Deliverable | Phase |
|-------|-------------|-------|
| 1 | Data schemas (Python Pydantic models) | 001 |
| 2 | Mock RAG interface + Series Registry schema | 001 |
| 3 | Scripture retrieval (Bolls.life → fallback chain) | 001 |
| 4 | `constitution.md` finalized | 001 |
| 5 | Content templates (all sections) | 002 |
| 6 | Day 7 + front matter templates | 002 |
| 7 | PDF layout engine + font embedding | 003 |
| 8 | KDP compliance checker | 003 |
| **9** | **AC Scoring Harness (immutable test spec + AC-01–43 scoring)** | **004** |
| 10 | Theological validators (FR-73–77) | 004 |
| 11 | Human review UI | 004 |
| 12 | Full RAG pipeline integration (Quote Catalog + Exposition RAG) | 004 |
| 13 | Export gate (approval status checking) | 004 |
| 14 | Encryption at rest | 004 |

---

## 9. Open Questions / Assumptions

The following items were not explicitly specified in the authoritative PRD and represent assumptions made in this planning document. They are flagged for operator review.

| # | Assumption | Source Gap | Impact |
|---|-----------|-----------|--------|
| A-01 | ~~The AC Scoring Harness shared test spec will live at a shared path accessible to both System A and Agent Zero.~~ **CORRECTED 2026-02-24**: There is no externally shared spec file delivered separately. The canonical AC test spec is derived from PRD_v16.md Section 11 (AC-01 through AC-43). System A derives and materializes a YAML spec to `../competition-2026/outputs/ac-test-spec.extracted.yaml`. spec_hash = SHA256(that file). Both systems compute spec_hash independently from PRD and record it in scoring outputs. Matching hashes confirm equivalent interpretation of the same contract. A mismatch is itself a competition finding. PRD_v16.md remains the sole source of truth. | PRD says "shared immutable test specification" — resolved: PRD itself is the shared immutable source. Machine-readable YAML is a derived artifact. | Resolved. See updated `constitution.md` Section 2.4 and `phases/004`. |
| A-02 | Quote Catalog will be implemented as a ChromaDB (or equivalent) vector database in Python, embedded locally in the application. The specific vector DB is an implementation choice (see Flag 1 above). | PRD says "local vector database" | Low — both valid; implementation choice for System A. |
| A-03 | The Exposition RAG sources (FR-17) will be indexed from public domain web sources during application setup, not bundled with the application. A setup script will crawl and index. | PRD does not specify whether sources are bundled or crawled. | Noted in Phase 001. |
| A-04 | The human review UI will be a local web app (Python backend serving a TypeScript/React frontend on localhost). This is the most practical implementation for WCAG AA compliance. | PRD says "local UI" but not the technology. | Consistent with TC-01. |
| A-05 | The encryption at rest will use OS keychain integration (macOS Keychain on Barbara's machine) for the encryption key. | PRD says "OS keychain-managed key or operator passphrase." | System A will implement OS keychain; operator passphrase as fallback. |
| A-06 | `sacredwhisperspublishing.com` must be live and functional before any publish-ready export is released (PRD Section 14.1). This is a human-required step outside the application. | PRD notes this in Section 14.1. | No application impact — flagged for operator awareness. |

---

### Competition Input Asymmetry (Confirmed 2026-02-24)

| System | Inputs Received |
|--------|----------------|
| System A | PRD_v16.md + manual Volume 1 seed files (`../competition-2026/input/`) |
| System B (Agent Zero) | PRD_v16.md only (pasted input) |

System A's seed files:
- `Sacred Whispers - Series 1 Volume 1 Week 1 - Draft.pdf`
- `Sacred Whispers - Series 1-Day 1.pdf`
- `Series 1 - Volume 1 - 30-Day Outline.csv` / `.numbers`

These seed files inform Volume 1 content but do not change application architecture.

### Competition Artifact Structure (Enforced 2026-02-24)

Competition artifacts are segregated from project documentation:

```
../competition-2026/
├── input/        (read-only authoritative inputs)
├── outputs/      (append-only: scoring runs, PDFs, spec snapshots, comparison reports)
└── notes/        (append-only: competition journal entries only)
```

Notes policy: timestamped, append-only, never modify prior entries, no system documentation changes. See `../competition-2026/notes/README.md`.
