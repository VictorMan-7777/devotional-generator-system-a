# Devotional Generator System A

Python application for generating KDP-ready devotional books.

## Start Here (Approvals)

Use this command to review pending approvals in UI mode (CLI launches UI):

```bash
python3 scripts/review/run_review.py --report outputs/devotionals/<run>__approval-gate-report.json
```

UI shortcuts: `A` approve, `R` reject, `S` skip (leave pending), `Left/Right` navigate, `Q` quit/resume later.

## Full Pipeline Run (CSV -> DB -> Validation -> Review Bundle)

```bash
python3 scripts/run_devotional_full.py --csv /path/to/series-volume.csv --row 1
```

This creates a production-parity run bundle in `outputs/devotionals/`:
- `__book.json` (full generated devotional content)
- `__agent-validation-report.json` (independent validator-agent artifact)
- `__approval-gate-report.json` (includes pending sections and content previews)
- `__kdp-personal-preview.pdf` (generated preview PDF)
- `__meta.json` (artifact index + ready-to-run review commands)

Notes:
- Full run defaults to production generator (`--generator real`).
- Debug generator usage requires explicit opt-in: `--generator mock --allow-nonprod-generator`.
- Optional scripture import fallback: `--scripture-import /path/to/scripture.csv`

Fallbacks:

```bash
# Browser-based local UI fallback (Safari works):
python3 scripts/review/run_review.py --backend web --report outputs/devotionals/<run>__approval-gate-report.json

# Terminal-only interactive fallback
python3 scripts/review/run_review.py --backend cli --report outputs/devotionals/<run>__approval-gate-report.json

# Batch actions
python3 scripts/review/run_review.py --backend reject-all --report outputs/devotionals/<run>__approval-gate-report.json

# Debug-only (explicit opt-in): batch approve all
python3 scripts/review/run_review.py --backend approve-all --allow-batch-approve --report outputs/devotionals/<run>__approval-gate-report.json

# Reviewer metadata (defaults to Victor)
python3 scripts/review/run_review.py --reviewed-by "Victor" --report outputs/devotionals/<run>__approval-gate-report.json

# Agent reviewers must include decision source
python3 scripts/review/run_review.py --reviewed-by "agent:verifier-1" --decision-source "secondary_source_crosscheck" --report outputs/devotionals/<run>__approval-gate-report.json
```

Detached full-UI track (not wired into default runner yet):

```bash
python3 scripts/review/run_review_studio.py --report outputs/devotionals/<run>__approval-gate-report.json
```

This opens a browser studio with dark mode, local-time display, and WYSIWYG draft editing. It writes normal approval decisions plus a separate `__review-edits.json` file for draft edits.

Optional: include a DevotionalBook JSON to show read-only section body previews while reviewing:

```bash
python3 scripts/review/run_review_studio.py --report outputs/devotionals/<run>__approval-gate-report.json --book-json outputs/devotionals/<run>__book.json
```

## Training System

DevG trains itself using AI agents (Claude or Codex) that generate content on benchmark passages, which is then scored and logged. Over time the scoring data improves the deterministic templates until the AI calls are no longer needed.

**All positions called "agent" make real AI calls. No exceptions.** See `docs/system/devg-autoresearch-implementation-plan.md` for full architecture.

### Starting the training loop

```bash
scripts/autoresearch/devg-start-training-loop
scripts/autoresearch/devg-watch        # live dashboard
```

### LLM configuration

```bash
export ANTHROPIC_API_KEY=sk-...        # Claude (default provider)
export OPENAI_API_KEY=sk-...           # Codex (optional, for load splitting)
export DEVG_LLM_PROVIDER=claude        # or "codex"
export DEVG_LLM_OUTLINER=codex         # per-worker override (optional)
```

### Suspending training

Set `SUPERVISOR_SUSPENDED["enabled"] = True` in `scripts/autoresearch/run_training_supervisor.py`. Monitoring workers (theological reviewer, library trainer, policy guardian) continue running. Content generation halts.

### Policy guardian

The policy guardian is a compliance cop, not an AI agent. It enforces the rules-laws constitution and federal laws (L2, L15) as written. It does not interpret or extrapolate. When it finds situations the law doesn't cover, it writes a proposed-rule annotation to `rules-laws/proposed/`.

## Project Status

Active development — Training system, review flow, validation, and RAG infrastructure in progress.

## Setup

```bash
pip install -e ".[dev]"
pip install anthropic          # required for Claude LLM calls in training
pip install openai             # optional, for Codex routing
```

## Testing

```bash
pytest tests/
```
