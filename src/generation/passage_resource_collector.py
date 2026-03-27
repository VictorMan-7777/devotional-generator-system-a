from __future__ import annotations

from pathlib import Path

from src.models.pipeline import PassageResourceBundle
from src.rag.research_librarian import prepare_passage_resource_bundle


def collect_passage_resources(
    *,
    topic: str,
    scripture_reference: str,
    db_path: Path,
    num_days: int = 1,
    day_plan: list[dict] | None = None,
) -> PassageResourceBundle:
    """Collect passage resources via the research librarian (agentic RAG).

    Provides the librarian with the full study context — passage, topic,
    duration, and day-by-day breakdown — so it can curate resources that
    serve the whole arc, not just the opening verse.

    Args:
        topic: Devotional topic.
        scripture_reference: The main scripture passage for the whole study.
        db_path: Registry database path.
        num_days: Total days in the devotional (passed to the librarian for context).
        day_plan: List of per-day dicts with scripture_reference and topic,
                  so the librarian knows what each day covers.
    """
    return prepare_passage_resource_bundle(
        topic=topic,
        scripture_reference=scripture_reference,
        db_path=db_path,
        num_days=num_days,
        day_plan=day_plan,
    )
