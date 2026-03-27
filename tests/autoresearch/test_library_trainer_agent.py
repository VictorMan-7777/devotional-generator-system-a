from __future__ import annotations

import json

from src.autoresearch.library_trainer_agent import build_library_trainer_review


def test_library_trainer_review_flags_blank_and_metadata_packets(tmp_path) -> None:
    repo_root = tmp_path
    (repo_root / "data" / "library" / "reading-notes" / "drafts").mkdir(parents=True)
    (repo_root / "docs" / "system" / "outputs").mkdir(parents=True)

    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__devg__outliner-training-cycle.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "editorial_build": {
                            "passage_resources": {
                                "outliner_resources": [
                                    {"excerpt_text": "", "source_title": "Blank Resource"},
                                    {"excerpt_text": "publication_metadata, page_images", "source_title": "Metadata Resource"},
                                ],
                                "exposition_resources": [],
                            }
                        }
                    }
                ]
            }
        )
    )
    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__devg__exposition-training-cycle.json").write_text(
        json.dumps(
            {
                "assignments": [
                    {
                        "focal_reference": "James 1:2-3",
                        "context_reference": "James 1:2-3",
                    }
                ]
            }
        )
    )

    payload = build_library_trainer_review(repo_root)

    assert payload["packet_summary"]["blank_excerpt_count"] == 1
    assert payload["packet_summary"]["metadata_excerpt_count"] == 1
    titles = {item["title"] for item in payload["findings"]}
    assert "Workers are still receiving blank cuttings" in titles
    assert "Workers are still receiving metadata-shaped cuttings" in titles
