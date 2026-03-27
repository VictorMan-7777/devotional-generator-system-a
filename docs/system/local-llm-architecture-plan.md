# Local LLM Architecture Plan
_Written: 2026-03-19. For retrieval after NAS migration by a new Claude CLI session._

---

## Overview

Replace Anthropic/OpenAI API calls for training with a local LLM running on the Mac Studio.
All data lives on the NAS. MacBook runs the DevG application and training loop.

**Why:** ~$25/week Anthropic + ~$10/week OpenAI with zero measurable training improvement.
A local model eliminates API cost entirely, removes rate limits, and allows unlimited iteration.

---

## Architecture

```
MacBook                    Mac Studio                 NAS
──────────                 ──────────                 ───
Training loop         →    Ollama (LLM server)        SQLite DB (devg_registry.sqlite3)
Supervisor            →    Socket server (DB layer)   Library / RAG index
Worker scripts             Model: Mistral/Llama 3     Artifacts / outputs (docs/, outputs/)
                                                       Scripture data
```

---

## Why Each Machine Does Its Job

### MacBook — Application + Orchestration
The training loop, supervisor, and worker scripts are lightweight Python. No reason to
tie up the Studio's resources running orchestration. MacBook handles all code execution.

### Mac Studio — LLM Inference + DB Socket Server
Two reasons the Studio is the right place for both services:

1. **LLM inference** — Apple Silicon unified memory architecture makes local model inference
   fast and efficient. A 7B–8B model runs in ~5GB of RAM, leaving plenty for other tasks.
   The Studio handles this trivially.

2. **Socket server** — SQLite over SMB under write-heavy load (training loop writing every
   20 seconds) causes disk I/O errors. We have already seen these in this project. The fix
   is to run the DevG socket server on the machine with the fastest direct NAS connection.
   The Studio connects to the NAS via 10GbE or Thunderbolt ethernet; all DB writes are
   serialized there and never cross SMB under write contention.

### NAS — All Persistent Data
- `data/devg_registry.sqlite3` — experiment store, registry
- `data/library/` — RAG index, library catalog
- `outputs/devotionals/` — generated artifacts, PDFs
- Scripture data, seed files, training outputs

---

## Setup Steps

### 1. Mac Studio: Install Ollama

```bash
# Install
brew install ollama

# Configure to accept LAN connections (not just localhost)
# Add to ~/.zshrc or launchd plist:
export OLLAMA_HOST=0.0.0.0

# Pull the starting model
ollama pull mistral        # 4GB, fast, strong JSON output
# or
ollama pull llama3.1:8b    # 5GB, strong reasoning

# Start the server
ollama serve
```

Ollama will be available at `http://mac-studio.local:11434` from the MacBook.

### 2. Mac Studio: Start the DevG Socket Server

The socket server must start on the Studio (not the MacBook) so all DB writes go through
a process with direct NAS access.

```bash
# On Mac Studio, from the repo directory (NAS mount)
.venv/bin/python scripts/start_socket_server.py
# or however the socket server is started in this project
```

Confirm the socket server is listening and the MacBook can reach it before starting training.

### 3. MacBook: Set Environment Variables

Add to `~/.zshrc` on the MacBook:

```bash
# Point LLM calls to the Studio
export DEVG_LLM_BASE_URL=http://mac-studio.local:11434
export DEVG_LLM_PROVIDER=ollama   # or whatever the provider name becomes

# Point DB to NAS (if socket server is not used) or Studio socket address
export DEVG_DB_PATH=/Volumes/nas/devg/data/devg_registry.sqlite3
# If using socket server:
# export DEVG_SOCKET_HOST=mac-studio.local
```

### 4. Add Ollama Client to DevG

A new `src/llm/ollama_client.py` needs to be written. It will:
- Call `http://{DEVG_LLM_BASE_URL}/v1/chat/completions` (Ollama is OpenAI-compatible)
- Or use `ollama` Python package directly
- Implement the same `generate(prompt: str) -> str` interface as `ClaudeLLMClient`
- Register in `src/llm/router.py` under provider name `"ollama"`

This is the only new code required. Everything else stays the same.

### 5. Disable Sleep on Mac Studio During Training

The MacBook training loop will fail if the Studio sleeps and Ollama becomes unreachable.

```
System Settings → Energy → Prevent automatic sleeping when display is off → ON
# Or use caffeinate:
caffeinate -s &
```

---

## Model Selection

Start here. Do not over-engineer the model choice before frozen metrics are defined.

| Model | RAM | Speed | Notes |
|-------|-----|-------|-------|
| Mistral 7B Q4 | ~4GB | Very fast | Strong instruction following, good JSON |
| Llama 3.1 8B Q4 | ~5GB | Fast | Better reasoning than Mistral 7B |
| Llama 3.1 70B Q4 | ~40GB | Slower | Needs 64GB+ Mac Studio; much stronger |

**Recommendation:** Start with `mistral` or `llama3.1:8b`. The training loop runs evaluations
constantly — speed matters more than raw capability at this stage. Upgrade to 70B only if
the smaller model demonstrably fails at the frozen metric tasks after real experimentation.

---

## What Does NOT Change

- All worker scripts (`run_outliner_training_cycle.py`, etc.) — unchanged
- Experiment store schema — unchanged
- Supervisor logic — unchanged
- Benchmark passages and scoring harness — unchanged
- The `generate(prompt: str) -> str` interface contract — unchanged

The only change is which `LLMClient` implementation is used, and where it points.

---

## The Constraint: Frozen Metrics First

**Do not restart training until frozen metrics are defined.**

See `docs/system/autoresearch-architecture-reset.md` for full context.

The local LLM does not solve the "insanity loop" problem by itself. The loop was insane
because there was no frozen ground truth — the LLM trainer was both proposing changes
and judging whether they worked. A local model running the same loop produces the same
insanity at zero API cost.

The correct order:

1. ✅ NAS migration complete
2. ✅ Ollama running on Studio
3. ⏳ Operator defines frozen metrics for each worker (Be Still, Action Steps, Exposition, Outliner)
4. ⏳ Frozen metric implemented as deterministic Python scoring functions
5. ⏳ Training loop updated: LLM proposes → deterministic score decides → keep or reject
6. ⏳ Restart training

---

## Key Principle (from ChatGPT architecture review)

> LLMs should PROPOSE. System should DECIDE.

The local LLM generates candidate changes or content. The frozen metric (a Python function,
not another LLM) decides whether the change was an improvement. The LLM never judges its
own output.

---

## Questions to Resolve in the Post-Migration Session

1. What are the frozen metrics for each worker? (Operator was thinking about this during migration)
2. Does the DevG socket server already handle remote connections, or does it need to be updated?
3. What is the NAS mount path on both machines? (Update `DEVG_DB_PATH` accordingly)
4. Should Ollama replace all LLM calls (training + pipeline), or just training?

---

_End of document. Written 2026-03-19 before NAS migration._
