"""Storage protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from deeplecture.dto.storage import ContentMetadata


class MetadataStorageProtocol(Protocol):
    """Protocol for content metadata storage."""

    def get(self, content_id: str) -> ContentMetadata | None:
        """Get metadata for content.

        Args:
            content_id: Content identifier.

        Returns:
            ContentMetadata if exists, None otherwise.
        """
        ...

    def save(self, metadata: ContentMetadata) -> None:
        """Save metadata.

        Args:
            metadata: ContentMetadata to save.
        """
        ...

    def exists(self, content_id: str) -> bool:
        """Check if content exists.

        Args:
            content_id: Content identifier.

        Returns:
            True if content exists.
        """
        ...

    def delete(self, content_id: str) -> bool:
        """Delete content metadata.

        Args:
            content_id: Content identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...


class ArtifactStorageProtocol(Protocol):
    """Protocol for artifact file storage."""

    def store(self, content_id: str, artifact_type: str, data: bytes) -> str:
        """Store artifact data.

        Args:
            content_id: Content identifier.
            artifact_type: Type of artifact.
            data: Binary data to store.

        Returns:
            Path to stored artifact.
        """
        ...

    def load(self, content_id: str, artifact_type: str) -> bytes | None:
        """Load artifact data.

        Args:
            content_id: Content identifier.
            artifact_type: Type of artifact.

        Returns:
            Binary data if exists, None otherwise.
        """
        ...

    def exists(self, content_id: str, artifact_type: str) -> bool:
        """Check if artifact exists.

        Args:
            content_id: Content identifier.
            artifact_type: Type of artifact.

        Returns:
            True if artifact exists.
        """
        ...
