#!/usr/bin/env python3
"""DevG v3 — Final safe_f scalar/tuple."""

import http.server
import socketserver
import sqlite3
import threading
import socket
import glob
import os
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "registry.db"
HUMAN_PORT = 8765
CLAUDE_PORT = 8766
REFRESH_SECS = 60

TRAINING_WORKERS = {
    "acquisition_librarian", "research_librarian", "outliner", "exposition_writer",
    "quote_selector", "be_still_writer", "action_writer", "prayer_writer"
}

_human_cache = None
_claude_cache = None
cache_lock = threading.Lock()

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except:
        return "localhost"
    finally:
        s.close()

def query(sql, params=()):
    try:
        conn = sqlite3.connect(str(DB), timeout=15)
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    except Exception as e:
        print(f"Query err: {e}")
        return [("ERR", str(e))]

def safe_f(v):
    # Handle scalar or tuple[row]
    if isinstance(v, (list, tuple)):
        if not v or len(v) == 0 or v[0] is None:
            return 0.0
        v = v[0]
    if v is None or str(v).startswith(('ERR', 'QUERY_ERROR')) or not isinstance(v, (int, float, str)):
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0

def stat_p(p: Path):
    try:
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        return f"{p.name} (mod {mtime})"
    except:
        return f"{p.name} (err)"

def nw_c(pattern):
    # Use max() on filename (timestamps are embedded) — avoids per-file stat() over SMB
    files = glob.glob(str(REPO / "docs/system/outputs" / pattern))
    return Path(max(files)) if files else None

def claude_sources():
    lines = [f"<b>DB:</b> {stat_p(DB)}"]
    for lbl, pat in [
        ("Supervisor", "*training-supervisor-cycle.json"),
        ("Outliner", "*outliner-training-cycle.json"),
        ("Expo", "*exposition-training-cycle.json"),
        ("Be Still", "*be_still-training-cycle.json"),
        ("Action", "*action-training-cycle.json"),
        ("Prayer", "*prayer-training-cycle.json")
    ]:
        p = nw_c(pat)
        lines.append(f"<b>{lbl}:</b> {stat_p(p) if p else 'none'}")
    memory = REPO / "grok_workspace" / "MEMORY.md"
    lines.append(f"<b>MEMORY.md:</b> {stat_p(memory)}")
    proposals_dir = REPO / "grok_workspace" / "proposals"
    pfiles = sorted(proposals_dir.glob("*.md"), key=os.path.getmtime, reverse=True) if proposals_dir.exists() else []
    lines.append("<b>Proposals:</b>")
    for p in pfiles[:6]:
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%H:%M")
        lines.append(f"&nbsp;&nbsp;{p.name} ({p.stat().st_size}b @ {mtime})")
    interv = REPO / "grok_workspace" / "monitoring" / "interventions.jsonl"
    lines.append(f"<b>Interventions:</b> {stat_p(interv)}")
    if interv.exists():
        tail = interv.read_text(encoding="utf-8").splitlines()[-3:]
        for l in tail:
            lines.append(f"&nbsp;&nbsp;<code>{l[:100]}...</code>")
    return "<br>".join(lines)

def memory_tail():
    p = REPO / "grok_workspace" / "MEMORY.md"
    if not p.exists():
        return "<i>MEMORY.md not found</i>"
    lines = p.read_text(encoding="utf-8").splitlines()
    return "<pre>" + "\n".join(lines[-15:]) + "</pre>"

GRADUATED_WORKERS = {"passage_researcher", "pdf_art_director", "pdf_layout_engineer"}

