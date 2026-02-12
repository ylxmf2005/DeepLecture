"""Shared context loading helpers for AI generation use cases."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.domain.entities.content import ContentMetadata
    from deeplecture.use_cases.interfaces import PathResolverProtocol, PdfTextExtractorProtocol

logger = logging.getLogger(__name__)


def build_slide_context_pdf_candidates(
    content_id: str,
    *,
    metadata: ContentMetadata | None,
    path_resolver: PathResolverProtocol,
) -> list[str]:
    """Return deduplicated candidate PDF paths for slide-context extraction."""
    candidates: list[str] = []

    if metadata and metadata.source_file:
        candidates.append(metadata.source_file)

    candidates.extend(
        [
            path_resolver.build_content_path(content_id, "slide", "slide.pdf"),
            path_resolver.build_content_path(content_id, "source.pdf"),
            path_resolver.build_content_path(content_id, "source", "source.pdf"),
        ]
    )

    unique: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        if path not in seen:
            unique.append(path)
            seen.add(path)

    return unique


def extract_first_available_slide_text(
    content_id: str,
    *,
    metadata: ContentMetadata | None,
    path_resolver: PathResolverProtocol,
    pdf_text_extractor: PdfTextExtractorProtocol | None,
) -> str:
    """Extract text from the first readable candidate slide PDF."""
    if pdf_text_extractor is None:
        return ""

    for pdf_path in build_slide_context_pdf_candidates(
        content_id,
        metadata=metadata,
        path_resolver=path_resolver,
    ):
        try:
            text = pdf_text_extractor.extract_text(pdf_path)
        except Exception as exc:
            logger.warning("Failed to extract slide text from %s: %s", pdf_path, exc)
            continue

        if text.strip():
            return text

    return ""
