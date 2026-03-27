from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.review.run_pending_approvals import (
    _build_output_path,
    _decision_key,
    _ensure_decision_source_policy,
    _sorted_decisions,
    default_reviewed_by,
    format_section_label,
    load_existing_decisions,
    load_report,
    parse_pending_item,
    unresolved_items,
    write_decisions,
)


class WebReviewState:
    def __init__(
        self,
        report_path: Path,
        output_path: Path,
        reviewed_by: str,
        decision_source: str | None,
        reset: bool = False,
    ) -> None:
        self.lock = threading.RLock()
        self.report_path = report_path
        self.report = load_report(report_path)
        self.report["source_report"] = str(report_path)
        self.section_previews = {
            str(k): str(v)
            for k, v in (self.report.get("section_previews_by_key") or {}).items()
            if isinstance(k, str)
        }
        self.section_meta = {
            str(k): dict(v)
            for k, v in (self.report.get("section_meta_by_key") or {}).items()
            if isinstance(k, str) and isinstance(v, dict)
        }
        self.items = [parse_pending_item(raw) for raw in self.report.get("pending_sections", [])]
        self.total_pending = len(self.items)
        self.output_path = output_path
        self.reviewed_by = reviewed_by
        self.decision_source = decision_source
        _ensure_decision_source_policy(self.reviewed_by, self.decision_source)
        self.decision_map = (
            {}
            if reset
            else load_existing_decisions(output_path, expected_source_report=report_path)
        )
        self.current_index = 0
        self.persist()

    def persist(self) -> None:
        write_decisions(
            output_path=self.output_path,
            report=self.report,
            decision_map=self.decision_map,
            mode="web",
            total_pending=self.total_pending,
        )

    def _remaining(self):
        return unresolved_items(self.items, self.decision_map)

    def _current_item(self):
        remaining = self._remaining()
        if not remaining:
            return None, remaining
        if self.current_index >= len(remaining):
            self.current_index = len(remaining) - 1
        return remaining[self.current_index], remaining

    def state_payload(self) -> dict:
        with self.lock:
            current, remaining = self._current_item()
            resolved = len(_sorted_decisions(self.decision_map))
            payload = {
                "topic": self.report.get("topic"),
                "days": self.report.get("days"),
                "total_pending": self.total_pending,
                "resolved": resolved,
                "remaining_count": len(remaining),
                "output_file": self.output_path.name,
                "reviewed_by": self.reviewed_by,
                "current_index": self.current_index,
                "current": None,
                "done": current is None,
            }
            if current is not None:
                payload["current"] = {
                    "day": current.day,
                    "section": current.section,
                    "section_label": format_section_label(current.section),
                    "position": self.current_index + 1,
                    "total_remaining": len(remaining),
                    "source_preview": self.section_previews.get(
                        _decision_key(current.day, current.section), ""
                    ),
                    "section_meta": self.section_meta.get(
                        _decision_key(current.day, current.section), {}
                    ),
                }
            return payload

    def _record(self, decision: str) -> None:
        current, remaining = self._current_item()
        if current is None:
            return
        record = {
            "day": current.day,
            "section": current.section,
            "decision": decision,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": self.reviewed_by,
        }
        if self.decision_source is not None:
            record["decision_source"] = self.decision_source
        self.decision_map[_decision_key(current.day, current.section)] = record
        self.persist()
        if self.current_index >= len(remaining):
            self.current_index = max(len(remaining) - 1, 0)

    def apply_action(self, action: str) -> dict:
        with self.lock:
            if action == "approve":
                self._record("approved")
            elif action == "reject":
                self._record("rejected")
            elif action == "skip":
                remaining = self._remaining()
                if remaining:
                    self.current_index = (self.current_index + 1) % len(remaining)
            elif action == "next":
                remaining = self._remaining()
                if remaining:
                    self.current_index = (self.current_index + 1) % len(remaining)
            elif action == "prev":
                remaining = self._remaining()
                if remaining:
                    self.current_index = (self.current_index - 1) % len(remaining)
            else:
                raise ValueError(f"Unknown action: {action}")
            return self.state_payload()


