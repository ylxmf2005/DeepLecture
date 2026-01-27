"""PDF processing protocols."""

from __future__ import annotations

from typing import Protocol


class PdfRendererProtocol(Protocol):
    """Protocol for PDF rendering."""

    def render_page(
        self,
        pdf_path: str,
        page_number: int,
        output_path: str,
        *,
        dpi: int = 150,
    ) -> str:
        """Render a PDF page to an image.

        Args:
            pdf_path: Path to PDF file.
            page_number: Page number (0-indexed).
            output_path: Output image path.
            dpi: Resolution in DPI.

        Returns:
            Path to rendered image.
        """
        ...

    def get_page_count(self, pdf_path: str) -> int:
        """Get the number of pages in a PDF.

        Args:
            pdf_path: Path to PDF file.

        Returns:
            Number of pages.
        """
        ...


class PdfTextExtractorProtocol(Protocol):
    """Protocol for PDF text extraction."""

    def extract_text(self, pdf_path: str) -> str:
        """Extract text from PDF.

        Args:
            pdf_path: Path to PDF file.

        Returns:
            Extracted text content.
        """
        ...

    def extract_text_by_page(self, pdf_path: str) -> list[str]:
        """Extract text from PDF page by page.

        Args:
            pdf_path: Path to PDF file.

        Returns:
            List of text content per page.
        """
        ...
