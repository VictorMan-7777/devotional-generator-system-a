---
name: AI Coding Tools 2026 — Video Research
description: Scored comparison of AI coding tools and frontier models for future build decisions, especially relevant for NAS migration and new system development
type: reference
---

## Source Videos (March 2026)

### Video 1: "Claude Opus 4.6 vs GPT-5.4" (AI Luke)
Head-to-head on raw model intelligence inside real codebases and one-shot browser apps.

**Claude Opus 4.6 strengths:**
- Thoughtful planning and proactive gap analysis
- Production-grade, maintainable code
- Handles larger/more complex codebases
- 1M context window
- Strong agentic capabilities

**GPT-5.4 / Codex strengths:**
- Raw execution speed
- Computer-use and agentic navigation tasks
- Architectural reasoning in some cases
- Lower cost per token

**Dual-wield pattern:** Use one model for initial generation/planning, the other for critical review and polishing. Consistently beats using either alone.

**Evaluation framework for real work:**
1. Pick real tasks (refactor, new feature, API design, PR review, debug)
2. Same prompt on both models
3. Measure: speed to usable output, code quality, handling ambiguity, edge cases, manual fix time
4. Track: time saved vs bugs introduced, consistency across long sessions, adherence to existing patterns

---

### Video 2: "Best AI Coding Tools for Developers in 2026" (Mikey No Code)
Report Card Method — graded across UX, prompt efficiency, deployment, and pricing.

| Tool | Score | Price | Best For |
|------|-------|-------|----------|
| Cursor AI | 68/100 | $20/mo (credit-based, fewer requests than before) | VS Code users, existing codebase work |
| Windsurf | 73/100 | $15/mo (500 credits) | VS Code + Cascade agent, native Netlify deploy |
| GitHub Copilot | 81/100 | $10/mo Pro, $39/mo Enterprise | In-IDE enhancement, production stability, multi-revision consistency |
| Base44 | 92/100 | $40/mo flat (no token surprises) | Rapid prototyping, no-code, instant web+iOS+Android deploy |

**GitHub Copilot** — highest among traditional tools. Best for production-ready code and stable multi-revision work. No built-in deployment (uses external tools).

**Base44** — clear winner for speed to production. Handles full-stack MVP (auth, DB, offline, threading) in ~2 min. One-click publish. Relevant for prototyping new product ideas before building custom.

---

---

### Video 3: "How to Make the Best of AI Programming Assistants" (Dave Farley)
Core argument: The Nyquist-Shannon sampling theorem applied to AI code generation.

**The problem:** AI produces code faster than humans can manually verify. If you check at low frequency (manual review) but produce at high frequency (AI generation), you will miss errors — guaranteed by information theory. The code looks plausible. Mistakes are subtle. Volume is too large to read manually.

**The solution — continuous integration as sampling mechanism:**
- Run full test suite on every AI-generated change, not in batches
- Automated checks: type checking, linting, architecture boundary enforcement, contract tests
- Test for behavior, not just syntax — AI produces syntactically valid code that violates domain logic
- Pipeline must be fast: seconds not minutes (30-minute pipelines = wrong sampling frequency)
- Work in small chunks — don't ask AI to write a whole feature at once; get feedback after each meaningful change
- Integrate frequently — long-lived branches reduce sampling rate dangerously
- Tests are the source of truth, not manual review

**Key quote:** "If you increase production frequency, you must increase feedback frequency or your system will fail."

**Directly relevant to DevG:**
- The training experiment loop IS the sampling mechanism — each experiment is a check
- l15_enforce was an undersampling failure: same error ran 146 times before detection
- The 303 stuck assignments were undetected because no automated check ran against the assigned queue
- archive_stale is a manual patch; an automated CI check on assigned experiment age would catch this continuously
- For NAS build: fast automated test suite on every change is non-negotiable when AI is generating training code at high velocity

## How to Apply in Future Builds

**NAS migration / new system builds:**
- Greenfield projects: consider Base44 for rapid prototype validation before committing to custom code
- IDE-integrated development: GitHub Copilot ($10/mo) over Cursor/Windsurf for stability
- Model choice for agents/trainers: Claude Opus 4.6 for complex reasoning and long-context work; GPT-5.4/Codex for speed and compute tasks
- Dual-wield: one model generates, a different one reviews (already live in DevG cross-evaluator)

**What doesn't change:**
- 100+ experiment rule before switching trainer APIs still applies
- Cross-provider evaluation (different AI reviews the generator's work) is already the right pattern
