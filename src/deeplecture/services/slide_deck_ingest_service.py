from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from deeplecture.app_context import AppContext, get_app_context
from deeplecture.dto.slide import SlideDeckDTO
from deeplecture.dto.storage import ContentMetadata
from deeplecture.storage.metadata_storage import MetadataStorage, get_default_metadata_storage
from deeplecture.utils.fs import ensure_directory

UTC = getattr(datetime, "UTC", timezone.utc)
logger = logging.getLogger(__name__)


class DeckIngestService:
    """
    Handle ingest of PDF slide decks and creation of initial metadata.

    This service is intentionally dumb: it is only responsible for taking the
    uploaded file, choosing a stable deck_id, writing the PDF, and persisting
    the `ContentMetadata` record. Any downstream generation is orchestrated
    by higher-level services.
    """

    def __init__(
        self,
        metadata_storage: Optional[MetadataStorage] = None,
        upload_folder: Optional[str] = None,
        workspace_root: Optional[str] = None,
        app_context: Optional[AppContext] = None,
    ) -> None:
        ctx = app_context or get_app_context()
        ctx.init_paths()

        self._metadata_storage: MetadataStorage = (
            metadata_storage or get_default_metadata_storage()
        )
        self._upload_folder = upload_folder or ctx.content_dir
        self._workspace_root = workspace_root or ctx.content_dir

    # Public API ---------------------------------------------------------

    def register_deck(self, file_obj, filename: str) -> SlideDeckDTO:
        """
        Save an uploaded PDF and return basic deck metadata.
        """
        safe_filename = self._sanitize_filename(filename or "slides.pdf")
        base_name, _ext = os.path.splitext(safe_filename)
        base_deck_id = self._sanitize_id(base_name or "deck")

        deck_id = self._allocate_deck_id(base_deck_id)

        pdf_filename = f"{deck_id}.pdf"
        pdf_path = os.path.join(self._upload_folder, pdf_filename)
        deck_dir = self._deck_dir(deck_id)

        try:
            os.makedirs(self._upload_folder, exist_ok=True)
            file_obj.save(pdf_path)  # type: ignore[attr-defined]

            page_count = self._get_pdf_page_count(pdf_path)
            created_at = datetime.now(UTC).replace(tzinfo=None)

            ensure_directory(deck_dir)

            metadata = ContentMetadata(
                id=deck_id,
                type="slide",
                original_filename=filename,
                created_at=created_at.isoformat(),
                updated_at=created_at.isoformat(),
                source_file=pdf_path,
                pdf_page_count=int(page_count),
                status="uploaded",
                notes_path=None,
                ask_conversations_dir=None,
                screenshots_dir=None,
                timeline_path=None,
            )
            self._metadata_storage.save(metadata)
        except Exception as exc:
            logger.error("Failed to register deck %s: %s, rolling back", deck_id, exc)
            try:
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                if os.path.exists(deck_dir):
                    import shutil

                    shutil.rmtree(deck_dir)
            except OSError as cleanup_exc:
                logger.error(
                    "Failed to clean up after deck registration failure for %s: %s",
                    deck_id,
                    cleanup_exc,
                )
            raise

        return SlideDeckDTO(
            deck_id=deck_id,
            filename=filename,
            pdf_path=pdf_path,
            output_dir=deck_dir,
            page_count=page_count,
            created_at=created_at,
        )

    # Helpers ------------------------------------------------------------

    def _deck_dir(self, deck_id: str) -> str:
        return ensure_directory(self._workspace_root, "temp", self._sanitize_id(deck_id))

    def _allocate_deck_id(self, base_deck_id: str) -> str:
        deck_id = base_deck_id
        suffix = 1
        while self._metadata_storage.exists(deck_id):
            deck_id = f"{base_deck_id}_{suffix}"
            suffix += 1
        return deck_id

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        filename = filename.strip().replace("\\", "/")
        filename = os.path.basename(filename)
        return filename or "slides.pdf"

    @staticmethod
    def _sanitize_id(raw: str) -> str:
        import re

        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw.strip())
        return safe or "deck"

    @staticmethod
    def _get_pdf_page_count(pdf_path: str) -> int:
        try:
            import pypdfium2 as pdfium  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - env specific
            raise ImportError(
                "pypdfium2 is required for PDF slide support. "
                "Install it with 'uv add pypdfium2'.",
            ) from exc

        doc = pdfium.PdfDocument(pdf_path)
        try:
            return len(doc)
        finally:
            doc.close()
