"""grok_agent.py — Agentic Grok loop with file-reading tools.

Gives Grok the ability to read files from the project rather than requiring
the caller to embed large code blocks in the prompt. Grok calls tools as needed,
the loop executes them locally, and returns Grok's final text response.

Available tools Grok can call:
    read_file(path, offset=0, limit=100)   — read N lines from a file
    search_file(path, pattern)             — grep for a regex pattern (returns matches + line numbers)
    list_files(pattern)                    — glob for files matching a pattern
    write_workspace_file(path, content)    — write to grok_workspace/ or competition-pivot/

Usage:
    from src.llm.grok_agent import run_grok_agent

    result = run_grok_agent(
        task="Analyze _theme_key() in real_section_generator.py and describe the ordering issue.",
        model="grok-4-1-fast-reasoning",
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
_COMPETITION_PIVOT_ROOT = _PROJECT_ROOT / "competition-pivot"  # competition-pivot docs
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
    """Write content to a file inside grok_workspace/ or competition-pivot/. Creates parent dirs as needed."""
    p = Path(path)
    # Strip leading path prefixes if Grok includes them
    if str(p).startswith("grok_workspace/"):
        p = Path(str(p)[len("grok_workspace/"):])
        target = (_WORKSPACE_ROOT / p).resolve()
    elif str(p).startswith("competition-pivot/"):
        p = Path(str(p)[len("competition-pivot/"):])
        target = (_COMPETITION_PIVOT_ROOT / p).resolve()
    else:
        # Default: try workspace first, then competition-pivot based on resolved path
        ws_target = (_WORKSPACE_ROOT / p).resolve()
        cp_target = (_COMPETITION_PIVOT_ROOT / p).resolve()
        if str(ws_target).startswith(str(_WORKSPACE_ROOT)):
            target = ws_target
        elif str(cp_target).startswith(str(_COMPETITION_PIVOT_ROOT)):
            target = cp_target
        else:
            return "ERROR: write blocked — path outside grok_workspace/ and competition-pivot/"

    in_workspace = str(target).startswith(str(_WORKSPACE_ROOT))
    in_pivot = str(target).startswith(str(_COMPETITION_PIVOT_ROOT))
    if not (in_workspace or in_pivot):
        return "ERROR: write blocked — path outside grok_workspace/ and competition-pivot/"
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
    """
    DISABLED — direct repo writes require Claude Code CLI authorization.

    Grok must use the proposal flow instead:
      1. Write full file content to grok_workspace/proposals/<name>.py
      2. Write justification to grok_workspace/proposals/<name>.md
      3. Write grok_workspace/notifications/pending_approval.md
      4. Stop — Claude Code CLI will review and apply.

    This rule exists because Grok's Fix4 and Fix5 both wrote invalid Python,
    silently breaking the outliner for 258 minutes.
    """
    p = Path(path)
    rel = str(p)
    if rel.startswith(str(_PROJECT_ROOT)):
        rel = rel[len(str(_PROJECT_ROOT)):].lstrip("/")

    return (
        f"BLOCKED: write_repo_file is disabled. Direct repo writes require Claude Code CLI authorization.\n"
        f"To propose a change to '{rel}':\n"
        f"  1. write_workspace_file('proposals/{Path(rel).stem}.py', <full file content>)\n"
        f"  2. write_workspace_file('proposals/{Path(rel).stem}.md', <justification>)\n"
        f"  3. write_workspace_file('notifications/pending_approval.md', "
        f"'PROPOSAL READY: {Path(rel).stem}\\nFile: {rel}\\nSummary: <one sentence>')\n"
        f"Claude Code CLI will review, validate syntax, and apply if safe."
    )


def _query_db(sql: str, db_path: str | None = None) -> str:
    """
    Run a read-only SQL SELECT query against a project SQLite database.
    Only SELECT statements are allowed. Returns tab-separated rows with a header.
    """
    import sqlite3
    sql_stripped = sql.strip()
    if not sql_stripped.upper().startswith("SELECT"):
        return "ERROR: only SELECT queries are permitted"

    # Default to registry.db at project root; allow explicit path within project
    if db_path:
        target = (_PROJECT_ROOT / db_path).resolve()
        if not str(target).startswith(str(_PROJECT_ROOT)):
            return "ERROR: db_path outside project root"
    else:
        target = _PROJECT_ROOT / "registry.db"

    if not target.exists():
        # Try alternate location
        alt = Path.home() / "Library" / "Application Support" / "DevG" / "devg_registry.sqlite3"
        if alt.exists():
            target = alt
        else:
            return f"ERROR: database not found at {target} or {alt}"

    try:
        con = sqlite3.connect(str(target), timeout=10)
        con.row_factory = sqlite3.Row
        cur = con.execute(sql_stripped)
        rows = cur.fetchall()
        if not rows:
            return "0 rows returned"
        header = "\t".join(rows[0].keys())
        lines = [header, "-" * len(header)]
        for row in rows[:200]:  # cap at 200 rows
            lines.append("\t".join(str(v) if v is not None else "NULL" for v in row))
        if len(rows) == 200:
            lines.append("... (truncated at 200 rows)")
        return "\n".join(lines)
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
    "query_db": lambda args: _query_db(args["sql"], args.get("db_path")),
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
                "Write a file to grok_workspace/ or competition-pivot/. "
                "grok_workspace/ is your persistent working directory for proposals, analysis, tasks, and scripts. "
                "competition-pivot/ is the shared competition planning directory for tracking docs, "
                "gate results, design briefs, and audit entries. "
                "To write to grok_workspace/: use paths like 'proposals/fix_outliner.py' or prefix with 'grok_workspace/'. "
                "To write to competition-pivot/: prefix path with 'competition-pivot/', e.g. 'competition-pivot/stage1-design-brief.md'. "
                "These are the ONLY locations you can write to."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path within grok_workspace/ or competition-pivot/, e.g. 'proposals/fix_density_check.py', 'grok_workspace/tasks/todo.md', or 'competition-pivot/stage-gate-tracker.md'"},
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
    {
        "type": "function",
        "function": {
            "name": "query_db",
            "description": (
                "Run a read-only SELECT query against the project SQLite database (registry.db). "
                "Use this to get raw experiment counts, pass rates, streaks, and status buckets "
                "directly from the source of truth. Only SELECT is allowed — no writes. "
                "Returns tab-separated rows with a header row. "
                "Key table: autoresearch_experiments (cols: worker_name, status, passage_reference, "
                "score, created_at_utc, completed_at_utc). "
                "Status values: 'pass', 'fail', 'assigned' (in-flight). "
                "Example: SELECT worker_name, COUNT(*) as total, "
                "SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passes "
                "FROM autoresearch_experiments GROUP BY worker_name;"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT query to run"},
                    "db_path": {
                        "type": "string",
                        "description": "Optional path to database file relative to project root (default: registry.db)",
                    },
                },
                "required": ["sql"],
            },
        },
    },
]


def run_grok_agent(
    task: str,
    *,
    model: str = "grok-4-1-fast-reasoning",
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
        "CRITICAL — file writing: When calling write_workspace_file, the content field "
        "must be raw text exactly as it should appear on disk. Never HTML-encode content. "
        "Write `\"` not `&quot;`, `>` not `&gt;`, `&` not `&amp;`. Python source files "
        "written with HTML entities are not valid Python and will be rejected.\n\n"
        "IMPORTANT: At the end of every session, update grok_workspace/MEMORY.md using "
        "write_workspace_file with the latest system state (outliner status, graduated workers, "
        "bottleneck, library count, any fixes applied). This is your only persistent memory.\n\n"
        + (f"## Your persistent memory:\n{_memory}" if _memory else "")
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