def grok_activity_section():
    chat_log = REPO / "grok_workspace" / "chat_log.jsonl"
    if not chat_log.exists():
        return "<p><i>No chat log found</i></p>"
    import json as _json
    entries = []
    for line in chat_log.read_text(encoding="utf-8").splitlines()[-40:]:
        if line.strip():
            try:
                entries.append(_json.loads(line))
            except:
                pass
    interactions = {}
    for e in reversed(entries):
        ts = str(e.get("timestamp", ""))[:16].replace("T", " ")
        user = str(e.get("user", "")).lower()
        label = "Claude"
        if any(w in user for w in TRAINING_WORKERS):
            for w in TRAINING_WORKERS:
                if w in user:
                    label = f"Trainer: {w}"
                    break
        if label not in interactions:
            interactions[label] = []
        if len(interactions[label]) < 2:
            interactions[label].append(ts)
    html = '<table><tr><th>Channel</th><th>Last 2 TS</th></tr>'
    for label in sorted(interactions.keys()):
        times = ", ".join(interactions[label])
        html += f"<tr><td>{label}</td><td>{times}</td></tr>"
    return html + "</table>"

def get_pending_proposals_count():
    pending_file = REPO / "grok_workspace" / "notifications" / "pending_approval.md"
    if not pending_file.exists():
        return 0
    content = pending_file.read_text()
    return content.count("PROPOSAL READY:")

def proposals_section():
    pending_count = get_pending_proposals_count()
    html = f'<p><b>Pending Claude Review:</b> <span style="color:#ffb86c;font-weight:bold">{pending_count}</span></p>'
    proposals_dir = REPO / "grok_workspace" / "proposals"
    if not proposals_dir.exists():
        return html + "<p><i>No proposals directory</i></p>"
    pending_names = set()
    pending_file = REPO / "grok_workspace" / "notifications" / "pending_approval.md"
    if pending_file.exists():
        for line in pending_file.read_text().splitlines():
            if line.startswith("PROPOSAL READY:"):
                pending_names.add(line.split(":", 1)[1].strip().split()[0])
    md_files = sorted(
        [p for p in proposals_dir.glob("*.md") if p.stem != "README"],
        key=os.path.getmtime,
        reverse=True
    )[:4]
    table_html = '<table><tr><th>Submitted</th><th>Name</th><th>Status</th></tr>'
    for p in md_files:
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M")
        name = p.stem
        if name in pending_names:
            status = '<span style="color:#ffb86c;font-weight:bold">PENDING</span>'
        else:
            status = '<span style="color:#888">CLOSED</span>'
        table_html += f"<tr><td>{mtime}</td><td>{name}</td><td>{status}</td></tr>"
    table_html += "</table>"
    return html + table_html

