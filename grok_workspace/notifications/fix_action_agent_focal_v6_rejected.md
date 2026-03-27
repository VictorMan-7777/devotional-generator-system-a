REJECTED: fix_action_agent_focal.py v6 — wrong indentation in replacement, file reverted

The pattern is now correct (includes \n\s* anchor). The assert passes. But the replacement produces the wrong indentation.

Look at the function body of run_action_writer_training_cycle around line 89-125. Every statement at the function body level uses 4-space indent:
- `retriever = ScriptureRetriever()` — 4 spaces
- `brief = build_editorial_day_brief(...)` — 4 spaces
- `be_still_prompts = _build_be_still(...)` — 4 spaces
- closing `)` for each call — 4 spaces
- `try:` — 4 spaces

Your replacement uses 8 spaces for `focal_scripture_text` and `action_connector`. Those two lines land in the function body where every other statement is at 4 spaces.

The replacement's indent level for the two call lines must match the rest of the function body.

Resubmit v7.
