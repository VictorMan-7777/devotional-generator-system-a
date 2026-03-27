# Chat Channel Broken — run_grok_chat.py returns session-end markers

The chat channel (grok_workspace/chat.md) is not working. Grok's responses to Claude's questions are "Done." and "## Session complete." rather than actual answers.

## Root cause identified

`run_grok_chat.py` calls `run_grok_agent()` to answer chat questions. The default system prompt in `run_grok_agent()` includes:

> "IMPORTANT: At the end of every session, update grok_workspace/MEMORY.md using write_workspace_file with the latest system state..."

When Grok answers a chat question, it:
1. Reads relevant files (tool calls)
2. Writes grok_workspace/MEMORY.md (tool call)
3. Returns its final text content as "Done." or "## Session complete." — a session-end marker, not an answer

The `msg.content` that `run_grok_chat.py` captures as the answer is this terminal string, not the conversational response.

## The fix

In `scripts/autoresearch/run_grok_chat.py`, the `_answer_question()` function should pass a custom `system` argument to `run_grok_agent()` that:
1. Removes the MEMORY.md update instruction (irrelevant for chat)
2. Explicitly instructs: "Your final text response MUST be your answer to the user's question. Do not write files as part of answering chat questions. Return your answer as conversational prose."

The custom system prompt for chat should be something like:

```python
system = (
    "You are Grok, monitoring the DevG devotional content generation system. "
    "Use the provided file tools to read what you need, then answer the question directly. "
    "Your final text response must be your complete answer to the user's question — "
    "conversational prose, specific numbers, file names where relevant. "
    "Do NOT write files. Do NOT end with 'Done.' or 'Session complete.' — "
    "end with your actual answer.\n\n"
    + (f"## Your persistent memory:\n{_memory}" if _memory else "")
)
```

Pass this as `system=system` to `run_grok_agent()`.

## Also broken: grok_outliner_monitor

The 19:04 supervisor cycle shows `run_grok_outliner_monitor.py` also returning `"raw_response": "**Final response complete.**"` with `"parse_error": "Could not extract JSON from Grok response"`. This is the same MEMORY.md session-end pattern — the outliner monitor's Grok call is writing MEMORY.md and returning a termination string instead of a JSON report.

The fix is the same: any call to `run_grok_agent()` that expects structured output or a substantive answer needs a custom `system=` override that removes the MEMORY.md update instruction.

## Current status

Until this is fixed, Claude cannot receive answers from Grok via chat.md, and the outliner monitor produces no usable output. All three of Claude's pending questions remain unanswered:
1. Workload read + QUEUE.md priority order
2. Diagnoses ready for be-still / prayer / action writer proposals
3. DB alert path fix status

These items remain blocked. Claude is routing structural bug findings to Grok via notifications/ instead.
