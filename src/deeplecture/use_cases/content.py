"""Content management use case - core business logic for content CRUD operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from deeplecture.domain.errors import ContentNotFoundError

if TYPE_CHECKING:
    from deeplecture.domain import ContentMetadata
    from deeplecture.use_cases.interfaces import (
        ArtifactStorageProtocol,
        MetadataStorageProtocol,
    )

UTC = getattr(datetime, "UTC", timezone.utc)
logger = logging.getLogger(__name__)


class ContentUseCase:
    """
    Content management use case - handles core CRUD operations.

    Orchestrates:
    - Content creation and metadata management
    - Content retrieval (single and batch)
    - Content deletion with artifact cleanup
    - Content existence checks
    - Content renaming

    Design:
    - Protocol-based dependencies (follows DIP)
    - No legacy serialization (moved to Controller layer)
    - No view construction (moved to Controller layer)
    - No path management (managed by Repository layer)
    - Focus on pure business logic
    """

    def __init__(
        self,
        *,
        metadata_storage: MetadataStorageProtocol,
        artifact_storage: ArtifactStorageProtocol,
    ) -> None:
        """
        Initialize ContentUseCase with injected dependencies.

        Args:
            metadata_storage: Storage for content metadata
            artifact_storage: Storage for artifact tracking
        """
        self._metadata = metadata_storage
        self._artifacts = artifact_storage

    # =========================================================================
    # PUBLIC API - Content CRUD Operations
    # =========================================================================

    def list_content(self) -> list[ContentMetadata]:
        """
        List all content items.

        Returns:
            List of content metadata objects
        """
        return self._metadata.list_all()

    def get_content(self, content_id: str) -> ContentMetadata:
        """
        Get content by ID.

        Args:
            content_id: Content identifier

        Returns:
            Content metadata

        Raises:
            ContentNotFoundError: If content doesn't exist
        """
        metadata = self._metadata.get(content_id)
        if metadata is None:
            raise ContentNotFoundError(content_id)
        return metadata

    def rename_content(self, content_id: str, new_name: str) -> ContentMetadata:
        """
        Rename content.

        Args:
            content_id: Content identifier
            new_name: New filename

        Returns:
            Updated content metadata

        Raises:
            ContentNotFoundError: If content doesn't exist
        """
        metadata = self.get_content(content_id)

        # Update metadata
        metadata.original_filename = new_name
        metadata.updated_at = datetime.now(UTC)

        # Persist
        self._metadata.save(metadata)

        logger.info("Renamed content %s to '%s'", content_id, new_name)
        return metadata

    def delete_content(self, content_id: str) -> bool:
        """
        Delete content and all associated artifacts.

        This is a clean architecture implementation that:
        1. Deletes metadata record (primary operation)
        2. Cleans up artifact registry and files (best-effort)
        3. Returns success based on metadata deletion only

        Args:
            content_id: Content identifier

        Returns:
            True if metadata deletion succeeded, False if content not found

        Note:
            Artifact cleanup failures are logged but do not affect the return value.
            This prevents "lying API" semantics where partial success returns False.
        """
        # Check existence
        if not self._metadata.exists(content_id):
            logger.warning("Delete failed: content %s not found", content_id)
            return False

        # PRIMARY OPERATION: Delete metadata
        deleted = self._metadata.delete(content_id)

        if not deleted:
            logger.error("Failed to delete metadata for content %s", content_id)
            return False

        # BEST-EFFORT: Clean up artifact registry and files
        # Failures here are logged but don't change the result
        try:
            self._artifacts.remove_content(content_id, delete_files=True)
        except Exception:
            logger.exception(
                "Artifact cleanup failed for content %s (metadata already deleted)",
                content_id,
            )

        logger.info("Deleted content %s successfully", content_id)
        return True

    # =========================================================================
    # FEATURE STATUS UPDATES
    # =========================================================================

    def update_feature_status(
        self,
        content_id: str,
        feature: str,
        status: str,
        *,
        job_id: str | None = None,
    ) -> ContentMetadata:
        """
        Update feature status for content.

        Args:
            content_id: Content identifier
            feature: Feature name (video, subtitle, translation, etc.)
            status: New status value
            job_id: Optional job ID for tracking

        Returns:
            Updated content metadata

        Raises:
            ContentNotFoundError: If content doesn't exist
        """
        metadata = self.get_content(content_id)

        # Update status
        setattr(metadata, f"{feature}_status", status)
        if job_id is not None:
            setattr(metadata, f"{feature}_job_id", job_id)
        metadata.updated_at = datetime.now(UTC)

        # Persist
        self._metadata.save(metadata)

        logger.debug(
            "Updated %s status for %s: %s (job_id=%s)",
            feature,
            content_id,
            status,
            job_id,
        )
        return metadata
