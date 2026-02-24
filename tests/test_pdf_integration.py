"""test_pdf_integration.py — End-to-end integration test for the Python-TypeScript PDF pipeline.

Tests the full path:
  SAMPLE_BOOK (Python fixture)
  → DocumentRenderer.render()  (Phase 002 Python rendering engine)
  → export_pdf()               (Phase 003 Python subprocess caller)
  → npx tsx ui/pdf/engine.ts   (Phase 003 TypeScript PDF engine)
  → raw PDF bytes

These tests verify the integration contract, not the PDF layout (which is covered
by Vitest engine tests in ui/pdf/__tests__/engine.test.ts).
"""

import pytest

from src.models.devotional import DevotionalBook
from src.models.document import DocumentRepresentation
from src.rendering.engine import DocumentRenderer
from src.api.pdf_export import export_pdf
from tests.fixtures.sample_devotional import SAMPLE_BOOK


@pytest.fixture(scope="module")
def sample_doc() -> DocumentRepresentation:
    """Render SAMPLE_BOOK once for all tests in this module."""
    return DocumentRenderer().render(SAMPLE_BOOK, "publish-ready")


def test_export_pdf_returns_bytes(sample_doc: DocumentRepresentation) -> None:
    """Full pipeline produces non-empty bytes."""
    pdf_bytes = export_pdf(sample_doc)
    assert len(pdf_bytes) > 0


def test_export_pdf_is_valid_pdf(sample_doc: DocumentRepresentation) -> None:
    """PDF bytes begin with the PDF magic bytes %PDF (ISO 32000-1)."""
    pdf_bytes = export_pdf(sample_doc)
    assert pdf_bytes[:4] == b"%PDF", f"Expected %PDF magic bytes, got: {pdf_bytes[:4]!r}"


def test_export_pdf_personal_mode() -> None:
    """Personal mode also produces valid PDF bytes."""
    doc = DocumentRenderer().render(SAMPLE_BOOK, "personal")
    pdf_bytes = export_pdf(doc, output_mode="personal")
    assert pdf_bytes[:4] == b"%PDF"


def test_export_pdf_size_is_reasonable(sample_doc: DocumentRepresentation) -> None:
    """PDF bytes are at least 10KB (too small = truncated/corrupt output)."""
    pdf_bytes = export_pdf(sample_doc)
    assert len(pdf_bytes) >= 10_000, f"PDF too small ({len(pdf_bytes)} bytes); may be corrupt"


def test_export_pdf_document_representation_contract() -> None:
    """export_pdf accepts a DocumentRepresentation and returns bytes — contract test."""
    doc = DocumentRenderer().render(SAMPLE_BOOK, "publish-ready")
    assert isinstance(doc, DocumentRepresentation)
    result = export_pdf(doc)
    assert isinstance(result, bytes)