def compute_human_html() -> str:
    metrics = query("""
        SELECT worker_name, COUNT(*) as total, SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passes,
        ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct FROM autoresearch_experiments GROUP BY worker_name ORDER BY total DESC
    """)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pending_props = get_pending_proposals_count()

    grad_names = [row[0].replace("_", " ") for row in metrics if row[0] in GRADUATED_WORKERS]
    grad_card = (
        '<div class="card green">'
        '<h3>Graduated Workers</h3>'
        + "".join(f"<p>✓ {name}</p>" for name in grad_names)
        + "</div>"
    ) if grad_names else '<div class="card green"><h3>Graduated</h3><p>(stable)</p></div>'

    cards_data = []
    for row in metrics:
        worker = row[0]
        if worker not in TRAINING_WORKERS:
            continue
        total = row[1]
        passes = row[2]
        pct = safe_f(row[3])
        last50_query = query("""
            SELECT ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / COUNT(*), 1)
            FROM (SELECT status, ROW_NUMBER() OVER (ORDER BY completed_at_utc DESC) as rn FROM autoresearch_experiments WHERE worker_name=? AND status IN ('pass','fail')) WHERE rn <= 50
        """, (worker,))
        prev50_query = query("""
            SELECT ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / COUNT(*), 1)
            FROM (SELECT status, ROW_NUMBER() OVER (ORDER BY completed_at_utc DESC) as rn FROM autoresearch_experiments WHERE worker_name=? AND status IN ('pass','fail')) WHERE rn BETWEEN 51 AND 100
        """, (worker,))
        last_pct = safe_f(last50_query[0] if last50_query else None)
        prev_pct = safe_f(prev50_query[0] if prev50_query else None)
        delta = last_pct - prev_pct
        color = "green" if delta > 0 else "yellow" if abs(delta) < 1 else "red"
        cards_data.append({
            'worker': worker.replace('_', ' '),
            'pct': pct,
            'passes': passes,
            'total': total,
            'delta': delta,
            'color': color
        })

    cards_data.sort(key=lambda x: x['pct'], reverse=True)

    cards_html = grad_card
    for data in cards_data:
        cards_html += f"""
        <div class="card {data['color']}">
            <h3>{data['worker']}</h3>
            <p class='big'>{data['pct']:.0f}%</p>
            <p>{data['passes']}/{data['total']}</p>
            <p style="font-size:11px">Δ {data['delta']:+.1f}</p>
        </div>
        """

    declining_workers = [data['worker'] for data in cards_data if data['delta'] < 0]
    alert_items = []
    if declining_workers:
        alert_items.append(f"Declining ({len(declining_workers)}): {', '.join(declining_workers)}")
    alert_items.append(f"Pending proposals: {pending_props}")
    alert_html = (
        '<div class="alert-box"><b>Alerts</b><ul>'
        + "".join(f"<li>{item}</li>" for item in alert_items)
        + '</ul></div>'
    ) if alert_items else '<div class="alert-box green"><b>✅ All clear</b></div>'

    return f"""<!DOCTYPE html>
<html><head>
<title>DevG Human Dashboard v3</title>
<meta http-equiv="refresh" content="{REFRESH_SECS}">
<style>
body {{ font-family: Arial; background: #1a1a2e; color: #eee; padding: 20px; max-width: 1400px; margin: auto; }}
h1 {{ color: #7ec8e3; text-align: center; }}
.cards {{ display: flex; flex-wrap: wrap; gap: 16px; margin: 20px 0; }}
.card {{ padding: 20px; border-radius: 12px; min-width: 180px; text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }}
.card h3 {{ margin: 0 0 12px; font-size: 14px; }}
.card .big {{ font-size: 36px; font-weight: bold; margin: 8px 0; }}
.green {{ background: linear-gradient(135deg, #1a4a2e, #2a5a3e); border: 2px solid #50fa7b; color: #50fa7b; }}
.yellow {{ background: linear-gradient(135deg, #4a3a1a, #5a4a2e); border: 2px solid #ffb86c; color: #ffb86c; }}
.red {{ background: linear-gradient(135deg, #4a1a1a, #5a2a2e); border: 2px solid #ff5555; color: #ff5555; }}
.alert-box {{ background: linear-gradient(135deg, #4a1a1a, #5a2a2e); border: 2px solid #ff5555; padding: 16px; border-radius: 10px; margin: 20px 0; }}
.alert-box.green {{ background: linear-gradient(135deg, #1a4a2e, #2a5a3e); border-color: #50fa7b; color: #50fa7b; }}
.meta {{ color: #888; font-size: 13px; text-align: center; }}
</style>
</head>
<body>
<h1>DevG v3 — {now_str}</h1>
<div class="meta">Background Cached | Δ Colors | Refresh {REFRESH_SECS}s | 8 Training Workers</div>
<div class="cards">{cards_html}</div>
{alert_html}
<h2>Grok Activity</h2>
{grok_activity_section()}
<h2>Proposals</h2>
{proposals_section()}
</body>
</html>"""

