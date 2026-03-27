#!/usr/bin/env python3
import sqlite3
import json
import time
import subprocess
import os
import sys
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

# Setup basic logging to stdout first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def get_project_root():
    return Path(__file__).resolve().parents[2]

PROJECT_ROOT = get_project_root()
PYTHON = str(PROJECT_ROOT / ".venv" / "bin" / "python")
GROK_WORKSPACE = PROJECT_ROOT / 'grok_workspace'
DB_PATH = PROJECT_ROOT / 'registry.db'

sys.path.insert(0, str(PROJECT_ROOT))
from src.llm.grok_agent import run_grok_agent

def read_todo_md() -> str:
    """Read grok_workspace/TODO.md content."""
    todo_path = GROK_WORKSPACE / 'TODO.md'
    return todo_path.read_text(encoding='utf-8') if todo_path.exists() else ""


def get_top_open_item(todo_text: str, section_name: str):
    """Parse TODO.md for first open [ ] item in given section (e.g. '## URGENT').
    Returns (item_text, full_line) or (None, None)."""
    lines = todo_text.splitlines()
    in_section = False
    for line in lines:
        stripped = line.strip()
        if section_name in stripped:
            in_section = True
            continue
        if in_section and stripped.startswith('---'):
            return None, None
        if in_section and stripped.startswith('- [ ]'):
            text = stripped[5:].strip()
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
            return text.strip(), line.strip()
    return None, None


def read_memory():
    memory_path = GROK_WORKSPACE / 'MEMORY.md'
    if memory_path.exists():
        return memory_path.read_text()
    return "No memory file found."

def read_recent_chat_directives(max_lines: int = 80) -> str:
    """Return the last max_lines of chat.md so Claude's directives reach cycle decisions."""
    chat_path = GROK_WORKSPACE / 'chat.md'
    if not chat_path.exists():
        return ""
    lines = chat_path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-max_lines:])

def list_proposals():
    proposals_dir = GROK_WORKSPACE / 'proposals'
    if proposals_dir.exists():
        return [f.name for f in proposals_dir.iterdir() if f.suffix == '.py']
    return []

def get_db_state():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Workers total stats
    cur.execute("""
        SELECT worker_name, 
               COUNT(*) as total,
               SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passes,
               SUM(CASE WHEN status='fail' THEN 1 ELSE 0 END) as fails,
               SUM(CASE WHEN status='assigned' THEN 1 ELSE 0 END) as assigned
        FROM autoresearch_experiments 
        GROUP BY worker_name
    """)
    workers_total = {row['worker_name']: dict(row) for row in cur.fetchall()}

    # Recent 24h completed
    cur.execute("""
        SELECT COUNT(*) as recent FROM autoresearch_experiments 
        WHERE completed_at_utc > datetime('now', '-24 hours')
    """)
    recent = cur.fetchone()['recent']

    # Assigned stalls
    cur.execute("""
        SELECT worker_name, benchmark_reference, created_at_utc,
               (strftime('%s','now') - strftime('%s',created_at_utc)) / 3600.0 as age_hours
        FROM autoresearch_experiments 
        WHERE status='assigned'
        ORDER BY created_at_utc ASC
    """)
    stalls = [dict(row) for row in cur.fetchall()]

    # Recent stats per worker
    recent_stats = {}
    for worker in workers_total:
        cur.execute("""
            SELECT status FROM autoresearch_experiments 
            WHERE worker_name=? 
            ORDER BY created_at_utc DESC 
            LIMIT 100
        """, (worker,))
        recent_exps = [row['status'] for row in cur.fetchall()]
        total_recent = len(recent_exps)
        passes_recent = recent_exps.count('pass')
        pass_rate = round((passes_recent / total_recent * 100), 1) if total_recent else 0

        consec_fails = 0
        for st in recent_exps:  # most recent first
            if st != 'fail':
                break
            consec_fails += 1

        recent_stats[worker] = {
            'total_recent': total_recent,
            'pass_rate_%': pass_rate,
            'consec_fails_recent': consec_fails
        }

    conn.close()
    return {
        'workers_total': workers_total,
        'recent_throughput_24h': recent,
        'assigned_stalls': stalls,
        'recent_stats': recent_stats
    }

