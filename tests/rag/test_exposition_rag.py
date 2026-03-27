from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.rag.exposition import ExpositionRAG

# Seed with only Genesis excerpts — isolated from the production DB so the test
# verifies filtering logic without depending on whatever entries happen to be in
# data/devg_registry.sqlite3 at runtime.
_GENESIS_ONLY_SEED = [
    {
        "text": "In the beginning God created the heavens and the earth, a passage about creation.",
        "source_title": "Commentary on Genesis",
        "author": "Calvin",
        "source_type": "commentary",
        "paragraph_type": "context",
        # passage_reference set — triggers direct-match path, excludes non-Genesis queries
        "passage_reference": "genesis 1:1",
    },
    {
        "text": "The covenant with Abraham establishes the redemptive arc of Scripture.",
        "source_title": "Biblical Theology",
        "author": "Geerhardus Vos",
        "source_type": "reference",
        "paragraph_type": "theological",
        "passage_reference": "genesis 17:1",
    },
]


def test_non_matching_passage_does_not_return_genesis_excerpts() -> None:
    """Genesis-only catalog must not return results when querying a Matthew passage."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(_GENESIS_ONLY_SEED, f)
        seed_path = Path(f.name)

    try:
        rag = ExpositionRAG(excerpts_path=seed_path)
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Matthew 26:5-9",
            topic="costly devotion",
            source_types=["commentary", "reference"],
        )
        assert results == []
    finally:
        seed_path.unlink(missing_ok=True)