def compute_claude_html() -> str:
    metrics = query("""
        SELECT worker_name, COUNT(*) as total, SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passes,
        SUM(CASE WHEN status='fail' THEN 1 ELSE 0 END) as fails, SUM(CASE WHEN status='assigned' THEN 1 ELSE 0 END) as pending,
        ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct FROM autoresearch_experiments GROUP BY worker_name ORDER BY total DESC
    """)
    traj_rows = []
    for worker in sorted(TRAINING_WORKERS):
        last50 = query("""
            SELECT ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / COUNT(*), 1)
            FROM (SELECT status, ROW_NUMBER() OVER (ORDER BY completed_at_utc DESC) as rn FROM autoresearch_experiments WHERE worker_name=? AND status IN ('pass','fail')) WHERE rn <= 50
        """, (worker,))
        prev50 = query("""
            SELECT ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / COUNT(*), 1)
            FROM (SELECT status, ROW_NUMBER() OVER (ORDER BY completed_at_utc DESC) as rn FROM autoresearch_experiments WHERE worker_name=? AND status IN ('pass','fail')) WHERE rn BETWEEN 51 AND 100
        """, (worker,))
        last_pct = safe_f(last50[0] if last50 else None)
        prev_pct = safe_f(prev50[0] if prev50 else None)
        delta = last_pct - prev_pct
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "→"
        traj_rows.append((worker, prev_pct, last_pct, arrow, delta))
    traj_rows.sort(key=lambda x: x[4], reverse=True)

    trainer_rows = query("""
        SELECT SUBSTR(worker_name, 9) as worker, COUNT(*) as total, MAX(completed_at_utc) as last_ts,
        SUM(CASE WHEN benchmark_name='trainer_directive' THEN 1 ELSE 0 END) as directives,
        SUM(CASE WHEN keep_decision='effective' THEN 1 ELSE 0 END) as effective
        FROM autoresearch_experiments WHERE worker_name LIKE 'trainer_%' GROUP BY SUBSTR(worker_name, 9) ORDER BY last_ts DESC
    """)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pending_props = get_pending_proposals_count()

    metrics_table = '<table><tr><th>Worker</th><th>Total</th><th>Passes</th><th>Fails</th><th>Pending</th><th>Pct</th></tr>'
    for row in metrics:
        worker, total, passes, fails, pending, pct = row
        pct_str = f"{safe_f(pct)}%"
        color = "#50fa7b" if pct > 80 else "#ffb86c" if pct > 20 else "#ff5555"
        style = f'style="color:{color}; font-weight: bold;"' if worker in TRAINING_WORKERS else ""
        metrics_table += f"<tr {style}><td>{worker}</td><td>{total}</td><td>{passes}</td><td>{fails}</td><td>{pending}</td><td>{pct_str}</td></tr>"
    metrics_table += "</table>"

    traj_table = '<table><tr><th>Worker</th><th>Prev 50%</th><th>Last 50%</th><th>Delta</th><th>Trend</th></tr>'
    for worker, prev_pct, last_pct, arrow, delta in traj_rows:
        color = "#50fa7b" if delta > 0 else "#ff5555" if delta < 0 else "#888"
        traj_table += f'<tr><td>{worker}</td><td>{prev_pct:.1f}</td><td>{last_pct:.1f}</td><td>{delta:+.1f}</td><td style="color:{color}; font-size: 20px;">{arrow}</td></tr>'
    traj_table += "</table>"

    trainer_table = '<table><tr><th>Trainer</th><th>Exps</th><th>Last TS</th><th>Directives</th><th>Effective</th></tr>'
    for row in trainer_rows:
        worker, total, last_ts, directives, effective = row
        if worker not in TRAINING_WORKERS:
            continue
        ts_str = last_ts[:16].replace("T", " ") if last_ts else "none"
        trainer_table += f"<tr><td>{worker}</td><td>{total}</td><td>{ts_str}</td><td>{directives}</td><td>{effective}</td></tr>"
    trainer_table += "</table>"

    declining_workers = [row[0] for row in traj_rows if row[3] == "▼"]
    declining_html = (
        f'<div style="background: #4a1a1a; border: 2px solid #ff5555; padding: 12px; border-radius: 8px; margin: 10px 0;">'
        f'<b>Declining (Δ &lt; 0): {len(declining_workers)} — {", ".join(declining_workers)}</b></div>'
    ) if declining_workers else (
        '<div style="background: #1a4a2e; border: 2px solid #50fa7b; padding: 12px; border-radius: 8px; margin: 10px 0;">'
        '<b>✅ No declining workers</b></div>'
    )

    return f"""<!DOCTYPE html>
<html><head>
<title>DevG Claude Dashboard v3</title>
<meta http-equiv="refresh" content="{REFRESH_SECS}">
<style>
body {{ font-family: monospace; background: #0d1117; color: #c9d1d9; padding: 20px; line-height: 1.4; }}
h1 {{ color: #58a6ff; }}
h2 {{ color: #79c0ff; border-bottom: 1px solid #30363d; padding-bottom: 8px; margin-top: 30px; }}
table {{ border-collapse: collapse; margin: 15px 0; font-size: 13px; }}
th, td {{ border: 1px solid #30363d; padding: 8px 12px; text-align: left; }}
th {{ background: #161b22; color: #79c0ff; }}
.meta {{ color: #8b949e; font-size: 13px; margin-bottom: 25px; padding: 10px; background: #161b22; border-radius: 6px; }}
</style>
</head>
<body>
<h1>DevG v3 Claude — {now_str}</h1>
<div class="meta">
Updated: {now_str} | Refresh: {REFRESH_SECS}s | Pending proposals: {pending_props} | 8 Training Workers Filter
</div>
<h2>All Worker Metrics</h2>
{metrics_table}
<h2>Trajectory Deltas (Sorted Desc, TRAINING_WORKERS only)</h2>
{traj_table}
{declining_html}
<h2>Grok-Trainer Interactions (trainer_* DB, SUBSTR(9), Filtered)</h2>
{trainer_table}
<h2>Working Memory Tail</h2>
{memory_tail()}
<h2>Grok ↔ Claude Activity</h2>
{grok_activity_section()}
<h2>Recent Proposals</h2>
{proposals_section()}
<h2>Data Sources & Interventions Tail</h2>
<div style="background: #161b22; padding: 15px; border-radius: 8px; font-size: 13px; line-height: 1.6;">
{claude_sources()}
</div>
</body>
</html>"""

