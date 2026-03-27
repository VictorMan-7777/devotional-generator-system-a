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


def _has_quote_locator(section) -> bool:
    citation_locator = str(getattr(section, "citation_locator", "") or "").strip()
    source_url = str(getattr(section, "source_url", "") or "").strip()
    legacy = str(getattr(section, "page_or_url", "") or "").strip()
    return bool(citation_locator or source_url or legacy)


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

        PERSONAL mode:  any non-approved section → exportable=True with warnings.
        PUBLISH_READY:  any non-approved section → exportable=False.
        All approved:   exportable=True in either mode.
        """
        not_approved: list[str] = []
        turabian_missing: list[str] = []

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
                if section.approval_status != SectionApprovalStatus.APPROVED:
                    not_approved.append(f"day {day.day_number} — {name}")
            tw = day.timeless_wisdom
            if not str(tw.author or "").strip():
                turabian_missing.append(f"day {day.day_number} — timeless_wisdom.author")
            if not str(tw.source_title or "").strip():
                turabian_missing.append(f"day {day.day_number} — timeless_wisdom.source_title")
            if tw.publication_year is None:
                turabian_missing.append(f"day {day.day_number} — timeless_wisdom.publication_year")
            if not _has_quote_locator(tw):
                turabian_missing.append(
                    f"day {day.day_number} — timeless_wisdom.citation_locator_or_source_url"
                )

        if not not_approved and not turabian_missing:
            return ExportabilityResult(exportable=True)

        if output_mode == OutputMode.PERSONAL:
            warnings: list[str] = []
            warnings.extend([f"Section pending approval: {s}" for s in not_approved])
            warnings.extend([f"Turabian field missing: {s}" for s in turabian_missing])
            return ExportabilityResult(
                exportable=True,
                warnings=warnings,
            )

        # PUBLISH_READY
        reasons: list[str] = []
        if not_approved:
            reasons.append(
                f"{len(not_approved)} section(s) pending approval: " + "; ".join(not_approved)
            )
        if turabian_missing:
            reasons.append(
                f"{len(turabian_missing)} Turabian field(s) missing: " + "; ".join(turabian_missing)
            )
        return ExportabilityResult(
            exportable=False,
            blocked_reason=" | ".join(reasons),
        )
