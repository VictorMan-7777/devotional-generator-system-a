from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.rag.sqlite_catalog import load_quote_rows


def _default_output_path() -> Path:
    return Path("outputs") / "devotionals" / "quote-citation-backfill.csv"


def export_quote_citation_backfill(*, db_path: Path, seed_path: Path, out_path: Path) -> Path:
    rows = load_quote_rows(db_path=db_path, seed_path=seed_path, strict_db_only=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "author",
                "source_title",
                "publication_year",
                "citation_locator",
                "publisher",
                "publication_city",
                "source_url",
                "public_domain",
                "needs_enrichment",
                "quote_preview",
            ],
        )
        writer.writeheader()
        for row in rows:
            quote_text = str(row.get("quote_text", "") or "").strip()
            writer.writerow(
                {
                    "author": str(row.get("author", "") or "").strip(),
                    "source_title": str(row.get("source_title", "") or "").strip(),
                    "publication_year": str(row.get("publication_year", "") or "").strip(),
                    "citation_locator": str(row.get("citation_locator", "") or "").strip(),
                    "publisher": str(row.get("publisher", "") or "").strip(),
                    "publication_city": str(row.get("publication_city", "") or "").strip(),
                    "source_url": str(row.get("source_url", "") or "").strip(),
                    "public_domain": str(bool(row.get("public_domain", False))).lower(),
                    "needs_enrichment": str(
                        not (
                            str(row.get("citation_locator", "") or "").strip()
                            and str(row.get("publisher", "") or "").strip()
                            and str(row.get("publication_city", "") or "").strip()
                        )
                    ).lower(),
                    "quote_preview": quote_text[:120],
                }
            )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export quote-catalog citation fields to a CSV worklist so publisher/city/locator "
            "metadata can be backfilled from the current source URLs."
        )
    )
    parser.add_argument("--db-path", default="data/devg_registry.sqlite3", help="SQLite DB path")
    parser.add_argument(
        "--seed-path",
        default="data/quotes/seed-quotes.json",
        help="Seed quote catalog JSON used if the DB table is empty",
    )
    parser.add_argument(
        "--out",
        default=str(_default_output_path()),
        help="Output CSV path",
    )
    args = parser.parse_args(argv)

    out_path = export_quote_citation_backfill(
        db_path=Path(args.db_path),
        seed_path=Path(args.seed_path),
        out_path=Path(args.out),
    )
    print(f"BACKFILL_CSV={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
