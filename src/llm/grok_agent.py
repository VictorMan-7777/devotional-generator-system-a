"""grok_agent.py — Agentic Grok loop with file-reading tools.

Gives Grok the ability to read files from the project rather than requiring
the caller to embed large code blocks in the prompt. Grok calls tools as needed,
the loop executes them locally, and returns Grok's final text response.

Available tools Grok can call:
    read_file(path, offset=0, limit=100)   — read N lines from a file
    search_file(path, pattern)             — grep for a regex pattern (returns matches + line numbers)
    list_files(pattern)                    — glob for files matching a pattern

Usage:
    from src.llm.grok_agent import run_grok_agent

    result = run_grok_agent(
        task="Analyze _theme_key() in real_section_generator.py and describe the ordering issue.",
        model="grok-4.20-0309-reasoning",
        max_tool_rounds=10,
    )
    print(result)
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WORKSPACE_ROOT = _PROJECT_ROOT / "grok_workspace"  # Grok's write sandbox
_MAX_LINE_LIMIT = 300  # Grok cannot request more than this many lines at once


def _read_file(path: str, offset: int = 0, limit: int = 100) -> str:
    """Read up to `limit` lines from `path` starting at line `offset` (0-based)."""
    limit = min(limit, _MAX_LINE_LIMIT)
    p = Path(path)
    target = p.resolve() if p.is_absolute() else (_PROJECT_ROOT / path).resolve()
    in_project = str(target).startswith(str(_PROJECT_ROOT))
    in_tmp = str(target).startswith("/tmp/")
    if not (in_project or in_tmp):
        return "ERROR: path outside project root or /tmp"
    if not target.exists():
        return f"ERROR: file not found: {path}"
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
        chunk = lines[offset: offset + limit]
        numbered = "\n".join(f"{offset + i + 1:>5}  {line}" for i, line in enumerate(chunk))
        total = len(lines)
        return f"[{path} lines {offset+1}–{offset+len(chunk)} of {total}]\n{numbered}"
    except Exception as exc:
        return f"ERROR: {exc}"


def _search_file(path: str, pattern: str) -> str:
    """Search `path` for lines matching `pattern` (regex). Returns matched lines with numbers."""
    target = (_PROJECT_ROOT / path).resolve()
    if not str(target).startswith(str(_PROJECT_ROOT)):
        return "ERROR: path outside project root"
    if not target.exists():
        return f"ERROR: file not found: {path}"
    try:
        result = subprocess.run(
            ["grep", "-n", "-E", pattern, str(target)],
            capture_output=True, text=True, timeout=10,
        )
        out = result.stdout.strip()
        return out if out else f"No matches for pattern: {pattern}"
    except Exception as exc:
        return f"ERROR: {exc}"


def _write_workspace_file(path: str, content: str) -> str:
    """Write content to a file inside grok_workspace/. Creates parent dirs as needed."""
    p = Path(path)
    # Strip leading grok_workspace/ if Grok includes it
    if str(p).startswith("grok_workspace/"):
        p = Path(str(p)[len("grok_workspace/"):])
    target = (_WORKSPACE_ROOT / p).resolve()
    if not str(target).startswith(str(_WORKSPACE_ROOT)):
        return "ERROR: write blocked — path outside grok_workspace/"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = target.relative_to(_PROJECT_ROOT)
        return f"OK: wrote {len(content)} bytes to {rel}"
    except Exception as exc:
        return f"ERROR: {exc}"


_ALLOWED_WRITE_PREFIXES = (
    "src/autoresearch/",
    "src/rag/",
    "src/llm/",
    "src/generation/",
    "scripts/autoresearch/",
)


def _write_repo_file(path: str, content: str) -> str:
    """Write content to an allowed repo file. Scoped to Grok's autonomous change directories."""
    p = Path(path)
    # Normalise — strip leading slash or project root prefix
    rel = str(p)
    if rel.startswith(str(_PROJECT_ROOT)):
        rel = rel[len(str(_PROJECT_ROOT)):].lstrip("/")
    target = (_PROJECT_ROOT / rel).resolve()
    if not str(target).startswith(str(_PROJECT_ROOT)):
        return "ERROR: write blocked — path outside project root"
    if not any(rel.startswith(prefix) for prefix in _ALLOWED_WRITE_PREFIXES):
        return (
            f"ERROR: write blocked — {rel!r} is outside Grok's autonomous scope. "
            f"Allowed: {', '.join(_ALLOWED_WRITE_PREFIXES)}"
        )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} bytes to {rel}"
    except Exception as exc:
        return f"ERROR: {exc}"


