from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.artifacts import (
    GroundingMap,
    GroundingMapEntry,
    PrayerTraceMap,
    PrayerTraceMapEntry,
)
from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    DailyDevotional,
    DevotionalInput,
    ExpositionSection,
    PrayerSection,
    ScriptureSection,
    SectionApprovalStatus,
    SendingPromptSection,
    TimelessWisdomSection,
)
from src.models.registry import QuoteRecord, ScriptureRecord, VolumeRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_grounding_entry(n: int) -> GroundingMapEntry:
    return GroundingMapEntry(
        paragraph_number=n,
        paragraph_name=f"para_{n}",
        sources_retrieved=["source_a"],
        excerpts_used=["excerpt_a"],
        how_retrieval_informed_paragraph="Informed the paragraph.",
    )


def _make_grounding_map(entry_count: int = 4) -> GroundingMap:
    return GroundingMap(
        id="gm-001",
        exposition_id="exp-001",
        entries=[_make_grounding_entry(i) for i in range(1, entry_count + 1)],
    )


def _make_prayer_entry(source_type: str) -> PrayerTraceMapEntry:
    return PrayerTraceMapEntry(
        element_text="Heavenly Father,",
        source_type=source_type,
        source_reference="Romans 8:15",
    )


def _now() -> datetime:
    return datetime.now()


def _make_daily_devotional() -> DailyDevotional:
    return DailyDevotional(
        day_number=1,
        timeless_wisdom=TimelessWisdomSection(
            quote_text="All is grace.",
            author="Author A",
            source_title="Source Book",
            page_or_url="p. 42",
            public_domain=True,
            verification_status="catalog_verified",
        ),
        scripture=ScriptureSection(
            reference="Romans 8:15",
            text="For you did not receive a spirit of slavery...",
            translation="NASB",
            retrieval_source="bolls_life",
            verification_status="verified",
        ),
        exposition=ExpositionSection(
            text="A" * 500,
            word_count=500,
            grounding_map_id="gm-001",
        ),
        be_still=BeStillSection(prompts=["Prompt 1", "Prompt 2", "Prompt 3"]),
        action_steps=ActionStepsSection(
            items=["Step one"],
            connector_phrase="This week,",
        ),
        prayer=PrayerSection(
            text="B" * 120,
            word_count=120,
            prayer_trace_map_id="ptm-001",
        ),
        created_at=_now(),
        last_modified=_now(),
    )


# ---------------------------------------------------------------------------
# DevotionalInput — num_days validation
# ---------------------------------------------------------------------------

class TestDevotionalInput:
    def test_default_num_days_is_six(self):
        d = DevotionalInput(topic="Grace")
        assert d.num_days == 6

    def test_accepts_num_days_1_through_7(self):
        for n in range(1, 8):
            d = DevotionalInput(topic="test", num_days=n)
            assert d.num_days == n

    def test_rejects_num_days_zero(self):
        with pytest.raises(ValidationError):
            DevotionalInput(topic="test", num_days=0)

    def test_rejects_num_days_eight(self):
        with pytest.raises(ValidationError):
            DevotionalInput(topic="test", num_days=8)

    def test_rejects_negative_num_days(self):
        with pytest.raises(ValidationError):
            DevotionalInput(topic="test", num_days=-1)

    def test_default_scripture_version_is_nasb(self):
        d = DevotionalInput(topic="Faith")
        assert d.scripture_version == "NASB"


# ---------------------------------------------------------------------------
# Section approval_status — all 6 section types default to PENDING
# ---------------------------------------------------------------------------

class TestSectionApprovalStatus:
    def test_timeless_wisdom_defaults_to_pending(self):
        s = TimelessWisdomSection(
            quote_text="q",
            author="a",
            source_title="t",
            page_or_url="p",
            public_domain=True,
            verification_status="catalog_verified",
        )
        assert s.approval_status == SectionApprovalStatus.PENDING

    def test_scripture_defaults_to_pending(self):
        s = ScriptureSection(
            reference="John 3:16",
            text="For God so loved...",
            translation="NASB",
            retrieval_source="bolls_life",
            verification_status="verified",
        )
        assert s.approval_status == SectionApprovalStatus.PENDING

    def test_exposition_defaults_to_pending(self):
        s = ExpositionSection(text="text", word_count=500, grounding_map_id="gm-1")
        assert s.approval_status == SectionApprovalStatus.PENDING

    def test_be_still_defaults_to_pending(self):
        s = BeStillSection(prompts=["p1", "p2", "p3"])
        assert s.approval_status == SectionApprovalStatus.PENDING

    def test_action_steps_defaults_to_pending(self):
        s = ActionStepsSection(items=["item1"], connector_phrase="This week,")
        assert s.approval_status == SectionApprovalStatus.PENDING

    def test_prayer_defaults_to_pending(self):
        s = PrayerSection(text="t", word_count=120, prayer_trace_map_id="ptm-1")
        assert s.approval_status == SectionApprovalStatus.PENDING

    def test_section_can_be_set_to_approved(self):
        s = BeStillSection(
            prompts=["p1", "p2", "p3"],
            approval_status=SectionApprovalStatus.APPROVED,
        )
        assert s.approval_status == SectionApprovalStatus.APPROVED


