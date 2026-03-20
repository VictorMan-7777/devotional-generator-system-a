# Grok Workspace

This directory is Grok's persistent working space. Grok has write access here only.
The rest of the repository is read-only from Grok's perspective.

## Directories

- **scripts/** — runnable monitoring/analysis scripts Grok wants to persist and reuse
- **proposals/** — code change proposals for human (Claude) review before applying to the main repo
- **analysis/** — analysis notes, findings, and reports from monitoring passes

## Rules

- Grok reads from anywhere in the repo but writes ONLY to this directory
- Proposals in `proposals/` are reviewed by the human before any changes go to the main repo
- Scripts in `scripts/` can be run by the training supervisor or manually
- Nothing in this directory is auto-applied to the main codebase

## Format for proposals/

Name files as: `{timestamp}_{description}.py` or `{timestamp}_{description}.md`
Include at the top:
- Target file in main repo
- What changes and why
- Urgency: blocking | high | medium | low
