"""
Series Registry — TC-05, FR-64–FR-72.

Persistent SQLite-backed registry tracking:
  - Quote usage across volumes/series (de-duplication + author distribution)
  - Scripture usage per volume (duplication warning)
  - Volume and series identity + parent-child relationships

De-duplication semantics (FR-65, FR-66):
  - Within-volume quote duplicate: raises DuplicateQuoteError (hard fail per FR-66)
    unless override_reason string is supplied.
  - Cross-volume quote duplicate (same series): raises CrossVolumeDuplicateError
    (flag per FR-65) unless override_reason string is supplied.
  - Scripture duplicate within volume: non-blocking; ScriptureUseResult.is_duplicate
    is True and warning_message is populated (FR-67).

Author distribution (FR-68):
  - get_author_distribution(volume_id) returns per-author quote counts for one volume.
  - get_parent_distribution_for_attribute(parent_volume_id, attribute) returns the
    distribution from a parent volume so child volumes can weight their RAG queries
    accordingly (FR-71). Supported attributes: "author", "source_title".

Backup (TC-05):
  - backup(volume_id, backup_path) copies the SQLite file to backup_path.

Network isolation: none — purely local SQLite; no external I/O.
"""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import Integer, String, Text, UniqueConstraint, create_engine, event, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from src.models.registry import (
    AutoresearchExperimentRecord,
    OutlinerSystemComparisonRecord,
    QuoteRecord,
    ResourceAcquisitionRequestRecord,
    ReviewSectionRecord,
    ScriptureRecord,
    TrainerRecommendationRecord,
    VolumeDayPlanRecord,
    VolumeDayQuoteRecord,
    VolumeRecord,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RegistryError(Exception):
    """Base class for all Series Registry errors."""


class DuplicateQuoteError(RegistryError):
    """
    Raised when a quote already appears in the same volume (FR-66).

    Pass override_reason to record_quote_use to bypass this check.
    """


class CrossVolumeDuplicateError(RegistryError):
    """
    Raised when a quote already appears in another volume of the same series (FR-65).

    Pass override_reason to record_quote_use to bypass this check.
    """


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------


@dataclass
class ScriptureUseResult:
    """
    Returned by record_scripture_use.

    is_duplicate is True when the same reference+translation already exists in
    the volume. The record is stored regardless (non-blocking per FR-67).
    """

    record: ScriptureRecord
    is_duplicate: bool
    warning_message: Optional[str] = field(default=None)


# ---------------------------------------------------------------------------
# SQLAlchemy ORM models (internal)
# ---------------------------------------------------------------------------


class _Base(DeclarativeBase):
    pass


class _SeriesRow(_Base):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)


class _VolumeRow(_Base):
    __tablename__ = "volumes"
    __table_args__ = (UniqueConstraint("series_id", "volume_number", name="uq_series_volume_number"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    series_id: Mapped[str] = mapped_column(String, nullable=False)
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parent_volume_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)


class _QuoteUseRow(_Base):
    __tablename__ = "quote_uses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    volume_id: Mapped[str] = mapped_column(String, nullable=False)
    series_id: Mapped[str] = mapped_column(String, nullable=False)
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String, nullable=False)
    source_title: Mapped[str] = mapped_column(String, nullable=False)
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime] = mapped_column(default=_utc_now)


class _ScriptureUseRow(_Base):
    __tablename__ = "scripture_uses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    volume_id: Mapped[str] = mapped_column(String, nullable=False)
    reference: Mapped[str] = mapped_column(String, nullable=False)
    translation: Mapped[str] = mapped_column(String, nullable=False)
    added_at: Mapped[datetime] = mapped_column(default=_utc_now)


