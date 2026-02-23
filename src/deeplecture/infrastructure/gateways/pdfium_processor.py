"""PDF processing implementations using pypdfium2."""

from __future__ import annotations

import contextlib
import io
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces.upload import FileStorageProtocol

logger = logging.getLogger(__name__)


class PdfiumRenderer:
    """Render PDF pages to images using pypdfium2."""

    def __init__(self, file_storage: FileStorageProtocol) -> None:
        self._file_storage = file_storage

    def render_pages_to_images(
        self,
        pdf_path: str,
        output_dir: str,
        *,
        scale: float = 2.0,
    ) -> dict[int, str]:
        """
        Render PDF pages to PNG images.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save rendered images
            scale: Render scale factor (default 2.0)

        Returns:
            Dict mapping 1-based page index to image file path
        """
        if not self._file_storage.file_exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            import pypdfium2 as pdfium  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("pypdfium2 is required for PDF rendering. Install with 'uv add pypdfium2'.") from exc

        self._file_storage.makedirs(output_dir)
        images: dict[int, str] = {}

        doc = pdfium.PdfDocument(pdf_path)
        try:
            for index in range(len(doc)):
                page_idx = index + 1
                out_path = os.path.join(output_dir, f"page_{page_idx:03d}.png")

                page = None
                bitmap = None
                try:
                    page = doc.get_page(index)
                    bitmap = page.render(scale=scale)
                    pil_image = bitmap.to_pil()

                    # Route I/O through FileStorage protocol
                    buffer = io.BytesIO()
                    pil_image.save(buffer, format="PNG")
                    self._file_storage.write_bytes(out_path, buffer.getvalue())

                    images[page_idx] = out_path
                except Exception as exc:
                    logger.warning("Failed to render page %d: %s", page_idx, exc)
                finally:
                    if bitmap is not None:
                        with contextlib.suppress(Exception):
                            bitmap.close()
                    if page is not None:
                        with contextlib.suppress(Exception):
                            page.close()
        finally:
            with contextlib.suppress(Exception):
                doc.close()

        return images


class PdfiumTextExtractor:
    """Extract text from PDFs using pypdfium2."""

    def __init__(self, file_storage: FileStorageProtocol) -> None:
        self._file_storage = file_storage

    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text content from all pages of a PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text with page separators, or empty string if extraction fails
        """
        if not self._file_storage.file_exists(pdf_path):
            return ""

        try:
            import pypdfium2 as pdfium  # type: ignore[import]
        except ImportError:
            logger.warning("pypdfium2 not available; cannot extract PDF text")
            return ""

        try:
            doc = pdfium.PdfDocument(pdf_path)
            try:
                parts: list[str] = []

                for index in range(len(doc)):
                    page = None
                    textpage = None
                    try:
                        page = doc.get_page(index)
                        textpage = page.get_textpage()
                        raw = textpage.get_text_range()
                        page_text = (raw or "").strip()

                        if page_text:
                            parts.append(f"--- Page {index + 1} ---\n{page_text}")
                    except Exception as e:
                        logger.warning("Failed to read PDF page %d: %s", index + 1, e)
                        continue
                    finally:
                        if textpage is not None:
                            with contextlib.suppress(Exception):
                                textpage.close()
                        if page is not None:
                            with contextlib.suppress(Exception):
                                page.close()

                return "\n\n".join(parts) if parts else ""
            finally:
                with contextlib.suppress(Exception):
                    doc.close()

        except Exception as e:
            logger.error("Failed to read PDF %s: %s", pdf_path, e)
            return ""