def refresh_loop():
    while True:
        try:
            # Compute unlocked (slow SMB OK in BG)
            human_html = compute_human_html()
            claude_html = compute_claude_html()
            # Atomic fast swap locked
            with cache_lock:
                global _human_cache, _claude_cache
                _human_cache = human_html
                _claude_cache = claude_html
            print(f"v3 caches swapped OK @ {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"v3 refresh err (continues): {e}")
        time.sleep(REFRESH_SECS)

class HumanHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        with cache_lock:
            html = _human_cache or "<h1>v3 Human Dashboard Loading (bg cache init)</h1><p>~{REFRESH_SECS}s first load.</p><script>setTimeout(()=>location.reload(),10000);</script>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

class ClaudeHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        with cache_lock:
            html = _claude_cache or "<h1>v3 Claude Dashboard Loading (bg cache init)</h1><p>~{REFRESH_SECS}s first load.</p><script>setTimeout(()=>location.reload(),10000);</script>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    threading.Thread(target=refresh_loop, daemon=True).start()
    ip = get_ip()
    print("DevG v3 Dashboard — Non-Blocking Cache Active (unlock compute)")
    print(f"  Human:  http://{ip}:{HUMAN_PORT}")
    print(f"  Claude: http://{ip}:{CLAUDE_PORT}")
    httpd1 = socketserver.ThreadingTCPServer(("", HUMAN_PORT), HumanHandler)
    t1 = threading.Thread(target=httpd1.serve_forever, daemon=True)
    t1.start()
    httpd2 = socketserver.ThreadingTCPServer(("", CLAUDE_PORT), ClaudeHandler)
    httpd2.serve_forever()