def call_grok_decisions(db_state, memory, proposals, chat_directives: str = "", todo_text: str = ""):
    state_str = json.dumps(db_state, default=str, indent=2)

    chat_section = ""
    if chat_directives.strip():
        chat_section = f"\nRecent directives from Claude (chat.md — tail):\n{chat_directives}\n"

    todo_section = ""
    if todo_text.strip():
        todo_section = f"\nTODO.md (open items for awareness):\n{todo_text[-3000:]}\n"

    user_prompt = f"""
Current DB state:
{state_str}

Grok MEMORY.md:
{memory}
{chat_section}{todo_section}
Pending proposals in grok_workspace/proposals/:
{proposals}

Task: Identify stalls, low pass rates (<50%), high consec fails (>5), old assigned (>1h), backlogs.

Decide 1-5 actions to unblock.

Output ONLY JSON array of objects like:
[
  {{"action": "run_worker", "worker": "outliner"}},
  {{"action": "flag_proposal", "proposal": "fix_outliner.py", "reason": "fix consec fails"}},
  {{"action": "operator_note", "message": "Outliner stalled — review logs"}},
  {{"action": "noop"}}  // if healthy
]

Worker names for run_worker: outliner, exposition_writer, etc. (matches run_{{worker}}_training_cycle.py script name without run_/._training_cycle.py)
flag_proposal: filename in proposals/
"""
    
    try:
        # Call Grok directly without tools — state is in the prompt, no file reads needed.
        # Using run_grok_agent with tools causes it to attempt tool calls before responding,
        # which wastes the single allowed round before returning the fallback string.
        import openai
        from src.llm.grok_client import _load_dotenv
        _load_dotenv()
        client = openai.OpenAI(api_key=os.environ.get("XAI_API_KEY"), base_url="https://api.x.ai/v1")
        response = client.chat.completions.create(
            model="grok-4-1-fast-reasoning",
            max_tokens=1000,
            messages=[
                {"role": "system", "content": "You are the DevG supervisor. Output ONLY a valid JSON array. No prose, no explanation."},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content.strip()

        m = re.search(r"\[.*\]", content, re.DOTALL)
        content = m.group(0) if m else content
        actions = json.loads(content)
        if not isinstance(actions, list):
            raise ValueError("Not a list")
        return actions
    except Exception as e:
        logger.error(f"Grok decision error: {e}")
        return []

def execute_actions(actions):
    for action in actions:
        logger.info(f"Action: {json.dumps(action)}")
        act = action['action']
        try:
            if act == 'run_worker':
                worker = action['worker']
                # DB worker names don't always match script names; normalize here
                _WORKER_SCRIPT_MAP = {
                    'exposition_writer': 'exposition',
                    'be_still_writer': 'be_still',
                }
                script_worker = _WORKER_SCRIPT_MAP.get(worker, worker)
                script_path = PROJECT_ROOT / 'scripts' / 'autoresearch' / f"run_{script_worker}_training_cycle.py"
                if script_path.exists():
                    env = {**os.environ}
                    env_local = PROJECT_ROOT / ".env.local"
                    if env_local.exists():
                        for line in env_local.read_text().splitlines():
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, _, v = line.partition("=")
                                env[k.strip()] = v.strip()
                    cmd = [PYTHON, str(script_path)]
                    if worker == "outliner":
                        cmd += ["--limit", "1"]
                    logger.info(f"Running {worker} (sequential, timeout=1800s)")
                    result = subprocess.run(
                        cmd, cwd=PROJECT_ROOT, env=env, timeout=1800,
                        start_new_session=True
                    )
                    logger.info(f"Worker {worker} exited rc={result.returncode}")
                else:
                    logger.error(f"No script: {script_path}")
            elif act == 'flag_proposal':
                prop = action.get('proposal', 'unknown')
                reason = action.get('reason', '')
                logger.warning(f"*** PROPOSAL FLAG HIGH PRIORITY: {prop} {reason} ***")
            elif act == 'operator_note':
                msg = action.get('message', action.get('note', 'no message'))
                logger.warning(f"*** OPERATOR: {msg} ***")
            elif act == 'noop':
                logger.info("No action needed.")
            else:
                logger.warning(f"Unknown action: {action}")
        except subprocess.TimeoutExpired:
            logger.error(f"Worker {action.get('worker', '?')} timed out — skipping, continuing with remaining actions.")
        except Exception as e:
            logger.error(f"Action {act} failed: {e} — skipping, continuing with remaining actions.")

def main():
    logs_dir = PROJECT_ROOT / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Add file handler
    fh = logging.FileHandler(logs_dir / 'supervisor.log')
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)
    
    logger.info("DevG Grok Supervisor started. Cycle every 5min.")
    
    while True:
        try:
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            logger.info(f"=== CYCLE START {timestamp} ===")
            
            memory = read_memory()
            proposals = list_proposals()
            db_state = get_db_state()
            todo_text = read_todo_md()

            logger.info(f"Pending proposals ({len(proposals)}): {proposals}")
            logger.info(f"24h throughput: {db_state['recent_throughput_24h']}")
            if db_state['assigned_stalls']:
                logger.info(f"Oldest stall: {json.dumps(db_state['assigned_stalls'][0], default=str)}")

            # === TODO PROCESSING STEP ===
            # URGENT items block Stage 3 — process before worker scheduling
            urgent_item, urgent_line = get_top_open_item(todo_text, '## URGENT')
            if urgent_item:
                logger.warning(f"URGENT TODO BLOCKING: {urgent_item[:100]}")
                todo_prompt = (
                    f"URGENT supervisor cycle TODO item:\n\n{urgent_line}\n\n"
                    "Progress this using your tools. Goal: resolve or make a major advance.\n"
                    "- Use query_db for DB checks.\n"
                    "- Use read_file/search_file for code review.\n"
                    "- Write proposals/*.md for fix designs (Claude applies).\n"
                    "- Update MEMORY.md with status/findings.\n"
                    "Report findings when done."
                )
                try:
                    agent_result = run_grok_agent(task=todo_prompt, max_tool_rounds=20)
                    logger.info(f"TODO WORK (URGENT): {agent_result[:300]}")
                except Exception as e:
                    logger.error(f"TODO WORK (URGENT) agent error: {e}")
            else:
                routine_item, routine_line = get_top_open_item(todo_text, '## ROUTINE')
                if routine_item:
                    logger.info(f"ROUTINE TODO: {routine_item[:100]}")
                    todo_prompt = (
                        f"ROUTINE supervisor cycle TODO item:\n\n{routine_line}\n\n"
                        "Investigate and make progress (5-10 min effort).\n"
                        "Log findings to MEMORY.md. Propose fix in proposals/*.md if needed."
                    )
                    try:
                        agent_result = run_grok_agent(task=todo_prompt, max_tool_rounds=8)
                        logger.info(f"TODO WORK (ROUTINE): {agent_result[:200]}")
                    except Exception as e:
                        logger.error(f"TODO WORK (ROUTINE) agent error: {e}")

            chat_directives = read_recent_chat_directives()
            actions = call_grok_decisions(db_state, memory, proposals, chat_directives, todo_text)
            
            if actions:
                logger.info(f"Actions ({len(actions)}): {json.dumps(actions, indent=2)}")
                execute_actions(actions)
            else:
                logger.info("No actions decided.")
            
            logger.info("=== CYCLE END ===")
            
        except Exception as e:
            logger.error(f"Cycle failed: {e}", exc_info=True)
        
        time.sleep(300)

if __name__ == '__main__':
    main()
