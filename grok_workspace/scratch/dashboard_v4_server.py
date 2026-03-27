#!/usr/bin/env python3
import sqlite3
import datetime
import http.server
import socketserver

DB_PATH = 'registry.db'
TODO_PATH = 'grok_workspace/TODO.md'
PORT = 8080

def query(sql):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()
    return rows

# Workers: last 50 completed pass rates
sql_workers = '''
SELECT worker_name, passes, total,
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

# Recent 20 expts
sql_recent = '''
SELECT worker_name, benchmark_reference, status,
       datetime(created_at_utc) AS created,
       datetime(completed_at_utc) AS completed
FROM autoresearch_experiments
ORDER BY created_at_utc DESC LIMIT 20
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

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/':
            self.send_error(404, 'Page not found')
            return
        try:
            html = self.generate_html()
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def generate_html(self):
        workers = query(sql_workers)
        recent = query(sql_recent)
        stats_row = query(sql_stats)[0]
        assigned_count = stats_row['assigned_count']
        last_update = stats_row['last_update']
        avg_completion_min = f"{stats_row['avg_completion_min']:.1f}" if stats_row['avg_completion_min'] else 'N/A'
        recent_completed = stats_row['recent_completed'] or 0
        recent_total = stats_row['recent_total'] or 0
        cycle_health = f"{100 * recent_completed / max(recent_total,1):.0f}%" if recent_total else 'N/A'

        with open(TODO_PATH, 'r') as f:
            todo_content = f.read()

        now = datetime.datetime.now().isoformat()

        worker_rows = ''.join(f"<tr><td>{row['worker_name']}</td><td>{row['passes']}</td><td>{row['total']}</td><td>{row['pct']}</td></tr>" for row in workers)
        recent_rows = ''.join(f"<tr><td>{row['worker_name']}</td><td>{str(row['benchmark_reference'] or '')[:40]}</td><td>{row['status']}</td><td>{row['created']}</td><td>{row['completed'] or 'Pending'}</td></tr>" for row in recent)

        todo_escaped = todo_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>DevG Dashboard v4 Server</title>
    <meta http-equiv="refresh" content="60">
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; }}
        h1, h2 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        pre {{ background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; }}
        .stat {{ font-size: 1.2em; font-weight: bold; color: #d00; }}
    </style>
</head>
<body>
    <h1>DevG Training Dashboard v4 Server — Updated {now} (Live DB)</h1>

    <h2>Worker Pass Rates (Last 50 Completed Experiments Each)</h2>
    <table>
        <tr><th>Worker</th><th>Passes</th><th>Total</th><th>Pass %</th></tr>
        {worker_rows}
    </table>

    <h2>Recent Experiments (Last 20)</h2>
    <table>
        <tr><th>Worker</th><th>Reference</th><th>Status</th><th>Created</th><th>Completed</th></tr>
        {recent_rows}
    </table>

    <h2>Supervisor Cycle Status</h2>
    <p><span class="stat">Live Assigned: {assigned_count}</span></p>
    <p>Last DB Update: {last_update or "Never"}</p>
    <p>24h Avg Completion: {avg_completion_min} min</p>
    <p>Last 2h Completion Rate: {cycle_health}</p>

    <h2>TODO.md Content</h2>
    <pre>{todo_escaped}</pre>
</body>
</html>'''
        return html

if __name__ == '__main__':
    print(f"Starting DevG Dashboard v4 Server at http://0.0.0.0:{PORT}")
    print(f"Local network: http://mac-studio.local:{PORT} (auto-refresh 60s)")
    print("Press Ctrl+C to stop.")
    with socketserver.TCPServer(("0.0.0.0", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()