def _html_page() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DevG Review</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f7f7f8;
      --text: #131418;
      --muted: #595f6a;
      --card: #ffffff;
      --border: #d8dbe1;
      --btn-bg: #eceef3;
      --btn-border: #cfd4de;
      --btn-text: #161a22;
      --btn-bg-hover: #e3e6ee;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #111318;
        --text: #f2f5fb;
        --muted: #b4bfce;
        --card: #1b2029;
        --border: #3a4251;
        --btn-bg: #2a3342;
        --btn-border: #445069;
        --btn-text: #f4f7ff;
        --btn-bg-hover: #333e52;
      }
    }
    body {
      font-family: -apple-system, Segoe UI, sans-serif;
      margin: 24px;
      color: var(--text);
      background: var(--bg);
    }
    .muted { color: var(--muted); font-size: 14px; }
    .card {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 18px;
      margin-top: 16px;
      background: var(--card);
    }
    .item { font-size: 40px; line-height: 1.2; margin: 10px 0; }
    button {
      font-size: 22px;
      padding: 12px 16px;
      margin-right: 8px;
      margin-top: 8px;
      border-radius: 10px;
      border: 1px solid var(--btn-border);
      background: var(--btn-bg);
      color: var(--btn-text);
      cursor: pointer;
    }
    button:hover { background: var(--btn-bg-hover); }
    .row { margin-top: 10px; }
    .source-box {
      margin-top: 16px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      background: var(--card);
      font-size: 18px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
  </style>
</head>
<body>
  <h2>DevG Approval Review (Web)</h2>
  <div id="meta" class="muted"></div>
  <div id="card" class="card"></div>
  <div id="meta2" class="muted" style="margin-top:8px;"></div>
  <div id="source" class="source-box"></div>
  <div class="row">
    <button onclick="act('approve')">Approve (A)</button>
    <button onclick="act('reject')">Reject (R)</button>
    <button onclick="act('skip')">Skip (S)</button>
    <button onclick="act('prev')">Prev (←)</button>
    <button onclick="act('next')">Next (→)</button>
  </div>
  <script>
    async function state() {
      const r = await fetch('/api/state');
      const s = await r.json();
      render(s);
    }
    async function act(action) {
      const r = await fetch('/api/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action})
      });
      const s = await r.json();
      render(s);
    }
    function render(s) {
      document.getElementById('meta').textContent =
        `Topic: ${s.topic ?? 'N/A'} | Days: ${s.days ?? 'N/A'} | Resolved: ${s.resolved}/${s.total_pending} | Remaining: ${s.remaining_count} | Reviewer: ${s.reviewed_by} | File: ${s.output_file}`;
      const card = document.getElementById('card');
      if (s.done) {
        card.innerHTML = '<div class="item">All pending sections are resolved.</div><div class="muted">You can close this tab and stop the server (Ctrl+C).</div>';
        document.getElementById('meta2').textContent = '';
        document.getElementById('source').textContent = '';
        return;
      }
      card.innerHTML =
        `<div class="item">Day ${s.current.day} - ${s.current.section_label}</div>` +
        `<div class="muted">Item ${s.current.position}/${s.current.total_remaining} of remaining pending sections.</div>`;
      const meta = s.current.section_meta || {};
      document.getElementById('meta2').textContent =
        `Verification: ${meta.verification_status || 'n/a'} | Retrieval: ${meta.retrieval_source || 'n/a'} | Approval: ${meta.approval_status || 'pending'}`;
      document.getElementById('source').textContent = s.current.source_preview || '(No section content preview in report.)';
    }
    window.addEventListener('keydown', (e) => {
      if (e.key === 'a' || e.key === 'A') act('approve');
      else if (e.key === 'r' || e.key === 'R') act('reject');
      else if (e.key === 's' || e.key === 'S') act('skip');
      else if (e.key === 'ArrowLeft') act('prev');
      else if (e.key === 'ArrowRight') act('next');
    });
    state();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "DevGReviewWeb/1.0"

    def _write_json(self, payload: dict, code: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _write_html(self, text: str, code: int = HTTPStatus.OK) -> None:
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._write_html(_html_page())
            return
        if self.path == "/api/state":
            self._write_json(self.server.app_state.state_payload())  # type: ignore[attr-defined]
            return
        self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/action":
            self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
            action = str(payload.get("action", ""))
            state = self.server.app_state.apply_action(action)  # type: ignore[attr-defined]
            self._write_json(state)
        except Exception as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open web review for pending approvals.")
    parser.add_argument("--report", required=True, help="Path to approval-gate report JSON")
    parser.add_argument("--out", help="Output decisions JSON path")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Ignore existing decisions file and start this report from scratch.",
    )
    parser.add_argument(
        "--reviewed-by",
        default=default_reviewed_by(),
        help="Reviewer identifier stored in decision metadata.",
    )
    parser.add_argument(
        "--decision-source",
        help=(
            "Decision provenance label. Required when --reviewed-by starts with 'agent:'. "
            "For humans this is optional."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host bind address.")
    parser.add_argument("--port", type=int, default=8765, help="Port bind address.")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not auto-open browser tab.",
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    output_path = _build_output_path(report_path, args.out)
    decision_source = args.decision_source.strip() if args.decision_source else None

    app_state = WebReviewState(
        report_path=report_path,
        output_path=output_path,
        reviewed_by=args.reviewed_by,
        decision_source=decision_source,
        reset=args.reset,
    )

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.app_state = app_state  # type: ignore[attr-defined]
    url = f"http://{args.host}:{args.port}/"
    print(f"WEB_REVIEW_URL={url}")
    print(f"DECISIONS={output_path}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
