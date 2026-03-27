#!/usr/bin/env python3
import sqlite3
import datetime
import re
import http.server
import socketserver
import threading
import time
import shutil
import tempfile
import os

DB_PATH = 'registry.db'
_DB_COPY = os.path.join(tempfile.gettempdir(), 'devg_dashboard_cache.db')
TODO_PATH = 'grok_workspace/TODO.md'
PORT = 8080
CACHE_TTL = 30  # seconds between DB refreshes

# In-memory cache — updated by background thread, read by HTTP handler
_cache = {'html': None, 'updated': None}
_cache_lock = threading.Lock()

def query(sql):
    conn = sqlite3.connect(_DB_COPY, timeout=5)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()
    return rows

def utc_to_local(utc_str):
    """Convert a UTC datetime string from SQLite to local time string."""
    if not utc_str:
        return ''
    try:
        dt = datetime.datetime.fromisoformat(str(utc_str).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone().strftime('%Y-%m-%d %H:%M')
    except Exception:
        return str(utc_str)[:16]

# Workers: last 50 completed pass rates
sql_workers = '''
SELECT worker_name, passes, total,
       ROUND(100.0 * passes / total, 1) AS pct_num,
       ROUND(100.0 * passes / total, 1) || '%' AS pct
FROM (
  SELECT worker_name,
         SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) AS passes,
         COUNT(*) AS total
  FROM (
    SELECT worker_name, status,
           ROW_NUMBER() OVER (PARTITION BY worker_name
                              ORDER BY completed_at_utc DESC) AS rn
    FROM autoresearch_experiments
    WHERE completed_at_utc IS NOT NULL
  )
  WHERE rn <= 50
  GROUP BY worker_name
  HAVING total > 0
)
ORDER BY total DESC
'''

# Recent 5 experiments
sql_recent = '''
SELECT worker_name, benchmark_reference, status,
       datetime(completed_at_utc) AS completed
FROM autoresearch_experiments
WHERE completed_at_utc IS NOT NULL
ORDER BY completed_at_utc DESC LIMIT 5
'''

# Cycle stats
sql_stats = '''
SELECT
  (SELECT COUNT(*) FROM autoresearch_experiments WHERE status = 'assigned') AS assigned_count,
  (SELECT MAX(completed_at_utc) FROM autoresearch_experiments WHERE completed_at_utc IS NOT NULL) AS last_update,
  (SELECT AVG((julianday(completed_at_utc) - julianday(created_at_utc)) * 1440)
   FROM autoresearch_experiments
   WHERE created_at_utc > datetime('now', '-1 day') AND completed_at_utc IS NOT NULL) AS avg_completion_min,
  (SELECT COUNT(*) FROM autoresearch_experiments
   WHERE created_at_utc > datetime('now', '-2 hours') AND completed_at_utc IS NOT NULL) AS recent_completed,
  (SELECT COUNT(*) FROM autoresearch_experiments
   WHERE created_at_utc > datetime('now', '-2 hours')) AS recent_total
'''

def rate_color(pct):
    if pct >= 50:
        return '#4caf50'  # green
    elif pct >= 20:
        return '#ffb74d'  # amber
    else:
        return '#ef5350'  # red

def rate_bg(pct):
    if pct >= 50:
        return '#1a2e1a'
    elif pct >= 20:
        return '#2e2410'
    else:
        return '#2e1414'

def render_todo(todo_content):
    """Render TODO.md as styled sections instead of a raw text block."""
    lines = todo_content.splitlines()
    html_parts = []
    in_list = False

    for line in lines:
        # Skip the title line
        if line.startswith('# '):
            continue
        # Section headers
        if line.startswith('## '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            section = line[3:].strip()
            color = '#ef5350' if 'URGENT' in section else '#aaa'
            html_parts.append(f'<h3 style="color:{color};margin-top:16px;margin-bottom:6px">{section}</h3>')
        # Separator
        elif line.strip() == '---':
            continue
        # Checked item
        elif line.strip().startswith('- [x]'):
            if not in_list:
                html_parts.append('<ul style="list-style:none;padding:0;margin:0">')
                in_list = True
            text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line.strip()[5:].strip())
            html_parts.append(f'<li style="color:#555;padding:3px 0;font-size:0.9em">&#10003; {text}</li>')
        # Open item
        elif line.strip().startswith('- [ ]'):
            if not in_list:
                html_parts.append('<ul style="list-style:none;padding:0;margin:0">')
                in_list = True
            text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line.strip()[5:].strip())
            html_parts.append(f'<li style="padding:4px 0;color:#ddd">&#9744; {text}</li>')
        # Other non-empty lines (notes etc)
        elif line.strip() and not line.strip().startswith('#'):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html_parts.append(f'<p style="margin:2px 0;font-size:0.85em;color:#777">{escaped}</p>')

    if in_list:
        html_parts.append('</ul>')

    return '\n'.join(html_parts)


