---
name: Policy Guardian Role
description: Policy guardian is an LLM agent cop — reads actual agent outputs against the written law (rules-laws constitution + federal laws). Authority is still the written law only; LLM is needed to read artifacts intelligently.
type: project
---

The policy guardian is the compliance cop and IS an LLM agent.

**Why:** A deterministic rule-checker can only verify file existence and fail counts. The cop needs LLM capability to actually read what agents are producing and apply the written laws to those outputs intelligently. The user confirmed this — the prior memory entry saying "no LLM" was wrong.

**How to apply:**
- Policy guardian IS an LLM agent — route: `DEVG_LLM_POLICY_GUARDIAN` in the router
- Its authority is still exclusively the written law — it does NOT invent or extrapolate rules
- It reads the rules-laws constitution (Tier 0) and federal laws (Tier 1, L1–L16)
- It reads actual agent output artifacts and evaluates them against those laws
- When a situation is not covered by written law: records "no applicable law" and escalates
- LLM is the reading/reasoning capability; the law is still the only authority
- Do NOT make it a judgment agent — it enforces what is written, not what it thinks is right
