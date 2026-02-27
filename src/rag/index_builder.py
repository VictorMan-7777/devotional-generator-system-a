"""index_builder.py — TF-IDF corpus index builder.

build() is pure computation with no disk writes.
save() is the only code path that writes index data to disk.
load() reads and validates an existing index file.

Usage (via scripts/rag/build-index.py — run manually when corpus changes):
    builder = CorpusIndexBuilder()
    index = builder.build(corpus_path)
    builder.save(index, index_path)
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List

from src.rag.corpus import format_source_title, load_corpus

_SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Deterministic tokenizer: lowercase → strip non-alnum-whitespace → split."""
    cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return cleaned.split()


# ---------------------------------------------------------------------------
# Index validation helper
# ---------------------------------------------------------------------------

_REQUIRED_INDEX_KEYS = (
    "schema_version",
    "corpus_file",
    "corpus_version",
    "num_documents",
    "vocabulary",
    "idf",
    "documents",
)


def _validate_index(index: dict) -> None:
    """Raise ValueError if required index keys are missing or wrong type."""
    for key in _REQUIRED_INDEX_KEYS:
        if key not in index:
            raise ValueError(f"Index JSON missing required key: '{key}'")
    if not isinstance(index["vocabulary"], list):
        raise ValueError("Index 'vocabulary' must be a list")
    if not isinstance(index["idf"], dict):
        raise ValueError("Index 'idf' must be a dict")
    if not isinstance(index["documents"], list):
        raise ValueError("Index 'documents' must be a list")


# ---------------------------------------------------------------------------
# CorpusIndexBuilder
# ---------------------------------------------------------------------------

class CorpusIndexBuilder:
    """Build, save, and load TF-IDF index files for a corpus."""

    def build(self, corpus_path: Path) -> dict:
        """Build TF-IDF index dict from a corpus file. No disk writes.

        Reads corpus_path to extract documents and provenance metadata, then
        computes a TF-IDF index with a sorted vocabulary and smoothed IDF.
        All float values are rounded to 10 decimal places for cross-platform
        stability.

        Args:
            corpus_path: Path to a corpus JSON file following Section B-1 schema.

        Returns:
            Index dict suitable for serialization by save().
        """
        corpus_path = Path(corpus_path).resolve()

        # Read provenance block for corpus_version metadata
        with open(corpus_path, encoding="utf-8") as fh:
            raw_data = json.load(fh)
        provenance = raw_data.get("provenance", {})
        corpus_version = provenance.get("corpus_version", "")

        # Load and validate documents (read-only operation)
        docs = load_corpus(corpus_path)

        # Tokenize all documents
        all_doc_tokens: List[List[str]] = [_tokenize(doc.text) for doc in docs]

        # Build vocabulary: sorted set of all unique tokens across all documents
        vocab_set: set[str] = set()
        for tokens in all_doc_tokens:
            vocab_set.update(tokens)
        vocabulary: List[str] = sorted(vocab_set)

        # Compute smoothed IDF for each vocabulary term
        # Formula: IDF[t] = log((N + 1) / (df[t] + 1)) + 1
        N = len(docs)
        idf: Dict[str, float] = {}
        for term in vocabulary:
            df = sum(1 for tokens in all_doc_tokens if term in set(tokens))
            idf[term] = round(math.log((N + 1) / (df + 1)) + 1, 10)

        # Compute per-document TF-IDF vectors
        # Formula: TF[doc][t] = count(t in doc) / len(doc_tokens)
        #          TFIDF[doc][t] = round(TF * IDF, 10)
        doc_entries = []
        for doc, tokens in zip(docs, all_doc_tokens):
            if not tokens:
                tfidf: Dict[str, float] = {}
            else:
                tf_counts = Counter(tokens)
                doc_len = len(tokens)
                tfidf = {
                    t: round((count / doc_len) * idf[t], 10)
                    for t, count in tf_counts.items()
                    if t in vocab_set
                }
            doc_entries.append({
                "source_id": doc.source_id,
                "source_title": format_source_title(doc.source_id, doc.canonical_citation),
                "paragraph_type": doc.paragraph_type,
                "source_type": doc.source_type,
                "tfidf": tfidf,
            })

        # Store a portable relative corpus path to avoid embedding absolute paths
        # Navigate: {project_root}/data/corpus/file.json → project_root is 3 parents up
        try:
            project_root = corpus_path.parent.parent.parent
            corpus_file_label = str(corpus_path.relative_to(project_root))
        except ValueError:
            corpus_file_label = corpus_path.name

        return {
            "schema_version": _SCHEMA_VERSION,
            "corpus_file": corpus_file_label,
            "corpus_version": corpus_version,
            "num_documents": N,
            "vocabulary": vocabulary,
            "idf": idf,
            "documents": doc_entries,
        }

    def save(self, index: dict, index_path: Path) -> None:
        """Serialize index dict to disk.

        Uses sort_keys=True for deterministic JSON output.

        Args:
            index: Index dict as returned by build().
            index_path: Destination file path. Parent dirs created if needed.
        """
        index_path = Path(index_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(index, sort_keys=True, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self, index_path: Path) -> dict:
        """Load and validate an index file from disk.

        Args:
            index_path: Path to an index JSON file produced by save().

        Returns:
            Index dict.

        Raises:
            FileNotFoundError: if index_path does not exist.
            ValueError: if the index is missing required keys.
        """
        index_path = Path(index_path)
        if not index_path.exists():
            raise FileNotFoundError(f"Index file not found: {index_path}")

        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)

        _validate_index(index)
        return index