class _VolumeDayPlanRow(_Base):
    __tablename__ = "volume_day_plan"
    __table_args__ = (
        UniqueConstraint("volume_id", "day_number", name="uq_volume_day_number"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    volume_id: Mapped[str] = mapped_column(String, nullable=False)
    series_id: Mapped[str] = mapped_column(String, nullable=False)
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    scripture_reference: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)


class _VolumeDayQuoteRow(_Base):
    __tablename__ = "volume_day_quotes"
    __table_args__ = (
        UniqueConstraint("volume_id", "day_number", name="uq_volume_quote_day_number"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    volume_id: Mapped[str] = mapped_column(String, nullable=False)
    series_id: Mapped[str] = mapped_column(String, nullable=False)
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String, nullable=False)
    source_title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)


class _ReviewSectionRow(_Base):
    __tablename__ = "review_sections"
    __table_args__ = (
        UniqueConstraint("run_slug", "day_number", "section_name", name="uq_review_run_day_section"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_slug: Mapped[str] = mapped_column(String, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_name: Mapped[str] = mapped_column(String, nullable=False)
    original_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    original_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    edited_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    edited_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    edited_plain: Mapped[str] = mapped_column(Text, nullable=False, default="")
    edit_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    edited_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")
    approval_decision: Mapped[str] = mapped_column(String, nullable=False, default="")
    operator_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_by: Mapped[str] = mapped_column(String, nullable=False, default="")
    decision_source: Mapped[str] = mapped_column(String, nullable=False, default="")
    reviewed_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")
    approved_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    approved_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")


class _AutoresearchExperimentRow(_Base):
    __tablename__ = "autoresearch_experiments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    worker_name: Mapped[str] = mapped_column(String, nullable=False)
    benchmark_name: Mapped[str] = mapped_column(String, nullable=False)
    benchmark_reference: Mapped[str] = mapped_column(String, nullable=False, default="")
    run_slug: Mapped[str] = mapped_column(String, nullable=False, default="")
    status: Mapped[str] = mapped_column(String, nullable=False, default="")
    attempted_change: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    learning_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keep_decision: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")
    completed_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")


class _ResourceAcquisitionRequestRow(_Base):
    __tablename__ = "resource_acquisition_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    requested_by: Mapped[str] = mapped_column(String, nullable=False)
    scripture_reference: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False, default="")
    worker_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requested_resource_kinds_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")
    completed_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")


class _TrainerRecommendationRow(_Base):
    __tablename__ = "trainer_recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trainer_name: Mapped[str] = mapped_column(String, nullable=False)
    worker_name: Mapped[str] = mapped_column(String, nullable=False)
    scripture_reference: Mapped[str] = mapped_column(String, nullable=False)
    passage_slug: Mapped[str] = mapped_column(String, nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    selection_stage: Mapped[str] = mapped_column(String, nullable=False, default="")
    status: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")
    consumed_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")


class _OutlinerSystemComparisonRow(_Base):
    __tablename__ = "outliner_system_comparisons"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scripture_reference: Mapped[str] = mapped_column(String, nullable=False)
    passage_slug: Mapped[str] = mapped_column(String, nullable=False, default="")
    range_label: Mapped[str] = mapped_column(String, nullable=False, default="")
    assignment_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    interaction_log_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    packet_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    reviewer_guidance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    artifact_paths_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    legacy_system_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    legacy_system_reference: Mapped[str] = mapped_column(String, nullable=False, default="")
    legacy_status: Mapped[str] = mapped_column(String, nullable=False, default="")
    legacy_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    legacy_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    legacy_metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    redesigned_system_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    redesigned_system_reference: Mapped[str] = mapped_column(String, nullable=False, default="")
    redesigned_status: Mapped[str] = mapped_column(String, nullable=False, default="")
    redesigned_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    redesigned_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    redesigned_metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    winner: Mapped[str] = mapped_column(String, nullable=False, default="")
    decision_status: Mapped[str] = mapped_column(String, nullable=False, default="")
    decision_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    comparison_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_by: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")
    completed_at_utc: Mapped[str] = mapped_column(String, nullable=False, default="")


# ---------------------------------------------------------------------------
# SeriesRegistry
# ---------------------------------------------------------------------------

# Attributes supported by get_parent_distribution_for_attribute.
_SUPPORTED_ATTRIBUTES: dict[str, type] = {
    "author": _QuoteUseRow,
    "source_title": _QuoteUseRow,
}


class SeriesRegistry:
    """
    Persistent Series Registry backed by SQLite (via SQLAlchemy 2.0).

    Inject a custom db_path in tests to isolate state (use pytest tmp_path).
    The default path is relative to the calling process working directory.
    """

    def __init__(self, db_path: Path = Path("registry.db")) -> None:
        self._db_path = db_path
        connect_args = {} if str(db_path) == ":memory:" else {"timeout": 30}
        engine = create_engine(f"sqlite:///{db_path}", connect_args=connect_args)

        if str(db_path) != ":memory:":
            @event.listens_for(engine, "connect")
            def _configure_sqlite(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA busy_timeout=30000")
                try:
                    cursor.execute("PRAGMA journal_mode=WAL")
                except Exception:
                    try:
                        # Fall back cleanly when WAL is unavailable on the current
                        # filesystem or SQLite context instead of failing the whole
                        # registry connection path.
                        cursor.execute("PRAGMA journal_mode=DELETE")
                    except Exception:
                        pass  # DB already in correct mode (e.g. over SMB where PRAGMA writes fail)
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

        _Base.metadata.create_all(engine)
        self._Session: sessionmaker[Session] = sessionmaker(engine)

    # ------------------------------------------------------------------
    # Series & Volume management
    # ------------------------------------------------------------------

    def create_series(self, series_id: str, title: Optional[str] = None) -> None:
        """
        Register a series.  Idempotent: silently succeeds if the series_id
        already exists (subsequent calls do not overwrite the title).
        """
        with self._Session() as session:
            existing = session.get(_SeriesRow, series_id)
            if existing is not None:
                return
            session.add(_SeriesRow(id=series_id, title=title))
            session.commit()

    def create_volume(
        self,
        volume_id: str,
        series_id: str,
        volume_number: int,
        title: Optional[str] = None,
        parent_volume_id: Optional[str] = None,
    ) -> VolumeRecord:
        """
        Register a volume within a series.

        parent_volume_id links child (in-depth) volumes to their parent (overview)
        volume for FR-70–FR-72 distribution surfacing.
        """
        with self._Session() as session:
            existing = session.scalar(
                select(_VolumeRow).where(
                    _VolumeRow.series_id == series_id,
                    _VolumeRow.volume_number == volume_number,
                )
            )
            if existing is not None:
                if title and not existing.title:
                    existing.title = title
                if parent_volume_id and not existing.parent_volume_id:
                    existing.parent_volume_id = parent_volume_id
                session.commit()
                return VolumeRecord(
                    id=existing.id,
                    series_id=existing.series_id,
                    volume_number=existing.volume_number,
                    title=existing.title,
                    parent_volume_id=existing.parent_volume_id,
                    created_at=existing.created_at,
                )
            row = _VolumeRow(
                id=volume_id,
                series_id=series_id,
                volume_number=volume_number,
                title=title,
                parent_volume_id=parent_volume_id,
                created_at=_utc_now(),
            )
            session.add(row)
            session.commit()
            return VolumeRecord(
                id=row.id,
                series_id=row.series_id,
                volume_number=row.volume_number,
                title=row.title,
                parent_volume_id=row.parent_volume_id,
                created_at=row.created_at,
            )

    def get_volume_by_number(self, series_id: str, volume_number: int) -> Optional[VolumeRecord]:
        with self._Session() as session:
            row = session.scalar(
                select(_VolumeRow).where(
                    _VolumeRow.series_id == series_id,
                    _VolumeRow.volume_number == volume_number,
                )
            )
            if row is None:
                return None
            return VolumeRecord(
                id=row.id,
                series_id=row.series_id,
                volume_number=row.volume_number,
                title=row.title,
                parent_volume_id=row.parent_volume_id,
                created_at=row.created_at,
            )

    def delete_volume(self, volume_id: str, *, delete_series_if_orphan: bool = False) -> bool:
        """Delete one volume and all of its registry-side usage records.

        Returns True when a volume row existed and was deleted; False otherwise.
        """
        with self._Session() as session:
            volume = session.get(_VolumeRow, volume_id)
            if volume is None:
                return False
            series_id = volume.series_id
            session.query(_QuoteUseRow).filter(_QuoteUseRow.volume_id == volume_id).delete()
            session.query(_ScriptureUseRow).filter(_ScriptureUseRow.volume_id == volume_id).delete()
            session.query(_VolumeDayPlanRow).filter(_VolumeDayPlanRow.volume_id == volume_id).delete()
            session.query(_VolumeDayQuoteRow).filter(_VolumeDayQuoteRow.volume_id == volume_id).delete()
            session.delete(volume)
            if delete_series_if_orphan:
                remaining = session.scalar(
                    select(func.count(_VolumeRow.id)).where(_VolumeRow.series_id == series_id)
                )
                if int(remaining or 0) == 0:
                    series = session.get(_SeriesRow, series_id)
                    if series is not None:
                        session.delete(series)
            session.commit()
            return True

    def record_volume_day_plan(
        self,
        *,
        volume_id: str,
        series_id: str,
        volume_number: int,
        day_number: int,
        week_number: int,
        topic: str,
        scripture_reference: str,
    ) -> VolumeDayPlanRecord:
        if day_number <= 0:
            raise ValueError("day_number must be > 0")
        if week_number <= 0:
            raise ValueError("week_number must be > 0")
        row = _VolumeDayPlanRow(
            id=str(uuid.uuid4()),
            volume_id=volume_id,
            series_id=series_id,
            volume_number=volume_number,
            day_number=day_number,
            week_number=week_number,
            topic=topic.strip(),
            scripture_reference=scripture_reference.strip(),
            created_at=_utc_now(),
        )
        with self._Session() as session:
            existing = session.scalar(
                select(_VolumeDayPlanRow).where(
                    _VolumeDayPlanRow.volume_id == volume_id,
                    _VolumeDayPlanRow.day_number == day_number,
                )
            )
            if existing is not None:
                existing.week_number = week_number
                existing.topic = topic.strip()
                existing.scripture_reference = scripture_reference.strip()
                session.commit()
                return VolumeDayPlanRecord(
                    id=existing.id,
                    volume_id=existing.volume_id,
                    series_id=existing.series_id,
                    volume_number=existing.volume_number,
                    day_number=existing.day_number,
                    week_number=existing.week_number,
                    topic=existing.topic,
                    scripture_reference=existing.scripture_reference,
                    created_at=existing.created_at,
                )
            session.add(row)
            session.commit()
            return VolumeDayPlanRecord(
                id=row.id,
                volume_id=row.volume_id,
                series_id=row.series_id,
                volume_number=row.volume_number,
                day_number=row.day_number,
                week_number=row.week_number,
                topic=row.topic,
                scripture_reference=row.scripture_reference,
                created_at=row.created_at,
            )

    def get_volume_day_plan(self, volume_id: str) -> list[VolumeDayPlanRecord]:
        with self._Session() as session:
            rows = session.execute(
                select(_VolumeDayPlanRow)
                .where(_VolumeDayPlanRow.volume_id == volume_id)
                .order_by(_VolumeDayPlanRow.day_number.asc())
            ).scalars()
            return [
                VolumeDayPlanRecord(
                    id=row.id,
                    volume_id=row.volume_id,
                    series_id=row.series_id,
                    volume_number=row.volume_number,
                    day_number=row.day_number,
                    week_number=row.week_number,
                    topic=row.topic,
                    scripture_reference=row.scripture_reference,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    def get_week_scripture_map_for_volume(self, volume_id: str) -> dict[int, set[str]]:
        refs_by_week: dict[int, set[str]] = {}
        for row in self.get_volume_day_plan(volume_id):
            refs_by_week.setdefault(row.week_number, set()).add(row.scripture_reference)
        return refs_by_week

    def record_volume_day_quote(
        self,
        *,
        volume_id: str,
        series_id: str,
        volume_number: int,
        day_number: int,
        week_number: int,
        quote_text: str,
        author: str,
        source_title: str,
    ) -> VolumeDayQuoteRecord:
        if day_number <= 0:
            raise ValueError("day_number must be > 0")
        if week_number <= 0:
            raise ValueError("week_number must be > 0")
        with self._Session() as session:
            existing = session.scalar(
                select(_VolumeDayQuoteRow).where(
                    _VolumeDayQuoteRow.volume_id == volume_id,
                    _VolumeDayQuoteRow.day_number == day_number,
                )
            )
            if existing is not None:
                existing.week_number = week_number
                existing.quote_text = quote_text.strip()
                existing.author = author.strip()
                existing.source_title = source_title.strip()
                session.commit()
                row = existing
            else:
                row = _VolumeDayQuoteRow(
                    id=str(uuid.uuid4()),
                    volume_id=volume_id,
                    series_id=series_id,
                    volume_number=volume_number,
                    day_number=day_number,
                    week_number=week_number,
                    quote_text=quote_text.strip(),
                    author=author.strip(),
                    source_title=source_title.strip(),
                    created_at=_utc_now(),
                )
                session.add(row)
                session.commit()
            return VolumeDayQuoteRecord(
                id=row.id,
                volume_id=row.volume_id,
                series_id=row.series_id,
                volume_number=row.volume_number,
                day_number=row.day_number,
                week_number=row.week_number,
                quote_text=row.quote_text,
                author=row.author,
                source_title=row.source_title,
                created_at=row.created_at,
            )

    def get_week_quote_map_for_volume(self, volume_id: str) -> dict[int, set[str]]:
        quotes_by_week: dict[int, set[str]] = {}
        with self._Session() as session:
            rows = session.execute(
                select(_VolumeDayQuoteRow)
                .where(_VolumeDayQuoteRow.volume_id == volume_id)
                .order_by(_VolumeDayQuoteRow.day_number.asc())
            ).scalars()
            for row in rows:
                quotes_by_week.setdefault(int(row.week_number), set()).add(row.quote_text)
        return quotes_by_week

    # ------------------------------------------------------------------
    # Quote usage
    # ------------------------------------------------------------------

    def record_quote_use(
        self,
        volume_id: str,
        series_id: str,
        quote_text: str,
        author: str,
        source_title: str,
        publication_year: Optional[int] = None,
        override_reason: Optional[str] = None,
    ) -> QuoteRecord:
        """
        Record a quote used in the given volume.

        Raises DuplicateQuoteError if the same quote_text already appears in
        the same volume and override_reason is not provided (FR-66).

        Raises CrossVolumeDuplicateError if the same quote_text already appears
        in a different volume of the same series and override_reason is not
        provided (FR-65).

        override_reason bypasses both checks and is stored in the record for
        auditing.
        """
        with self._Session() as session:
            # 1. Within-volume duplicate check (FR-66)
            within_vol_dup = session.scalar(
                select(_QuoteUseRow).where(
                    _QuoteUseRow.volume_id == volume_id,
                    _QuoteUseRow.quote_text == quote_text,
                )
            )
            if within_vol_dup is not None and not override_reason:
                raise DuplicateQuoteError(
                    f"Quote already used in volume '{volume_id}'. "
                    "Provide override_reason to record despite duplication."
                )

            # 2. Cross-volume duplicate check (FR-65)
            if within_vol_dup is None:  # only check cross-volume if not already within-vol dup
                cross_vol_dup = session.scalar(
                    select(_QuoteUseRow).where(
                        _QuoteUseRow.series_id == series_id,
                        _QuoteUseRow.quote_text == quote_text,
                        _QuoteUseRow.volume_id != volume_id,
                    )
                )
                if cross_vol_dup is not None and not override_reason:
                    raise CrossVolumeDuplicateError(
                        f"Quote already used in series '{series_id}' "
                        f"(volume '{cross_vol_dup.volume_id}'). "
                        "Provide override_reason to record despite cross-volume duplication."
                    )

            # 3. Insert record
            now = _utc_now()
            row = _QuoteUseRow(
                id=str(uuid.uuid4()),
                volume_id=volume_id,
                series_id=series_id,
                quote_text=quote_text,
                author=author,
                source_title=source_title,
                publication_year=publication_year,
                override_reason=override_reason,
                added_at=now,
            )
            session.add(row)
            session.commit()
            return QuoteRecord(
                id=row.id,
                volume_id=row.volume_id,
                series_id=row.series_id,
                quote_text=row.quote_text,
                author=row.author,
                source_title=row.source_title,
                publication_year=row.publication_year,
                added_at=row.added_at,
            )

    # ------------------------------------------------------------------
    # Scripture usage
    # ------------------------------------------------------------------

    def record_scripture_use(
        self,
        volume_id: str,
        reference: str,
        translation: str,
    ) -> ScriptureUseResult:
        """
        Record a scripture reference used in the given volume.

        Non-blocking: the record is always stored.  If the same reference and
        translation already appear in the volume, ScriptureUseResult.is_duplicate
        is True and warning_message is populated (FR-67).
        """
        with self._Session() as session:
            existing = session.scalar(
                select(_ScriptureUseRow).where(
                    _ScriptureUseRow.volume_id == volume_id,
                    _ScriptureUseRow.reference == reference,
                    _ScriptureUseRow.translation == translation,
                )
            )
            is_dup = existing is not None
            warning: Optional[str] = None
            if is_dup:
                warning = (
                    f"Scripture '{reference}' ({translation}) already used in "
                    f"volume '{volume_id}'. Review before export (FR-67)."
                )

            now = _utc_now()
            row = _ScriptureUseRow(
                id=str(uuid.uuid4()),
                volume_id=volume_id,
                reference=reference,
                translation=translation,
                added_at=now,
            )
            session.add(row)
            session.commit()
            record = ScriptureRecord(
                id=row.id,
                volume_id=row.volume_id,
                reference=row.reference,
                translation=row.translation,
                added_at=row.added_at,
            )
            return ScriptureUseResult(
                record=record,
                is_duplicate=is_dup,
                warning_message=warning,
            )

    # ------------------------------------------------------------------
    # Distribution queries (FR-68, FR-71)
    # ------------------------------------------------------------------

    def get_author_distribution(self, volume_id: str) -> dict[str, int]:
        """
        Return a per-author quote count for the given volume (FR-68).

        Example: {"C.S. Lewis": 3, "Spurgeon": 1}
        """
        with self._Session() as session:
            rows = session.execute(
                select(_QuoteUseRow.author, func.count(_QuoteUseRow.id))
                .where(_QuoteUseRow.volume_id == volume_id)
                .group_by(_QuoteUseRow.author)
            ).all()
            return {author: count for author, count in rows}

    def get_parent_distribution_for_attribute(
        self,
        parent_volume_id: str,
        attribute: str,
    ) -> dict[str, int]:
        """
        Return a per-value distribution for the given attribute from the parent
        volume (FR-71).

        Used by child (in-depth) volumes to understand the parent's quote
        concentration before RAG weighting is applied.

        Supported attributes: "author", "source_title".
        Raises ValueError for unsupported attributes.

        Example:
            get_parent_distribution_for_attribute("vol-001", "author")
            → {"C.S. Lewis": 2, "Spurgeon": 1}
        """
        if attribute not in _SUPPORTED_ATTRIBUTES:
            raise ValueError(
                f"Unsupported attribute '{attribute}'. "
                f"Supported: {sorted(_SUPPORTED_ATTRIBUTES)}"
            )
        col = getattr(_QuoteUseRow, attribute)
        with self._Session() as session:
            rows = session.execute(
                select(col, func.count(_QuoteUseRow.id))
                .where(_QuoteUseRow.volume_id == parent_volume_id)
                .group_by(col)
            ).all()
            return {value: count for value, count in rows}

    # ------------------------------------------------------------------
    # Backup (TC-05)
    # ------------------------------------------------------------------

    def backup(self, volume_id: str, backup_path: Path) -> None:
        """
        Copy the SQLite registry file to backup_path (TC-05).

        volume_id is validated to exist in the database before the copy
        to prevent silent no-op backups.

        Uses the sqlite3 online backup API so that WAL-mode databases are
        fully checkpointed into the destination file rather than leaving
        uncommitted pages in the WAL sidecar.
        """
        import sqlite3

        with self._Session() as session:
            volume = session.get(_VolumeRow, volume_id)
            if volume is None:
                raise RegistryError(
                    f"Cannot backup: volume '{volume_id}' not found in registry."
                )
            # Use the raw DBAPI connection to drive sqlite3's online backup API.
            src_conn: sqlite3.Connection = session.connection().connection
            with sqlite3.connect(str(backup_path)) as dst_conn:
                src_conn.backup(dst_conn)

    # ------------------------------------------------------------------
    # Review state
    # ------------------------------------------------------------------

    @staticmethod
    def _review_record_from_row(row: _ReviewSectionRow) -> ReviewSectionRecord:
        return ReviewSectionRecord(
            run_slug=row.run_slug,
            day_number=row.day_number,
            section_name=row.section_name,
            original_payload_json=row.original_payload_json,
            original_preview=row.original_preview,
            edited_payload_json=row.edited_payload_json,
            edited_html=row.edited_html,
            edited_plain=row.edited_plain,
            edit_note=row.edit_note,
            edited_at_utc=row.edited_at_utc,
            approval_decision=row.approval_decision,
            operator_note=row.operator_note,
            reviewed_by=row.reviewed_by,
            decision_source=row.decision_source,
            reviewed_at_utc=row.reviewed_at_utc,
            approved_payload_json=row.approved_payload_json,
            approved_preview=row.approved_preview,
        )

    def seed_review_section(
        self,
        *,
        run_slug: str,
        day_number: int,
        section_name: str,
        original_payload_json: str,
        original_preview: str,
    ) -> ReviewSectionRecord:
        with self._Session() as session:
            row = session.scalar(
                select(_ReviewSectionRow).where(
                    _ReviewSectionRow.run_slug == run_slug,
                    _ReviewSectionRow.day_number == day_number,
                    _ReviewSectionRow.section_name == section_name,
                )
            )
            if row is None:
                row = _ReviewSectionRow(
                    id=str(uuid.uuid4()),
                    run_slug=run_slug,
                    day_number=day_number,
                    section_name=section_name,
                    original_payload_json=original_payload_json or "{}",
                    original_preview=original_preview or "",
                )
                session.add(row)
            else:
                if row.original_payload_json in {"", "{}"} and original_payload_json:
                    row.original_payload_json = original_payload_json
                if not row.original_preview and original_preview:
                    row.original_preview = original_preview
            session.commit()
            return self._review_record_from_row(row)

    def list_review_sections(self, run_slug: str) -> list[ReviewSectionRecord]:
        with self._Session() as session:
            rows = session.execute(
                select(_ReviewSectionRow)
                .where(_ReviewSectionRow.run_slug == run_slug)
                .order_by(_ReviewSectionRow.day_number.asc(), _ReviewSectionRow.section_name.asc())
            ).scalars()
            return [self._review_record_from_row(row) for row in rows]

    def save_review_edit(
        self,
        *,
        run_slug: str,
        day_number: int,
        section_name: str,
        edited_payload_json: str,
        edited_html: str,
        edited_plain: str,
        edit_note: str,
        edited_at_utc: str,
    ) -> ReviewSectionRecord:
        with self._Session() as session:
            row = session.scalar(
                select(_ReviewSectionRow).where(
                    _ReviewSectionRow.run_slug == run_slug,
                    _ReviewSectionRow.day_number == day_number,
                    _ReviewSectionRow.section_name == section_name,
                )
            )
            if row is None:
                row = _ReviewSectionRow(
                    id=str(uuid.uuid4()),
                    run_slug=run_slug,
                    day_number=day_number,
                    section_name=section_name,
                )
                session.add(row)
            row.edited_payload_json = edited_payload_json or ""
            row.edited_html = edited_html or ""
            row.edited_plain = edited_plain or ""
            row.edit_note = edit_note or ""
            row.edited_at_utc = edited_at_utc or ""
            session.commit()
            return self._review_record_from_row(row)

    def save_review_decision(
        self,
        *,
        run_slug: str,
        day_number: int,
        section_name: str,
        approval_decision: str,
        operator_note: str,
        reviewed_by: str,
        decision_source: Optional[str],
        reviewed_at_utc: str,
        approved_payload_json: str,
        approved_preview: str,
    ) -> ReviewSectionRecord:
        with self._Session() as session:
            row = session.scalar(
                select(_ReviewSectionRow).where(
                    _ReviewSectionRow.run_slug == run_slug,
                    _ReviewSectionRow.day_number == day_number,
                    _ReviewSectionRow.section_name == section_name,
                )
            )
            if row is None:
                row = _ReviewSectionRow(
                    id=str(uuid.uuid4()),
                    run_slug=run_slug,
                    day_number=day_number,
                    section_name=section_name,
                )
                session.add(row)
            row.approval_decision = approval_decision or ""
            row.operator_note = operator_note or ""
            row.reviewed_by = reviewed_by or ""
            row.decision_source = decision_source or ""
            row.reviewed_at_utc = reviewed_at_utc or ""
            row.approved_payload_json = approved_payload_json or ""
            row.approved_preview = approved_preview or ""
            session.commit()
            return self._review_record_from_row(row)

    # ------------------------------------------------------------------
    # Autoresearch experiments
    # ------------------------------------------------------------------

    @staticmethod
    def _autoresearch_record_from_row(
        row: _AutoresearchExperimentRow,
    ) -> AutoresearchExperimentRecord:
        return AutoresearchExperimentRecord(
            experiment_id=row.id,
            worker_name=row.worker_name,
            benchmark_name=row.benchmark_name,
            benchmark_reference=row.benchmark_reference,
            run_slug=row.run_slug,
            status=row.status,
            attempted_change=row.attempted_change,
            metrics_json=row.metrics_json,
            learning_note=row.learning_note,
            keep_decision=row.keep_decision,
            created_at_utc=row.created_at_utc,
            completed_at_utc=row.completed_at_utc,
        )

    def log_autoresearch_experiment(
        self,
        *,
        experiment_id: str,
        worker_name: str,
        benchmark_name: str,
        benchmark_reference: str,
        run_slug: str,
        status: str,
        attempted_change: str,
        metrics_json: str,
        learning_note: str,
        keep_decision: str,
        created_at_utc: str,
        completed_at_utc: str,
    ) -> AutoresearchExperimentRecord:
        with self._Session() as session:
            row = session.get(_AutoresearchExperimentRow, experiment_id)
            if row is None:
                row = _AutoresearchExperimentRow(
                    id=experiment_id,
                    worker_name=worker_name.strip(),
                    benchmark_name=benchmark_name.strip(),
                )
                session.add(row)
            row.benchmark_reference = benchmark_reference.strip()
            row.run_slug = run_slug.strip()
            row.status = status.strip()
            row.attempted_change = attempted_change.strip()
            row.metrics_json = metrics_json or "{}"
            row.learning_note = learning_note.strip()
            row.keep_decision = keep_decision.strip()
            row.created_at_utc = created_at_utc.strip()
            row.completed_at_utc = completed_at_utc.strip()
            session.commit()
            return self._autoresearch_record_from_row(row)

    def list_autoresearch_experiments(
        self,
        *,
        worker_name: Optional[str] = None,
        benchmark_name: Optional[str] = None,
    ) -> list[AutoresearchExperimentRecord]:
        with self._Session() as session:
            stmt = select(_AutoresearchExperimentRow)
            if worker_name:
                stmt = stmt.where(_AutoresearchExperimentRow.worker_name == worker_name)
            if benchmark_name:
                stmt = stmt.where(_AutoresearchExperimentRow.benchmark_name == benchmark_name)
            rows = session.execute(
                stmt.order_by(_AutoresearchExperimentRow.created_at_utc.asc())
            ).scalars()
            return [self._autoresearch_record_from_row(row) for row in rows]

    @staticmethod
    def _resource_acquisition_record_from_row(
        row: _ResourceAcquisitionRequestRow,
    ) -> ResourceAcquisitionRequestRecord:
        try:
            resource_kinds = json.loads(row.requested_resource_kinds_json or "[]")
        except json.JSONDecodeError:
            resource_kinds = []
        return ResourceAcquisitionRequestRecord(
            request_id=row.id,
            requested_by=row.requested_by,
            scripture_reference=row.scripture_reference,
            topic=row.topic,
            worker_name=row.worker_name,
            reason=row.reason,
            requested_resource_kinds=list(resource_kinds or []),
            status=row.status,
            notes=row.notes,
            created_at_utc=row.created_at_utc,
            completed_at_utc=row.completed_at_utc,
        )

    def request_resource_acquisition(
        self,
        *,
        request_id: str,
        requested_by: str,
        scripture_reference: str,
        topic: str,
        worker_name: str,
        reason: str,
        requested_resource_kinds: list[str],
        status: str,
        notes: str,
        created_at_utc: str,
        completed_at_utc: str,
    ) -> ResourceAcquisitionRequestRecord:
        with self._Session() as session:
            row = session.get(_ResourceAcquisitionRequestRow, request_id)
            if row is None:
                row = _ResourceAcquisitionRequestRow(
                    id=request_id,
                    requested_by=requested_by.strip(),
                    scripture_reference=scripture_reference.strip(),
                )
                session.add(row)
            row.topic = topic.strip()
            row.worker_name = worker_name.strip()
            row.reason = reason.strip()
            row.requested_resource_kinds_json = json.dumps(
                list(requested_resource_kinds or []), sort_keys=True
            )
            row.status = status.strip()
            row.notes = notes.strip()
            row.created_at_utc = created_at_utc.strip()
            row.completed_at_utc = completed_at_utc.strip()
            session.commit()
            return self._resource_acquisition_record_from_row(row)

    def list_resource_acquisition_requests(
        self,
        *,
        requested_by: Optional[str] = None,
        worker_name: Optional[str] = None,
        scripture_reference: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[ResourceAcquisitionRequestRecord]:
        with self._Session() as session:
            stmt = select(_ResourceAcquisitionRequestRow)
            if requested_by:
                stmt = stmt.where(_ResourceAcquisitionRequestRow.requested_by == requested_by)
            if worker_name:
                stmt = stmt.where(_ResourceAcquisitionRequestRow.worker_name == worker_name)
            if scripture_reference:
                stmt = stmt.where(
                    _ResourceAcquisitionRequestRow.scripture_reference == scripture_reference
                )
            if status:
                stmt = stmt.where(_ResourceAcquisitionRequestRow.status == status)
            rows = session.execute(
                stmt.order_by(_ResourceAcquisitionRequestRow.created_at_utc.asc())
            ).scalars()
            return [self._resource_acquisition_record_from_row(row) for row in rows]

    def update_resource_acquisition_request(
        self,
        *,
        request_id: str,
        status: str,
        notes: str,
        completed_at_utc: str,
    ) -> ResourceAcquisitionRequestRecord:
        with self._Session() as session:
            row = session.get(_ResourceAcquisitionRequestRow, request_id)
            if row is None:
                raise RegistryError(f"Resource acquisition request '{request_id}' not found.")
            row.status = status.strip()
            row.notes = notes.strip()
            row.completed_at_utc = completed_at_utc.strip()
            session.commit()
            return self._resource_acquisition_record_from_row(row)

    @staticmethod
    def _trainer_recommendation_record_from_row(
        row: _TrainerRecommendationRow,
    ) -> TrainerRecommendationRecord:
        return TrainerRecommendationRecord(
            recommendation_id=row.id,
            trainer_name=row.trainer_name,
            worker_name=row.worker_name,
            scripture_reference=row.scripture_reference,
            passage_slug=row.passage_slug,
            priority=row.priority,
            rationale=row.rationale,
            selection_stage=row.selection_stage,
            status=row.status,
            created_at_utc=row.created_at_utc,
            consumed_at_utc=row.consumed_at_utc,
        )

    def record_trainer_recommendation(
        self,
        *,
        recommendation_id: str,
        trainer_name: str,
        worker_name: str,
        scripture_reference: str,
        passage_slug: str,
        priority: int,
        rationale: str,
        selection_stage: str,
        status: str,
        created_at_utc: str,
        consumed_at_utc: str,
    ) -> TrainerRecommendationRecord:
        with self._Session() as session:
            row = session.get(_TrainerRecommendationRow, recommendation_id)
            if row is None:
                row = _TrainerRecommendationRow(
                    id=recommendation_id,
                    trainer_name=trainer_name.strip(),
                    worker_name=worker_name.strip(),
                    scripture_reference=scripture_reference.strip(),
                )
                session.add(row)
            row.passage_slug = passage_slug.strip()
            row.priority = int(priority)
            row.rationale = rationale.strip()
            row.selection_stage = selection_stage.strip()
            row.status = status.strip()
            row.created_at_utc = created_at_utc.strip()
            row.consumed_at_utc = consumed_at_utc.strip()
            session.commit()
            return self._trainer_recommendation_record_from_row(row)

    def list_trainer_recommendations(
        self,
        *,
        trainer_name: Optional[str] = None,
        worker_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[TrainerRecommendationRecord]:
        with self._Session() as session:
            stmt = select(_TrainerRecommendationRow)
            if trainer_name:
                stmt = stmt.where(_TrainerRecommendationRow.trainer_name == trainer_name)
            if worker_name:
                stmt = stmt.where(_TrainerRecommendationRow.worker_name == worker_name)
            if status:
                stmt = stmt.where(_TrainerRecommendationRow.status == status)
            rows = session.execute(
                stmt.order_by(_TrainerRecommendationRow.priority.asc(), _TrainerRecommendationRow.created_at_utc.asc())
            ).scalars()
            return [self._trainer_recommendation_record_from_row(row) for row in rows]

    @staticmethod
    def _outliner_system_comparison_record_from_row(
        row: _OutlinerSystemComparisonRow,
    ) -> OutlinerSystemComparisonRecord:
        return OutlinerSystemComparisonRecord(
            comparison_id=row.id,
            scripture_reference=row.scripture_reference,
            passage_slug=row.passage_slug,
            range_label=row.range_label,
            assignment_payload_json=row.assignment_payload_json,
            interaction_log_json=row.interaction_log_json,
            packet_snapshot_json=row.packet_snapshot_json,
            reviewer_guidance_json=row.reviewer_guidance_json,
            artifact_paths_json=row.artifact_paths_json,
            legacy_system_name=row.legacy_system_name,
            legacy_system_reference=row.legacy_system_reference,
            legacy_status=row.legacy_status,
            legacy_score=row.legacy_score,
            legacy_summary=row.legacy_summary,
            legacy_metrics_json=row.legacy_metrics_json,
            redesigned_system_name=row.redesigned_system_name,
            redesigned_system_reference=row.redesigned_system_reference,
            redesigned_status=row.redesigned_status,
            redesigned_score=row.redesigned_score,
            redesigned_summary=row.redesigned_summary,
            redesigned_metrics_json=row.redesigned_metrics_json,
            winner=row.winner,
            decision_status=row.decision_status,
            decision_rationale=row.decision_rationale,
            comparison_notes=row.comparison_notes,
            reviewed_by=row.reviewed_by,
            created_at_utc=row.created_at_utc,
            completed_at_utc=row.completed_at_utc,
        )

    def record_outliner_system_comparison(
        self,
        *,
        comparison_id: str,
        scripture_reference: str,
        passage_slug: str,
        range_label: str,
        assignment_payload_json: str,
        interaction_log_json: str,
        packet_snapshot_json: str,
        reviewer_guidance_json: str,
        artifact_paths_json: str,
        legacy_system_name: str,
        legacy_system_reference: str,
        legacy_status: str,
        legacy_score: Optional[float],
        legacy_summary: str,
        legacy_metrics_json: str,
        redesigned_system_name: str,
        redesigned_system_reference: str,
        redesigned_status: str,
        redesigned_score: Optional[float],
        redesigned_summary: str,
        redesigned_metrics_json: str,
        winner: str,
        decision_status: str,
        decision_rationale: str,
        comparison_notes: str,
        reviewed_by: str,
        created_at_utc: str,
        completed_at_utc: str,
    ) -> OutlinerSystemComparisonRecord:
        with self._Session() as session:
            row = session.get(_OutlinerSystemComparisonRow, comparison_id)
            if row is None:
                row = _OutlinerSystemComparisonRow(
                    id=comparison_id,
                    scripture_reference=scripture_reference.strip(),
                )
                session.add(row)
            row.passage_slug = passage_slug.strip()
            row.range_label = range_label.strip()
            row.assignment_payload_json = assignment_payload_json or "{}"
            row.interaction_log_json = interaction_log_json or "{}"
            row.packet_snapshot_json = packet_snapshot_json or "{}"
            row.reviewer_guidance_json = reviewer_guidance_json or "{}"
            row.artifact_paths_json = artifact_paths_json or "{}"
            row.legacy_system_name = legacy_system_name.strip()
            row.legacy_system_reference = legacy_system_reference.strip()
            row.legacy_status = legacy_status.strip()
            row.legacy_score = legacy_score
            row.legacy_summary = legacy_summary.strip()
            row.legacy_metrics_json = legacy_metrics_json or "{}"
            row.redesigned_system_name = redesigned_system_name.strip()
            row.redesigned_system_reference = redesigned_system_reference.strip()
            row.redesigned_status = redesigned_status.strip()
            row.redesigned_score = redesigned_score
            row.redesigned_summary = redesigned_summary.strip()
            row.redesigned_metrics_json = redesigned_metrics_json or "{}"
            row.winner = winner.strip()
            row.decision_status = decision_status.strip()
            row.decision_rationale = decision_rationale.strip()
            row.comparison_notes = comparison_notes.strip()
            row.reviewed_by = reviewed_by.strip()
            row.created_at_utc = created_at_utc.strip()
            row.completed_at_utc = completed_at_utc.strip()
            session.commit()
            return self._outliner_system_comparison_record_from_row(row)

    def list_outliner_system_comparisons(
        self,
        *,
        scripture_reference: Optional[str] = None,
        passage_slug: Optional[str] = None,
        decision_status: Optional[str] = None,
    ) -> list[OutlinerSystemComparisonRecord]:
        with self._Session() as session:
            stmt = select(_OutlinerSystemComparisonRow)
            if scripture_reference:
                stmt = stmt.where(_OutlinerSystemComparisonRow.scripture_reference == scripture_reference)
            if passage_slug:
                stmt = stmt.where(_OutlinerSystemComparisonRow.passage_slug == passage_slug)
            if decision_status:
                stmt = stmt.where(_OutlinerSystemComparisonRow.decision_status == decision_status)
            rows = session.execute(
                stmt.order_by(_OutlinerSystemComparisonRow.created_at_utc.asc())
            ).scalars()
            return [self._outliner_system_comparison_record_from_row(row) for row in rows]