# ---------------------------------------------------------------------------
# GroundingMap — validator: exactly 4 entries, all non-empty
# ---------------------------------------------------------------------------

class TestGroundingMap:
    def test_accepts_exactly_four_entries(self):
        gm = _make_grounding_map(4)
        assert len(gm.entries) == 4

    def test_rejects_one_entry(self):
        with pytest.raises(ValidationError, match="exactly 4 entries"):
            _make_grounding_map(1)

    def test_rejects_three_entries(self):
        with pytest.raises(ValidationError, match="exactly 4 entries"):
            _make_grounding_map(3)

    def test_rejects_five_entries(self):
        with pytest.raises(ValidationError, match="exactly 4 entries"):
            _make_grounding_map(5)

    def test_rejects_empty_sources_retrieved(self):
        entries = [_make_grounding_entry(i) for i in range(1, 5)]
        entries[1] = GroundingMapEntry(
            paragraph_number=2,
            paragraph_name="context",
            sources_retrieved=[],  # empty — invalid
            excerpts_used=["excerpt"],
            how_retrieval_informed_paragraph="Informed.",
        )
        with pytest.raises(ValidationError, match="non-empty"):
            GroundingMap(id="gm-1", exposition_id="exp-1", entries=entries)

    def test_rejects_empty_excerpts_used(self):
        entries = [_make_grounding_entry(i) for i in range(1, 5)]
        entries[2] = GroundingMapEntry(
            paragraph_number=3,
            paragraph_name="theological",
            sources_retrieved=["source"],
            excerpts_used=[],  # empty — invalid
            how_retrieval_informed_paragraph="Informed.",
        )
        with pytest.raises(ValidationError, match="non-empty"):
            GroundingMap(id="gm-1", exposition_id="exp-1", entries=entries)


# ---------------------------------------------------------------------------
# PrayerTraceMap — validator: all entries traceable to known source types
# ---------------------------------------------------------------------------

class TestPrayerTraceMap:
    def test_accepts_all_valid_source_types(self):
        entries = [
            _make_prayer_entry("scripture"),
            _make_prayer_entry("exposition"),
            _make_prayer_entry("be_still"),
        ]
        ptm = PrayerTraceMap(id="ptm-1", prayer_id="pr-1", entries=entries)
        assert len(ptm.entries) == 3

    def test_rejects_invalid_source_type(self):
        entries = [_make_prayer_entry("unknown_source")]
        with pytest.raises(ValidationError, match="traceable"):
            PrayerTraceMap(id="ptm-1", prayer_id="pr-1", entries=entries)

    def test_rejects_mixed_valid_and_invalid(self):
        entries = [
            _make_prayer_entry("scripture"),
            _make_prayer_entry("not_valid"),
        ]
        with pytest.raises(ValidationError, match="traceable"):
            PrayerTraceMap(id="ptm-1", prayer_id="pr-1", entries=entries)

    def test_accepts_scripture_source_type(self):
        ptm = PrayerTraceMap(
            id="ptm-1",
            prayer_id="pr-1",
            entries=[_make_prayer_entry("scripture")],
        )
        assert ptm.entries[0].source_type == "scripture"


# ---------------------------------------------------------------------------
# Registry schemas — basic instantiation
# ---------------------------------------------------------------------------

class TestRegistrySchemas:
    def test_quote_record_instantiates(self):
        q = QuoteRecord(
            id="q-001",
            volume_id="vol-001",
            series_id="ser-001",
            quote_text="All is grace.",
            author="Author A",
            source_title="Book B",
            added_at=_now(),
        )
        assert q.author == "Author A"

    def test_scripture_record_instantiates(self):
        s = ScriptureRecord(
            id="s-001",
            volume_id="vol-001",
            reference="Romans 8:15",
            translation="NASB",
            added_at=_now(),
        )
        assert s.reference == "Romans 8:15"

    def test_volume_record_instantiates(self):
        v = VolumeRecord(
            id="v-001",
            series_id="ser-001",
            volume_number=1,
            created_at=_now(),
        )
        assert v.volume_number == 1
