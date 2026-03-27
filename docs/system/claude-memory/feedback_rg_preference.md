---
name: Use rg not grep
description: User prefers rg (ripgrep) over grep in all shell commands
type: feedback
---

Always use `rg` instead of `grep` in Bash commands.

**Why:** Personal preference.

**How to apply:** Any time a shell search command is needed, use `rg` instead of `grep`. The Grep tool is fine (it uses rg internally), but in Bash commands write `rg`, not `grep`.
