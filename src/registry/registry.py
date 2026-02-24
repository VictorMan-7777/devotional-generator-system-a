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

import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import Integer, String, Text, create_engine, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from src.models.registry import QuoteRecord, ScriptureRecord, VolumeRecord


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
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class _VolumeRow(_Base):
    __tablename__ = "volumes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    series_id: Mapped[str] = mapped_column(String, nullable=False)
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parent_volume_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


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
    added_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class _ScriptureUseRow(_Base):
    __tablename__ = "scripture_uses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    volume_id: Mapped[str] = mapped_column(String, nullable=False)
    reference: Mapped[str] = mapped_column(String, nullable=False)
    translation: Mapped[str] = mapped_column(String, nullable=False)
    added_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


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
        engine = create_engine(f"sqlite:///{db_path}")
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
            row = _VolumeRow(
                id=volume_id,
                series_id=series_id,
                volume_number=volume_number,
                title=title,
                parent_volume_id=parent_volume_id,
                created_at=datetime.utcnow(),
            )
            session.add(row)
            session.commit()
            return VolumeRecord(
                id=row.id,
                series_id=row.series_id,
                volume_number=row.volume_number,
                title=row.title,
                created_at=row.created_at,
            )

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
            now = datetime.utcnow()
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

            now = datetime.utcnow()
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
        """
        with self._Session() as session:
            volume = session.get(_VolumeRow, volume_id)
            if volume is None:
                raise RegistryError(
                    f"Cannot backup: volume '{volume_id}' not found in registry."
                )
        shutil.copy2(str(self._db_path), str(backup_path))
