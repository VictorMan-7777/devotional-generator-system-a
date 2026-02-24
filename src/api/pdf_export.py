"""pdf_export.py — Python subprocess integration for TypeScript PDF engine.

Serializes a DocumentRepresentation to JSON and spawns the TypeScript
PDF engine as a subprocess. Returns raw PDF bytes from stdout.

Integration method: Option A (subprocess), as documented in constitution.md v1.3.
  stdin:  JSON payload — { "document": <DocumentRepresentation>, "output_mode": "..." }
  stdout: raw PDF bytes
  stderr: error messages (only on failure)

Invocation: npx tsx <project_root>/ui/pdf/engine.ts
"""

from __future__ import annotations

import json
import pathlib
import subprocess
from typing import Literal

from src.models.document import DocumentRepresentation

OutputMode = Literal["personal", "publish-ready"]

# Project root: src/api/pdf_export.py → src/api/ → src/ → project root
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ENGINE_PATH = _PROJECT_ROOT / "ui" / "pdf" / "engine.ts"


def export_pdf(
    document: DocumentRepresentation,
    output_mode: OutputMode = "publish-ready",
    timeout: int = 60,
) -> bytes:
    """
    Convert a DocumentRepresentation to a KDP-compliant PDF.

    Serializes the document to JSON and passes it to the TypeScript PDF engine
    via subprocess stdin. Returns raw PDF bytes received from stdout.

    Args:
        document: DocumentRepresentation produced by DocumentRenderer.render().
        output_mode: 'personal' (advisory compliance) or 'publish-ready'
                     (compliance enforced; violations block export).
        timeout: Maximum seconds to wait for the TypeScript engine. Default 60.

    Returns:
        Raw PDF bytes (ready to write to disk or return via HTTP).

    Raises:
        FileNotFoundError: if the TypeScript engine file does not exist.
        subprocess.CalledProcessError: if the engine exits with non-zero status.
        subprocess.TimeoutExpired: if the engine exceeds `timeout` seconds.
    """
    if not _ENGINE_PATH.exists():
        raise FileNotFoundError(
            f"TypeScript PDF engine not found at {_ENGINE_PATH}. "
            "Ensure 'pnpm install' has been run in the ui/ directory."
        )

    payload = json.dumps(
        {
            "document": json.loads(document.model_dump_json()),
            "output_mode": output_mode,
        }
    ).encode("utf-8")

    result = subprocess.run(
        ["npx", "tsx", str(_ENGINE_PATH)],
        input=payload,
        capture_output=True,
        cwd=str(_PROJECT_ROOT),
        timeout=timeout,
        check=True,
    )

    pdf_bytes = bytes(result.stdout)

    # Guard against stdout contamination: any console.log() in the TypeScript engine
    # would prepend text to the PDF bytes, producing a corrupt file.  Validate the
    # PDF magic bytes before returning.  If this assertion fires, check the TypeScript
    # engine for console.log / console.warn / console.info calls — all logging must
    # go to stderr only.
    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError(
            f"PDF export failed: stdout does not begin with %PDF magic bytes. "
            f"Got: {pdf_bytes[:20]!r}. "
            "TypeScript engine may be emitting console.log() to stdout — "
            "all logging must use process.stderr.write() instead."
        )

    return pdf_bytes
