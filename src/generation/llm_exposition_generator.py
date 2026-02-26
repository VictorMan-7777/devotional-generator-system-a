"""llm_exposition_generator.py — Phase 012 LLM-backed exposition generator.

Generates ExpositionSection.text via a single LLM call, grounded by
deterministic RAG retrieval and a persisted GroundingMap artifact.

Contract:
- LLM is called exactly once per generate_exposition() call.
- Excerpts are retrieved deterministically via ExpositionRAG seed data.
- GroundingMap is built and saved before the LLM call.
- grounding_map_id is always truthy on the returned ExpositionSection.
- prayer_trace_map_id is NOT set here (prayer remains deterministic).
- No network calls beyond the injected llm.generate().
- No randomness. No embeddings. No vector DB.

Grounding slot assignment:
    Paragraph 1 (declaration): first available excerpt (context → theological → fallback)
    Paragraph 2 (context):     full context excerpt set from ExpositionRAG
    Paragraph 3 (theological): full theological excerpt set from ExpositionRAG
    Paragraph 4 (bridge):      first available excerpt (same as paragraph 1)

RAG shortage fallback:
    If a paragraph slot is empty after RAG retrieval, a synthetic fallback
    excerpt is inserted (source_title="RAG_SHORTAGE") so GroundingMapBuilder
    can always produce exactly 4 non-empty entries.
"""
from __future__ import annotations

from typing import Optional

from src.grounding_store.id_policy import create_grounding_map_id
from src.grounding_store.store import GroundingMapStore
from src.interfaces.rag import RetrievedExcerpt
from src.llm.interfaces import LLMClient
from src.models.devotional import ExpositionSection
from src.rag.exposition import ExpositionRAG
from src.rag.grounding import GroundingMapBuilder

# ---------------------------------------------------------------------------
# RAG shortage fallback excerpts
# ---------------------------------------------------------------------------

_SHORTAGE_CONTEXT = RetrievedExcerpt(
    text="SHORTAGE: no context excerpt available",
    source_title="RAG_SHORTAGE",
    author="",
    source_type="commentary",
)

_SHORTAGE_THEOLOGICAL = RetrievedExcerpt(
    text="SHORTAGE: no theological excerpt available",
    source_title="RAG_SHORTAGE",
    author="",
    source_type="commentary",
)

