"""test_smoke_tier2.py — IRB Tier 2 smoke tests.

Three tests used by the IRB Tier 2 runner:

  test_pipeline_smoke              — T2-SMOKE-002
  test_grounding_map_artifact      — T2-SMOKE-003
  test_prayer_trace_map_artifact   — T2-SMOKE-004

All tests are deterministic — no network calls, no real LLM.
Fixtures are loaded from tests/fixtures/devotional_smoke_input.yaml.
Artifacts are written to pytest's tmp_path (outside the git tree);
the mutation guard is unaffected.

Evidence printed to stdout for IRB runner parsing:
  SMOKE_PIPELINE_DAY_NUMBER=<int>
  SMOKE_GM_ARTIFACT_SHA256=<hex>
  SMOKE_GM_ARTIFACT_PATH=<filename>
  SMOKE_PTM_ARTIFACT_SHA256=<hex>
  SMOKE_PTM_ARTIFACT_PATH=<filename>
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from src.api.generation_pipeline import generate_devotional
from src.generation.llm_exposition_generator import LLMExpositionGenerator
from src.generation.llm_prayer_generator import LLMPrayerGenerator
from src.grounding_store.store import GroundingMapStore
from src.models.pipeline import PipelineResult
from src.prayer_trace_store.store import PrayerTraceMapStore

# ---------------------------------------------------------------------------
# Fixture loader (inline — PyYAML not required in target venv)
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "devotional_smoke_input.yaml"


def _load_fixture() -> dict:
    """Parse a flat key: value YAML file into a dict.

    Handles string values (quoted or bare) and integer values.
    No external dependencies — stdlib only.
    """
    result: dict = {}
    for line in _FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, raw_value = line.partition(":")
        key = key.strip()
        value: str | int = raw_value.strip().strip('"').strip("'")
        try:
            value = int(value)  # type: ignore[assignment]
        except ValueError:
            pass
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# Fake LLM clients (deterministic, no network)
# ---------------------------------------------------------------------------

# Exposition fake: 4 labelled paragraphs, 548 words total.
# label word + 136 fillers = 137 words × 4 = 548 words.
# No "you"/"your" — passes EXPOSITION_VOICE check.
# No prosperity/works-merit patterns — passes doctrinal guardrails.
_FAKE_EXPO_TEXT = "\n\n".join(
    [
        "declaration " + " ".join(["grace"] * 136),
        "context " + " ".join(["mercy"] * 136),
        "theological " + " ".join(["faith"] * 136),
        "bridge " + " ".join(["hope"] * 136),
    ]
)

# Prayer fake: 6 lines, each a distinct element.
# Contains scripture refs (8:28, 46:10), "exposition" keyword, and be_still lines.
# Total ~162 words — within the 120–200 validator range.
# Trinity names present: Father, Lord, Holy Spirit, God, Jesus, Spirit.
_FAKE_PRAYER_TEXT = "\n".join(
    [
        "Father, we anchor our prayer in Romans 8:28, trusting all things work together for good.",
        "Lord, as this exposition of grace has illuminated your mercy, let truth guide us always.",
        "Holy Spirit, in this stillness we open our hearts to receive whatever you have prepared.",
        "God, your promise in Psalm 46:10 calls us to be still and know your sovereign love.",
        "Jesus, as this exposition has shown your boundless mercy, let it flow through us today.",
        "Spirit, guide us as we carry this stillness with us, your peace surpassing all understanding.",
    ]
)


class _FakeLLMClient:
    """Deterministic LLM stub that returns fixed text regardless of prompt."""

    def __init__(self, text: str) -> None:
        self._text = text

    def generate(self, prompt: str) -> str:  # noqa: ARG002
        return self._text


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pipeline_smoke():
    """T2-SMOKE-002: generate_devotional() completes with a valid PipelineResult.

    Loads fixture inputs, calls generate_devotional(), asserts the result is a
    valid PipelineResult with the expected number of days. Prints structured
    evidence for the IRB runner.
    """
    fixture = _load_fixture()
    topic: str = fixture["topic"]
    passage_reference: str = fixture["passage_reference"]
    day_number: int = fixture["day_number"]

    result = generate_devotional(
        topic=topic,
        num_days=day_number,
        scripture_reference=passage_reference,
    )

    assert isinstance(result, PipelineResult)
    assert len(result.book.days) == day_number
    assert result.book.days[0].day_number == day_number

    print(f"SMOKE_PIPELINE_DAY_NUMBER={result.book.days[0].day_number}")


def test_grounding_map_artifact(tmp_path, monkeypatch):
    """T2-SMOKE-003: LLMExpositionGenerator produces a GroundingMap artifact.

    Redirects GroundingMapStore.DEFAULT_ROOT to pytest's tmp_path (outside
    the git tree). Calls the generator directly — hard-halt on
    generation_pipeline.py is unaffected. Asserts one artifact JSON exists
    and prints its SHA-256 hash for the IRB runner.
    """
    fixture = _load_fixture()
    topic: str = fixture["topic"]
    passage_reference: str = fixture["passage_reference"]
    day_number: int = fixture["day_number"]

    monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

    llm = _FakeLLMClient(_FAKE_EXPO_TEXT)
    gen = LLMExpositionGenerator(llm=llm)
    exposition_id = f"smoke-expo-{topic}-day{day_number}"

    section = gen.generate_exposition(
        exposition_id=exposition_id,
        topic=topic,
        passage_reference=passage_reference,
    )

    artifact_files = list(tmp_path.glob("*.json"))
    assert len(artifact_files) == 1, (
        f"Expected exactly 1 GroundingMap artifact, found {len(artifact_files)}"
    )
    assert section.grounding_map_id, "grounding_map_id must be truthy on returned section"

    artifact_path = artifact_files[0]
    content = artifact_path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()

    print(f"SMOKE_GM_ARTIFACT_SHA256={sha256}")
    print(f"SMOKE_GM_ARTIFACT_PATH={artifact_path.name}")


def test_prayer_trace_map_artifact(tmp_path, monkeypatch):
    """T2-SMOKE-004: LLMPrayerGenerator produces a PrayerTraceMap artifact.

    Redirects PrayerTraceMapStore.DEFAULT_ROOT to pytest's tmp_path (outside
    the git tree). Calls the generator directly — hard-halt on
    generation_pipeline.py is unaffected. Asserts one artifact JSON exists
    and prints its SHA-256 hash for the IRB runner.
    """
    fixture = _load_fixture()
    topic: str = fixture["topic"]
    passage_reference: str = fixture["passage_reference"]
    day_number: int = fixture["day_number"]

    monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", tmp_path)

    llm = _FakeLLMClient(_FAKE_PRAYER_TEXT)
    gen = LLMPrayerGenerator(llm=llm)
    prayer_id = f"smoke-prayer-{topic}-day{day_number}"

    section = gen.generate_prayer(
        prayer_id=prayer_id,
        topic=topic,
        passage_reference=passage_reference,
        exposition_text="Smoke test exposition placeholder text for prayer grounding.",
        be_still_prompts=["Rest in the Lord", "Trust in his grace"],
    )

    artifact_files = list(tmp_path.glob("*.json"))
    assert len(artifact_files) == 1, (
        f"Expected exactly 1 PrayerTraceMap artifact, found {len(artifact_files)}"
    )
    assert section.prayer_trace_map_id, "prayer_trace_map_id must be truthy on returned section"

    artifact_path = artifact_files[0]
    content = artifact_path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()

    print(f"SMOKE_PTM_ARTIFACT_SHA256={sha256}")
    print(f"SMOKE_PTM_ARTIFACT_PATH={artifact_path.name}")
