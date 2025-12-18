"""PDF processing protocol interfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PdfRendererProtocol(Protocol):
    """
    Contract for PDF page rendering service.

    Implementations handle rendering PDF pages to image files.
    """

    def render_pages_to_images(
        self,
        pdf_path: str,
        output_dir: str,
        *,
        scale: float = 2.0,
    ) -> dict[int, str]:
        """
        Render PDF pages to image files.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save rendered images
            scale: Render scale factor (default 2.0 for high quality)

        Returns:
            Dict mapping 1-based page index to image file path.
            Note: Pages that fail to render are silently skipped.
            Callers should compare len(result) with expected page count
            if strict completeness is required.

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ImportError: If required PDF library is not installed
        """
        ...


@runtime_checkable
class PdfTextExtractorProtocol(Protocol):
    """
    Contract for PDF text extraction service.

    Implementations handle extracting text content from PDF files.
    """

    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text content from all pages of a PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text with page separators, or empty string if extraction fails

        Note:
            Returns empty string (not raises) if PDF is unreadable or library unavailable.
            This is intentional for graceful degradation.
        """
        ...
