"""
generate_cover.py — Generate three KDP cover designs for a devotional.

Usage:
    python -m scripts.generate_cover \
        --title "Trusting God in Uncertainty" \
        --subtitle "A 3-Day Devotional on Psalm 23" \
        --page-count 60 \
        --output-dir outputs/covers/

Optional env vars:
    UNSPLASH_ACCESS_KEY — enables photo background on Design 3 (Sanctuary)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cover.concepts import ALL_CONCEPTS
from src.cover.engine import render_cover

_DEFAULT_BLURB = (
    "What does it mean to trust God when the path ahead is unclear? "
    "This three-day devotional walks through the timeless words of Psalm 23, "
    "inviting you to encounter the Shepherd who leads, restores, and accompanies "
    "his people through every valley. Each day pairs careful exposition with "
    "guided reflection, honest prayer, and concrete steps of faithfulness. "
    "Whether you face uncertainty in work, relationships, health, or purpose, "
    "these pages will ground your trust in the God who has never abandoned his "
    "flock. Open these pages slowly. Let the Psalm speak before you respond. "
    "The Shepherd is already ahead of you."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate KDP cover designs.")
    parser.add_argument("--title", default="Trusting God in Uncertainty")
    parser.add_argument("--subtitle", default="A 3-Day Devotional on Psalm 23")
    parser.add_argument("--author", default="Sacred Whispers Publishers")
    parser.add_argument("--blurb", default=_DEFAULT_BLURB)
    parser.add_argument("--website", default="sacredwhisperspublishing.com")
    parser.add_argument("--page-count", type=int, default=60)
    parser.add_argument("--output-dir", default="outputs/covers")
    parser.add_argument("--design", choices=["all"] + [c.design_id for c in ALL_CONCEPTS], default="all")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    concepts = ALL_CONCEPTS if args.design == "all" else [c for c in ALL_CONCEPTS if c.design_id == args.design]

    for concept in concepts:
        print(f"Rendering: {concept.name} ({concept.design_id})...")
        paths = render_cover(
            concept,
            title=args.title,
            subtitle=args.subtitle,
            author=args.author,
            blurb=args.blurb,
            website=args.website,
            page_count=args.page_count,
            output_dir=output_dir,
        )
        print(f"  PNG: {paths['png']}")
        print(f"  PDF: {paths['pdf']}")

    print(f"\nAll {len(concepts)} cover design(s) saved to {output_dir}/")


if __name__ == "__main__":
    main()