def _list_files(pattern: str) -> str:
    """List files matching a glob pattern relative to the project root, or absolute."""
    p = Path(pattern)
    if p.is_absolute():
        matches = glob.glob(pattern, recursive=True)
        rel = sorted(matches)
    else:
        matches = glob.glob(str(_PROJECT_ROOT / pattern), recursive=True)
        rel = sorted(str(Path(m).relative_to(_PROJECT_ROOT)) for m in matches)
    return "\n".join(rel) if rel else f"No files matched: {pattern}"


_TOOL_HANDLERS = {
    "read_file": lambda args: _read_file(
        args["path"], int(args.get("offset", 0)), int(args.get("limit", 100))
    ),
    "write_workspace_file": lambda args: _write_workspace_file(args["path"], args["content"]),
    "write_repo_file": lambda args: _write_repo_file(args["path"], args["content"]),
    "search_file": lambda args: _search_file(args["path"], args["pattern"]),
    "list_files": lambda args: _list_files(args["pattern"]),
}

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read lines from a project file. Use offset+limit to page through large files. "
                f"Maximum {_MAX_LINE_LIMIT} lines per call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to project root, e.g. src/generation/real_section_generator.py"},
                    "offset": {"type": "integer", "description": "0-based line offset to start reading from (default 0)"},
                    "limit": {"type": "integer", "description": f"Number of lines to read (default 100, max {_MAX_LINE_LIMIT})"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_workspace_file",
            "description": (
                "Write a file to grok_workspace/ — your persistent working directory. "
                "Use this to save scripts, proposals, analysis notes, and tasks you want to keep. "
                "Subdirs: scripts/ (runnable scripts), proposals/ (code changes for human review), "
                "analysis/ (findings/notes), tasks/ (your own task list). "
                "You can organise these however you like — create new subdirs freely. "
                "Path is relative to grok_workspace/ (e.g. 'proposals/fix_outliner.py'). "
                "This is the ONLY location you can write to."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path within grok_workspace/, e.g. 'proposals/fix_density_check.py' or 'tasks/todo.md'"},
                    "content": {"type": "string", "description": "Full file content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_repo_file",
            "description": (
                "Write a file directly to the repository. Scoped to Grok's autonomous change directories: "
                "src/autoresearch/, src/rag/, src/llm/, src/generation/, scripts/autoresearch/. "
                "Use this to apply fixes directly. Always verify via a supervisor cycle after writing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to project root, e.g. 'src/autoresearch/outliner_training_agent.py'"},
                    "content": {"type": "string", "description": "Full file content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_file",
            "description": "Search a file for lines matching a regex pattern. Returns matching lines with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to project root"},
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                },
                "required": ["path", "pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files matching a glob pattern relative to the project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. src/**/*.py"},
                },
                "required": ["pattern"],
            },
        },
    },
]


def run_grok_agent(
    task: str,
    *,
    model: str = "grok-4.20-0309-reasoning",
    max_tokens: int = 8000,
    max_tool_rounds: int = 15,
    system: str | None = None,
) -> str:
    """Run Grok with file-reading tools. Returns the final text response.

    Args:
        task: The task description / question for Grok.
        model: Grok model to use.
        max_tokens: Max output tokens.
        max_tool_rounds: Safety limit on tool call iterations.
        system: Optional system prompt override.
    """
    from src.llm.grok_client import _load_dotenv
    _load_dotenv()  # populate XAI_API_KEY from .env before reading it

    try:
        import openai
    except ImportError as exc:
        raise ImportError("openai package required: pip install openai") from exc

    api_key = os.environ.get("XAI_API_KEY")
    client = openai.OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

    # Load persistent memory file if present
    _memory_path = _PROJECT_ROOT / "grok_workspace" / "MEMORY.md"
    _memory = ""
    if _memory_path.exists():
        try:
            _memory = _memory_path.read_text(encoding="utf-8")
        except Exception:
            pass

    _system = system or (
        "You are Grok, autonomous monitor and engineer for the DevG devotional content "
        "generation system. Use the provided file tools to read only what you need. "
        "When you have enough information, return your complete answer — code blocks "
        "where code is required, prose where analysis is required.\n\n"
        + (f"## Your persistent memory (update grok_workspace/MEMORY.md when state changes):\n{_memory}" if _memory else "")
    )

    messages: list[dict] = [
        {"role": "system", "content": _system},
        {"role": "user", "content": task},
    ]

    for round_num in range(max_tool_rounds):
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            tools=_TOOL_SCHEMAS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_unset=True))

        # No tool calls — Grok is done.
        if not msg.tool_calls:
            return msg.content or ""

        # Execute each tool call and feed results back.
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            handler = _TOOL_HANDLERS.get(fn_name)
            result = handler(args) if handler else f"ERROR: unknown tool {fn_name!r}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return f"[Agent stopped after {max_tool_rounds} tool rounds — partial response may follow]\n{messages[-1].get('content', '')}"
