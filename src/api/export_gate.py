"""export_gate.py — Phase 004.D export eligibility check.

Python-layer pre-flight before calling export_pdf(). Inspects per-section
approval_status on every section of every day and returns an ExportabilityResult.

Never raises. Never mutates the book.
OutputMode and SectionApprovalStatus are imported from src.models.devotional
(canonical location); not redefined here.
"""
from __future__ import annotations

from src.models.devotional import (
    DevotionalBook,
    OutputMode,
    SectionApprovalStatus,
)
from src.models.pipeline import ExportabilityResult


class ExportGate:
    def check_exportability(
        self,
        book: DevotionalBook,
        output_mode: OutputMode,
    ) -> ExportabilityResult:
        """Return export eligibility for the given book and output mode.

        Checks approval_status on every present section of every day:
          timeless_wisdom, scripture, exposition, be_still, action_steps, prayer,
          plus sending_prompt and day7 if they are not None.

        PERSONAL mode:  any PENDING → exportable=True with warnings populated.
        PUBLISH_READY:  any PENDING → exportable=False with blocked_reason set.
        No PENDING:     exportable=True in either mode.
        """
        pending: list[str] = []

        for day in book.days:
            always_present = [
                ("timeless_wisdom", day.timeless_wisdom),
                ("scripture", day.scripture),
                ("exposition", day.exposition),
                ("be_still", day.be_still),
                ("action_steps", day.action_steps),
                ("prayer", day.prayer),
            ]
            optional = []
            if day.sending_prompt is not None:
                optional.append(("sending_prompt", day.sending_prompt))
            if day.day7 is not None:
                optional.append(("day7", day.day7))

            for name, section in always_present + optional:
                if section.approval_status == SectionApprovalStatus.PENDING:
                    pending.append(f"day {day.day_number} — {name}")

        if not pending:
            return ExportabilityResult(exportable=True)

        if output_mode == OutputMode.PERSONAL:
            return ExportabilityResult(
                exportable=True,
                warnings=[f"Section pending approval: {s}" for s in pending],
            )

        # PUBLISH_READY
        return ExportabilityResult(
            exportable=False,
            blocked_reason=(
                f"{len(pending)} section(s) pending approval: "
                + "; ".join(pending)
            ),
        )
