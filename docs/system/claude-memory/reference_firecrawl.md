---
name: Firecrawl — library acquisition tool
description: Web scraping tool that converts pages to clean markdown/JSON for AI; relevant for DevG library expansion in later phases
type: reference
---

Firecrawl converts web pages to clean markdown/JSON consumable by AI agents. Covered in Greg Isenberg YouTube video "Firecrawl AI clearly explained" (uploaded 2026-03-24). Operator asked about applicability to DevG.

**Assessment**: Not a current-phase priority. Relevant for Phase 15+ when library depth becomes a RAG quality ceiling.

**Potential use in DevG**:
- Automate pulling public-domain theological texts from CCEL (Christian Classics Ethereal Library) and Project Gutenberg into the RAG library
- Accelerate open-source biblical resource scouting (see `docs/system/open-source-biblical-resource-scouting.md`)
- Feed the library trainer agent with acquired texts

**Why not now**: Current bottlenecks are worker pass rates and training loop quality — not data acquisition. RAG already has indexed source texts sufficient for current training.
