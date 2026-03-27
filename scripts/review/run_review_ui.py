from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.review.run_pending_approvals import (
    _ensure_decision_source_policy,
    _build_output_path,
    _decision_key,
    _sorted_decisions,
    default_reviewed_by,
    format_section_label,
    load_existing_decisions,
    load_report,
    parse_pending_item,
    unresolved_items,
    write_decisions,
)


class ApprovalReviewApp:
    def __init__(
        self,
        report_path: Path,
        output_path: Path,
        reviewed_by: str,
        decision_source: str | None = None,
        reset: bool = False,
    ):
        try:
            import tkinter as tk
            from tkinter import messagebox
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "UI backend requires tkinter, which is not available in this Python build."
            ) from exc

        self.tk = tk
        self.messagebox = messagebox
        self.report_path = report_path
        self.report = load_report(report_path)
        self.report["source_report"] = str(report_path)
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
        self.remaining = unresolved_items(self.items, self.decision_map)
        self.current_index = 0

        self.root = self.tk.Tk()
        self.root.title("DevG Approval Review")
        self.root.geometry("980x560")
        self.root.minsize(860, 500)

        self.progress_var = self.tk.StringVar()
        self.topic_var = self.tk.StringVar(value=f"Topic: {self.report.get('topic') or 'N/A'}")
        self.run_meta_var = self.tk.StringVar()
        self.item_var = self.tk.StringVar()
        self.summary_var = self.tk.StringVar()
        self.shortcuts_var = self.tk.StringVar(
            value="Shortcuts: A approve, R reject, S skip, Left/Right navigate, Q quit"
        )
        self.status_var = self.tk.StringVar(value="")

        self._build_ui()
        self._bind_shortcuts()
        self._persist()
        self._render()

    def _build_ui(self) -> None:
        tk = self.tk
        wrapper = tk.Frame(self.root, padx=22, pady=22)
        wrapper.pack(fill=tk.BOTH, expand=True)

        tk.Label(wrapper, textvariable=self.topic_var, font=("Arial", 15, "bold")).pack(anchor="w")
        tk.Label(wrapper, textvariable=self.run_meta_var, font=("Arial", 11)).pack(anchor="w", pady=(4, 0))
        tk.Label(wrapper, textvariable=self.progress_var, font=("Arial", 12)).pack(anchor="w", pady=(6, 0))
        tk.Label(wrapper, textvariable=self.shortcuts_var, font=("Arial", 10, "italic")).pack(anchor="w", pady=(6, 0))

        tk.Label(
            wrapper,
            textvariable=self.item_var,
            font=("Arial", 26, "bold"),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(28, 14))

        tk.Label(
            wrapper,
            textvariable=self.summary_var,
            font=("Arial", 12),
            justify="left",
            wraplength=900,
        ).pack(anchor="w")

        button_row = tk.Frame(wrapper)
        button_row.pack(anchor="w", pady=(28, 0))

        tk.Button(button_row, text="Approve (A)", width=14, command=self._approve).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(button_row, text="Reject (R)", width=14, command=self._reject).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(button_row, text="Skip (S)", width=12, command=self._skip).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(button_row, text="Prev", width=10, command=self._prev).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(button_row, text="Next", width=10, command=self._next).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(button_row, text="Quit (Q)", width=12, command=self._quit).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(wrapper, textvariable=self.status_var, font=("Arial", 11, "bold")).pack(anchor="w", pady=(16, 0))

    def _bind_shortcuts(self) -> None:
        self.root.bind("<a>", lambda _e: self._approve())
        self.root.bind("<A>", lambda _e: self._approve())
        self.root.bind("<r>", lambda _e: self._reject())
        self.root.bind("<R>", lambda _e: self._reject())
        self.root.bind("<s>", lambda _e: self._skip())
        self.root.bind("<S>", lambda _e: self._skip())
        self.root.bind("<q>", lambda _e: self._quit())
        self.root.bind("<Q>", lambda _e: self._quit())
        self.root.bind("<Left>", lambda _e: self._prev())
        self.root.bind("<Right>", lambda _e: self._next())

    def _persist(self) -> None:
        write_decisions(
            output_path=self.output_path,
            report=self.report,
            decision_map=self.decision_map,
            mode="ui",
            total_pending=self.total_pending,
        )

    def _render(self) -> None:
        self.remaining = unresolved_items(self.items, self.decision_map)
        completed = len(_sorted_decisions(self.decision_map))
        days = self.report.get("days") or "N/A"
        self.run_meta_var.set(
            f"Days: {days}    Pending in report: {self.total_pending}    Decisions file: {self.output_path.name}"
        )
        self.progress_var.set(
            f"Resolved: {completed}/{self.total_pending}    Remaining: {len(self.remaining)}"
        )

        if not self.remaining:
            self.item_var.set("All pending sections are resolved.")
            self.summary_var.set(
                "All items are decided. You can close this window now. "
                "Rerun with --reset to start over."
            )
            return

        if self.current_index >= len(self.remaining):
            self.current_index = len(self.remaining) - 1
        current = self.remaining[self.current_index]
        section_pos = self.current_index + 1
        total_remaining = len(self.remaining)
        label = format_section_label(current.section)
        self.item_var.set(f"Day {current.day} — {label}")
        self.summary_var.set(
            f"Viewing remaining item {section_pos}/{total_remaining}. "
            "Approve or Reject saves a final decision. "
            "Skip keeps this item pending and moves forward."
        )

    def _record(self, decision: str) -> None:
        if not self.remaining:
            return
        current = self.remaining[self.current_index]
        self.decision_map[_decision_key(current.day, current.section)] = {
            "day": current.day,
            "section": current.section,
            "decision": decision,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": self.reviewed_by,
        }
        if self.decision_source is not None:
            self.decision_map[_decision_key(current.day, current.section)]["decision_source"] = (
                self.decision_source
            )
        label = format_section_label(current.section)
        self.status_var.set(f"Saved: day {current.day} — {label} => {decision}")
        self._persist()
        self._render()

    def _approve(self) -> None:
        self._record("approved")

    def _reject(self) -> None:
        self._record("rejected")

    def _skip(self) -> None:
        if self.remaining:
            self.current_index = (self.current_index + 1) % len(self.remaining)
            self.status_var.set("Skipped: item left pending.")
            self._render()

    def _prev(self) -> None:
        if self.remaining:
            self.current_index = (self.current_index - 1) % len(self.remaining)
            self._render()

    def _next(self) -> None:
        if self.remaining:
            self.current_index = (self.current_index + 1) % len(self.remaining)
            self._render()

    def _quit(self) -> None:
        self._persist()
        self.root.destroy()

    def run(self) -> int:
        if not self.items:
            self.messagebox.showinfo("No pending sections", "The report contains no pending sections.")
        self.root.mainloop()
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open UI review for pending approvals.")
    parser.add_argument("--report", required=True, help="Path to approval-gate report JSON")
    parser.add_argument("--out", help="Output decisions JSON path")
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
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Ignore existing decisions file and start this report from scratch.",
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    output_path = _build_output_path(report_path, args.out)
    app = ApprovalReviewApp(
        report_path=report_path,
        output_path=output_path,
        reviewed_by=args.reviewed_by,
        decision_source=args.decision_source.strip() if args.decision_source else None,
        reset=args.reset,
    )
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
