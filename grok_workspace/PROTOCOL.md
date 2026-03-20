# Grok Autonomous Change Protocol

## Branch
All Grok-initiated code changes go on: `grok/autoresearch`

Never commit to `main` or `feat/*` branches.

## Permission
Grok has permission to modify the training system autonomously under these rules:

### Human approval
When the user says "apply", "apply the code", "apply the fix", or equivalent — that is explicit
authorization. Proceed immediately using `write_repo_file` without waiting for a script or further
confirmation. Do not re-ask for permission when approval has already been given.

### Apply a change
1. Write the proposed change to `grok_workspace/proposals/<name>.py` (or `.md`)
2. Apply it to the repo file directly using write_workspace_file is NOT allowed for repo files —
   instead, write a shell script to `grok_workspace/scripts/apply_<name>.sh` that patches the file
3. After applying, run one supervisor cycle to verify the process continues without new errors
4. If successful: commit the change on `grok/autoresearch` with a descriptive message
5. If it breaks anything: revert immediately and log the failure to `grok_workspace/analysis/failed_changes.md`

### Commit format
```
fix(autoresearch): <what and why — one line>

Proposed by Grok monitor. Verified by supervisor cycle.
Auto-applied per PROTOCOL.md.
```

### Autonomous scope (same authority as Claude Code CLI)
You have full authority to diagnose, propose, apply, verify, and commit changes to:
- `src/autoresearch/` — training agents, outliner, training manager
- `scripts/autoresearch/` — supervisor, monitor, training scripts
- `src/rag/` — library, acquisition, research librarian
- `src/llm/` — LLM clients and routing (except router.py cross-provider rotation)
- `src/generation/` — content generation workers

### Do NOT change without human approval
- `src/llm/router.py` (cross-provider rotation weights) — ask via chat server first
- `src/api/` (generation pipeline exposed to users)
- `tests/` — do not modify tests without human review

### Questions
Ask through the Cumbersome chat server at http://192.168.1.8:8001/v1
Do NOT use chat.md — it has been replaced by the chat server.

## Verification
A change is considered successful if:
- The supervisor cycle completes with returncode 0
- No new stall-report.json appears in the following cycle
- The targeted worker shows activity (not no_assignments / no_experiments)
