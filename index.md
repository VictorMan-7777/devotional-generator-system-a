# Devotional Generator — System A

**Project Slug**: devotional-generator-system-a
**Status**: Phase 003 Complete — Phase 004 in progress
**Last Updated**: 2026-02-24
**Operator**: Barbara
**Competition Role**: System A (Automated Builder — builds first)
**Authoritative PRD**: [../competition-2026/input/PRD_v16.md](../competition-2026/input/PRD_v16.md) (read-only)

---

## Overview

System A is Barbara's primary implementation of the FaithJourney.ai Devotional Generator, built under the Automated Builder framework with human-guided AI development. It produces KDP-ready devotional books from structured inputs, enforces doctrinal guardrails, and implements the deterministic AC Scoring Harness required for competition validity.

The application is local, single-user, and built in Python (backend, generation, validation, scoring) and TypeScript (review UI, PDF export layer). No cloud deployment in V1.0.

---

## Navigation

### Planning Artifacts
- [PRD](prd.md) — Goals, requirements, and acceptance criteria for System A's build
- [Constitution](constitution.md) — Python/TypeScript boundary definition (TC-04 required)
- [Roadmap](roadmap.md) — Phases, milestones, and dependencies
- [Iteration Log](iteration-log.md) — Planning evolution tracking

### Phase Plans
- [Phase 001: Data Model & Inputs](phases/001-data-model-and-inputs.md)
- [Phase 002: Template System](phases/002-template-system.md)
- [Phase 003: KDP PDF Export](phases/003-kdp-pdf-export.md)
- [Phase 004: Validation, Review UI & AC Scoring Harness](phases/004-validation-review-and-scoring-harness.md)

### Build Outputs
- [Build Outputs](docs/system/outputs/)

---

## Authoritative Source Rule

`../competition-2026/input/` is read-only. All planner outputs are written only to this project directory (`devotional-generator-system-a/`) and its subdirectories.

---

## Competition Context

| Property | Value |
|----------|-------|
| System A role | Build first; produce production-quality implementation |
| System B | Agent Zero (autonomous, local LLMs, offset execution) |
| Evaluation basis | AC-01 through AC-43 via shared immutable AC Scoring Harness |
| Competition format | Offset and log-based; not head-to-head |
| PRD stance | Implementation-agnostic — both systems satisfy the same behavioral contract independently |

---

## Layer Separation Summary

| Layer | Language | Responsibility |
|-------|----------|---------------|
| Generation | Python | LLM calls, RAG pipelines, orchestration |
| Validation | Python | Deterministic FR-73–77 validators |
| AC Scoring | Python | Isolated, hash-verified, model-independent |
| Review UI | TypeScript | Local web UI for human review/edit/approval |
| PDF Export | TypeScript | KDP-compliant 6x9 PDF generation |

Full boundary definition: [constitution.md](constitution.md)

---

## Key Implementation Constraints

- Python + TypeScript only (TC-01)
- Python/TypeScript boundary defined in `constitution.md` before Phase 001 closes (TC-04)
- AC Scoring Harness: deterministic, isolated, hash-verified, version-locked (TC-06)
- Quote retrieval: cached RAG with live fallback; no AI recall (TC-02)
- Exposition generation: agentic RAG with Grounding Map (TC-03)
- Series Registry: persistent, encrypted at rest, survives restarts (TC-05)

---

## Phase Sequence

| Phase | Name | Prerequisite |
|-------|------|--------------|
| 001 | Data Model & Inputs | None |
| 002 | Template System | Phase 001 complete |
| 003 | KDP PDF Export | Phase 002 complete |
| 004 | Validation, Review UI & AC Scoring Harness | Phase 001 schema; Phase 003 PDF working |

---

## Status

| Phase | Status |
|-------|--------|
| Phase 001 — Data Model & Inputs | **COMPLETE — 2026-02-24** (CP1–CP5; 102 tests) |
| Phase 002 — Template System | **COMPLETE — 2026-02-24** (CP1–CP4; 123 tests) |
| Phase 003 — KDP PDF Export | **COMPLETE — 2026-02-24** (CP1–CP8; 73 TypeScript tests) |
| Phase 004 — Validation, Review UI & AC Scoring Harness | In progress — FR-73–77 validators complete; scoring harness and Review UI pending |

**Current Step**: Phase 004 implementation ongoing
**Next Step**: Phase 004 AC Scoring Harness
