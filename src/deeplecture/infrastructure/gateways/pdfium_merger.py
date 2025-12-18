"""PDF merger implementation using pypdfium2."""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from pathlib import Path

from deeplecture.domain.errors import PDFMergeError

logger = logging.getLogger(__name__)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_pdf_path(
    path: str,
    *,
    must_exist: bool,
    allowed_roots: tuple[Path, ...] | None,
) -> Path:
    resolved = Path(path).expanduser().resolve(strict=False)
    if resolved.suffix.lower() != ".pdf":
        raise PDFMergeError(f"Invalid PDF extension: {resolved.suffix}")
    if must_exist and not resolved.exists():
        raise PDFMergeError(f"PDF file not found: {resolved}")
    if allowed_roots and not any(_is_under(resolved, root) for root in allowed_roots):
        raise PDFMergeError("Path outside allowed directories")
    return resolved


class PdfiumMerger:
    """Merge multiple PDF files using pypdfium2."""

    def __init__(
        self,
        *,
        allowed_roots: set[str] | set[Path] | list[str] | list[Path] | tuple[str, ...] | None = None,
    ) -> None:
        if allowed_roots:
            root_strs = sorted({str(Path(p).expanduser().resolve(strict=False)) for p in allowed_roots})
            self._allowed_roots: tuple[Path, ...] | None = tuple(Path(p) for p in root_strs)
        else:
            self._allowed_roots = None

    def merge_pdfs(self, input_paths: list[str], output_path: str) -> None:
        if not input_paths:
            raise PDFMergeError("No input PDFs provided")

        # Validate all input paths
        inputs = [_validate_pdf_path(p, must_exist=True, allowed_roots=self._allowed_roots) for p in input_paths]

        # Validate output path
        out = _validate_pdf_path(output_path, must_exist=False, allowed_roots=self._allowed_roots)
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            import pypdfium2 as pdfium  # type: ignore[import]
        except ImportError as exc:
            raise PDFMergeError("pypdfium2 is required for PDF merging. Install it with 'uv add pypdfium2'.") from exc

        documents = []
        tmp_path: str | None = None
        try:
            for p in inputs:
                documents.append(pdfium.PdfDocument(str(p)))

            out_doc = pdfium.PdfDocument.new()
            try:
                for doc in documents:
                    out_doc.import_pages(doc)

                # Atomic write: save to temp file first, then replace
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    suffix=".pdf",
                    dir=str(out.parent),
                    delete=False,
                ) as f:
                    tmp_path = f.name

                out_doc.save(tmp_path)
            finally:
                out_doc.close()

            # Atomic replace
            os.replace(tmp_path, str(out))
            tmp_path = None  # Successfully replaced, don't delete in finally

        except PDFMergeError:
            raise
        except Exception as exc:
            logger.error("PDF merge failed: %s", exc)
            raise PDFMergeError(str(exc), len(input_paths)) from exc
        finally:
            for doc in documents:
                with contextlib.suppress(Exception):
                    doc.close()
            # Clean up temp file if something failed after creation
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)