_SHORTAGE_GENERIC = RetrievedExcerpt(
    text="SHORTAGE: no excerpt available",
    source_title="RAG_SHORTAGE",
    author="",
    source_type="commentary",
)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_prompt(
    topic: str,
    passage_reference: str,
    context_excerpts: list[RetrievedExcerpt],
    theological_excerpts: list[RetrievedExcerpt],
) -> str:
    """Construct the LLM prompt for exposition generation.

    Includes topic, passage reference, grounding instruction, up to 3 verbatim
    excerpt blocks from each RAG set (skipping RAG_SHORTAGE entries), required
    paragraph structure, and target word count.
    """
    lines: list[str] = []

    lines.append(f"TOPIC: {topic}")
    lines.append(f"PASSAGE: {passage_reference}")
    lines.append("")
    lines.append(
        "INSTRUCTION: Use only the provided excerpts for claims; "
        "do not introduce extra facts."
    )
    lines.append("")

    # Collect up to 3 real excerpts from each set (skip shortage placeholders).
    real_context = [e for e in context_excerpts if e.source_title != "RAG_SHORTAGE"][:3]
    real_theological = [
        e for e in theological_excerpts if e.source_title != "RAG_SHORTAGE"
    ][:3]
    all_excerpts = real_context + real_theological

    if all_excerpts:
        lines.append("PROVIDED EXCERPTS:")
        for i, excerpt in enumerate(all_excerpts, start=1):
            lines.append(f"[{i}] \"{excerpt.text}\"")
            lines.append(f"    — {excerpt.author}, {excerpt.source_title}")
        lines.append("")

    lines.append("REQUIRED STRUCTURE:")
    lines.append(
        "Write exactly 4 paragraphs. Begin each paragraph with its name as the first word:"
    )
    lines.append("  1. declaration")
    lines.append("  2. context")
    lines.append("  3. theological")
    lines.append("  4. bridge")
    lines.append("")
    lines.append("TARGET LENGTH: 500-650 words total.")
    lines.append("VOICE: Do not use 'you' or 'your'. Use communal voice (we, our).")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class LLMExpositionGenerator:
    """LLM-backed exposition generator with deterministic RAG grounding.

    Retrieves excerpts via ExpositionRAG, persists a GroundingMap artifact,
    then generates ExpositionSection.text with a single LLM call.

    Args:
        llm:   Injectable LLMClient. Production may use an OpenAI adapter;
               tests inject FakeLLMClient. Must not be called more than once
               per generate_exposition() invocation.
        rag:   Optional ExpositionRAG instance. Defaults to ExpositionRAG()
               (seed-file backed, deterministic).
        store: Optional GroundingMapStore. If None, the store is instantiated
               at call-time using GroundingMapStore.DEFAULT_ROOT (the class
               attribute), which is monkeypatchable in tests.
    """

    def __init__(
        self,
        llm: LLMClient,
        rag: Optional[ExpositionRAG] = None,
        store: Optional[GroundingMapStore] = None,
    ) -> None:
        self._llm = llm
        self._rag = rag if rag is not None else ExpositionRAG()
        self._store = store

    def generate_exposition(
        self,
        exposition_id: str,
        topic: str,
        passage_reference: str,
    ) -> ExpositionSection:
        """Generate an ExpositionSection backed by a single LLM call.

        Steps:
          1. Retrieve context and theological excerpts via ExpositionRAG.
          2. Apply shortage fallback so all 4 paragraph slots are non-empty.
          3. Build a GroundingMap with a deterministic id and persist it.
          4. Build an LLM prompt from the retrieved excerpts and call llm.generate().
          5. Return ExpositionSection with truthy grounding_map_id.

        Args:
            exposition_id:      Stable identifier for this exposition
                                (e.g. "expo-grace-day1"). Used to derive the
                                deterministic grounding_map_id.
            topic:              Devotional topic string.
            passage_reference:  Scripture passage reference (e.g. "Romans 8:28").

        Returns:
            ExpositionSection with text from the LLM, computed word_count,
            and a truthy grounding_map_id referencing the saved artifact.
        """
        # ------------------------------------------------------------------
        # Step 1 — Retrieve excerpts deterministically via ExpositionRAG.
        # ------------------------------------------------------------------
        context_excerpts = self._rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference=passage_reference,
            topic=topic,
            source_types=["commentary"],
        )
        theological_excerpts = self._rag.retrieve_for_paragraph(
            paragraph_type="theological",
            passage_reference=passage_reference,
            topic=topic,
            source_types=["commentary"],
        )

        # ------------------------------------------------------------------
        # Step 2 — Build paragraph_excerpts dict with shortage fallbacks.
        #
        # Paragraphs 1 and 4 reuse the first available excerpt so all 4
        # slots are always non-empty (GroundingMapBuilder requires this).
        # ------------------------------------------------------------------
        para2 = context_excerpts if context_excerpts else [_SHORTAGE_CONTEXT]
        para3 = theological_excerpts if theological_excerpts else [_SHORTAGE_THEOLOGICAL]
        first = (context_excerpts + theological_excerpts)[:1] or [_SHORTAGE_GENERIC]

        paragraph_excerpts: dict[int, list[RetrievedExcerpt]] = {
            1: first,
            2: para2,
            3: para3,
            4: first,
        }

        # ------------------------------------------------------------------
        # Step 3 — Build GroundingMap, assign deterministic id, persist.
        # ------------------------------------------------------------------
        gm_id = create_grounding_map_id(exposition_id)
        gm = GroundingMapBuilder().build(
            exposition_id=exposition_id,
            paragraph_excerpts=paragraph_excerpts,
        )
        gm = gm.model_copy(update={"id": gm_id})

        active_store = (
            self._store
            if self._store is not None
            else GroundingMapStore(root_dir=GroundingMapStore.DEFAULT_ROOT)
        )
        active_store.save(gm)

        # ------------------------------------------------------------------
        # Step 4 — Build prompt and call LLM exactly once.
        # ------------------------------------------------------------------
        prompt = _build_prompt(topic, passage_reference, context_excerpts, theological_excerpts)
        text = self._llm.generate(prompt)

        # ------------------------------------------------------------------
        # Step 5 — Construct and return ExpositionSection.
        # ------------------------------------------------------------------
        word_count = len(text.split())
        return ExpositionSection(
            text=text,
            word_count=word_count,
            grounding_map_id=gm_id,
        )