def refresh_cache():
    """Background thread: copy DB locally then rebuild HTML every CACHE_TTL seconds."""
    while True:
        try:
            shutil.copy2(DB_PATH, _DB_COPY)
            handler = DashboardHandler.__new__(DashboardHandler)
            html = handler.generate_html()
            with _cache_lock:
                _cache['html'] = html
                _cache['updated'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f'Cache refresh error: {e}')  # keep serving last good cache
        time.sleep(CACHE_TTL)


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/':
            self.send_error(404, 'Page not found')
            return
        with _cache_lock:
            html = _cache['html']
        if html is None:
            html = '<!DOCTYPE html><html><head><meta http-equiv="refresh" content="5"><style>body{background:#121212;color:#e0e0e0;font-family:Arial;padding:40px}</style></head><body><h2>Dashboard loading...</h2><p>First DB query in progress. Auto-retry in 5s.</p></body></html>'
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        pass  # suppress request logging noise

    def generate_html(self):
        workers = query(sql_workers)
        recent = query(sql_recent)
        stats_row = query(sql_stats)[0]
        assigned_count = stats_row['assigned_count']
        last_update = utc_to_local(stats_row['last_update']) or 'Never'
        avg_completion_min = f"{stats_row['avg_completion_min']:.1f}" if stats_row['avg_completion_min'] else 'N/A'
        recent_completed = stats_row['recent_completed'] or 0
        recent_total = stats_row['recent_total'] or 0
        cycle_health = f"{100 * recent_completed / max(recent_total,1):.0f}%" if recent_total else 'N/A'

        with open(TODO_PATH, 'r') as f:
            todo_content = f.read()

        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        worker_rows = ''
        for row in workers:
            pct = row['pct_num'] or 0
            color = rate_color(pct)
            bg = rate_bg(pct)
            worker_rows += (
                f'<tr style="background:{bg}">'
                f'<td>{row["worker_name"]}</td>'
                f'<td style="text-align:center">{row["passes"]}</td>'
                f'<td style="text-align:center">{row["total"]}</td>'
                f'<td style="text-align:center;font-weight:bold;color:{color}">{row["pct"]}</td>'
                f'</tr>'
            )

        status_colors = {'pass': '#4caf50', 'fail': '#ef5350', 'revise': '#ffb74d', 'assigned': '#aaa'}
        recent_rows = ''
        for row in recent:
            sc = status_colors.get(row['status'], '#aaa')
            ref = str(row['benchmark_reference'] or '')[:45]
            completed_local = utc_to_local(row['completed'])
            recent_rows += (
                f'<tr>'
                f'<td>{row["worker_name"]}</td>'
                f'<td>{ref}</td>'
                f'<td style="font-weight:bold;color:{sc}">{row["status"]}</td>'
                f'<td style="color:#777">{completed_local}</td>'
                f'</tr>'
            )

        todo_html = render_todo(todo_content)

        assigned_color = '#ef5350' if assigned_count > 10 else '#4caf50'

        return f'''<!DOCTYPE html>
<html>
<head>
    <title>DevG Dashboard</title>
    <meta http-equiv="refresh" content="60">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 16px; background: #121212; color: #e0e0e0; }}
        h1 {{ color: #e0e0e0; font-size: 1.2em; margin-bottom: 4px; }}
        h2 {{ color: #bbb; font-size: 1.05em; margin: 20px 0 8px; border-bottom: 1px solid #333; padding-bottom: 4px; }}
        .meta {{ color: #666; font-size: 0.8em; margin-bottom: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 8px; background: #1e1e1e; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.4); }}
        th {{ background: #2a2a2a; color: #ccc; padding: 8px 10px; text-align: left; font-size: 0.85em; }}
        td {{ padding: 7px 10px; border-bottom: 1px solid #2a2a2a; font-size: 0.9em; color: #ddd; }}
        .stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }}
        .stat-card {{ background: #1e1e1e; border-radius: 6px; padding: 12px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.4); min-width: 140px; }}
        .stat-label {{ font-size: 0.75em; color: #666; text-transform: uppercase; }}
        .stat-value {{ font-size: 1.4em; font-weight: bold; margin-top: 2px; color: #e0e0e0; }}
        .todo-box {{ background: #1e1e1e; border-radius: 6px; padding: 14px 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.4); font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>DevG Training Dashboard</h1>
    <div class="meta">Updated {now} &nbsp;&#x2022;&nbsp; Auto-refresh 60s</div>

    <h2>Supervisor Status</h2>
    <div class="stats">
        <div class="stat-card">
            <div class="stat-label">Live Assigned</div>
            <div class="stat-value" style="color:{assigned_color}">{assigned_count}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Last DB Update</div>
            <div class="stat-value" style="font-size:0.9em">{last_update}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">24h Avg Completion</div>
            <div class="stat-value">{avg_completion_min}<span style="font-size:0.6em;color:#666"> min</span></div>
        </div>
        <div class="stat-card">
            <div class="stat-label">2h Completion Rate</div>
            <div class="stat-value">{cycle_health}</div>
        </div>
    </div>

    <h2>Worker Pass Rates — Last 50 Experiments</h2>
    <table>
        <tr><th>Worker</th><th style="text-align:center">Passes</th><th style="text-align:center">Total</th><th style="text-align:center">Rate</th></tr>
        {worker_rows}
    </table>

    <h2>Recent Activity</h2>
    <table>
        <tr><th>Worker</th><th>Reference</th><th>Status</th><th>Completed</th></tr>
        {recent_rows}
    </table>

    <h2>TODO</h2>
    <div class="todo-box">
        {todo_html}
    </div>
</body>
</html>'''

if __name__ == '__main__':
    print(f"Starting DevG Dashboard at http://0.0.0.0:{PORT}")
    print(f"Local network: http://mac-studio.local:{PORT} (auto-refresh 60s)")
    print("Press Ctrl+C to stop.")
    t = threading.Thread(target=refresh_cache, daemon=True)
    t.start()
    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
    with ThreadedTCPServer(("0.0.0.0", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()
