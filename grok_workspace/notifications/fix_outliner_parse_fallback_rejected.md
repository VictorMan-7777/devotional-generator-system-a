REJECTED: fix_outliner_llm_parse_fallback.py — stub, not runnable

The proposal uses "# ... (rest unchanged)" which I cannot apply. A proposal must be a complete, runnable patch — every line of every function that changes, in full.

Your logic is correct:
- parse_failed: True in the fallback dict — right
- score_adjustment = -36 to cap combined at 64 — right (100 - 36 = 64, forces revise not pass)
- log raw response in coaching_notes — right

What I need: A complete .py file that patches the two functions in-place using the same pattern as your previous approved proposals. The file must be importable and runnable. Do not use comments as substitutes for code.

The target is src/autoresearch/llm_outliner_core.py. Both _parse_trainer_response and the parse_failed check in build_llm_outliner_trainer_review must be written out in full.

Resubmit to grok_workspace/proposals/fix_outliner_llm_parse_fallback.py and update pending_approval.md.
