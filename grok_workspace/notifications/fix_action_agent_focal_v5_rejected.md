REJECTED: fix_action_agent_focal.py v5 — file damage, reverted

The assert passed (pattern matched 182 chars) but the replacement produced broken indentation. The file has been reverted.

Root cause: your regex pattern starts matching at `action_connector` — not at the start of the line. The 4 leading spaces before `action_connector` are NOT part of the match. When the replacement is inserted, it lands AFTER those 4 existing spaces. Result:

- `focal_scripture_text` ends up at 4 + 8 = 12-space indent
- `action_connector` in the replacement starts on a new line at 8-space indent
- Neither is correct for the actual 4-space indent level of the function body

The target call in the file:
```
    action_connector, action_items = _build_action_steps(
        brief=brief,
        day_number=1,
        exposition_text=exposition_text,
        scripture_text=scripture_text,
    )
```
That is 4-space indent for the call, 8-space for args.

Diagnose: where in the regex pattern do you need to anchor or adjust so that the 4 leading spaces are part of the match, and the replacement is positioned correctly?

Resubmit v6 to grok_workspace/proposals/fix_action_agent_focal.py and update pending_approval.md.
