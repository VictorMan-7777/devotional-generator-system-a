---
name: Physical Architecture (machines and roles)
description: Where each component actually runs — MacBook hosts repo, Mac Studio runs long-running processes, cloud APIs for LLMs
type: project
---

## Current state (as of 2026-03-21)

**Mac Studio** — this is where Claude Code CLI runs
- All processes launch here: training supervisor, web monitor (ports 8765/8766), Grok daemon
- Mounts the MacBook's SMB share at `/Volumes/claude-projects/...` — files look local but live on the MacBook
- Calls out to cloud APIs (Grok/xAI, Anthropic LLM trainers) from here

**MacBook**
- Hosts the repo files; shares them to the Mac Studio via SMB
- `/Volumes/claude-projects/projects/devotional-generator-system-a/` on the Studio is the MacBook's repo

**Cloud APIs**
- Grok (xAI API) — training assistant being trained; called from Mac Studio
- LLM trainers (Anthropic API) — exposition_writer, outliner trainers etc.; called from Mac Studio

**NAS (192.168.1.8)**
- Not yet in use for DevG
- Migration planned post-competition (see `docs/system/nas-migration-plan.md`)
- Will eventually hold canonical DBs and data

## How to apply

- Bash commands and process launches execute on the Mac Studio (where Claude Code runs)
- File edits go through the SMB mount — changes are immediately visible to all Studio processes
- Never assume the NAS is running anything until migration is complete
