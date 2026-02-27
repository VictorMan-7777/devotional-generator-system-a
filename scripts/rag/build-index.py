#!/usr/bin/env python3
"""build-index.py — Rebuild the TF-IDF index for data/corpus/excerpts-corpus.json.

Run manually when corpus content changes. Output is committed to git.
Do NOT call this from application code — retrieval code must never auto-build. [AC-1]

Usage (from devotional-generator project root):
    python3 scripts/rag/build-index.py

Reads:  data/corpus/excerpts-corpus.json
Writes: data/index/excerpts-index.json
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path for src.rag imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.rag.index_builder import CorpusIndexBuilder


def main() -> None:
    corpus_path = _PROJECT_ROOT / "data" / "corpus" / "excerpts-corpus.json"
    index_path = _PROJECT_ROOT / "data" / "index" / "excerpts-index.json"

    if not corpus_path.exists():
        print(f"ERROR: corpus file not found: {corpus_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Building TF-IDF index...")
    print(f"  Corpus: {corpus_path}")
    print(f"  Index:  {index_path}")

    builder = CorpusIndexBuilder()
    index = builder.build(corpus_path)
    builder.save(index, index_path)

    print(f"\nIndex written successfully.")
    print(f"  Documents indexed:  {index['num_documents']}")
    print(f"  Vocabulary size:    {len(index['vocabulary'])}")
    print(f"  Schema version:     {index['schema_version']}")
    print(f"  Corpus version:     {index['corpus_version']}")


if __name__ == "__main__":
    main()
