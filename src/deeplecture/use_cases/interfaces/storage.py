"""Storage protocols - contracts for data persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from deeplecture.domain.entities import ContentMetadata


@runtime_checkable
class MetadataStorageProtocol(Protocol):
    """
    Contract for content metadata persistence.

    Implementations: SQLiteMetadataStorage, InMemoryMetadataStorage (for tests)
    """

    def get(self, content_id: str) -> ContentMetadata | None:
        """Get metadata by content ID."""
        ...

    def save(self, metadata: ContentMetadata) -> None:
        """Save or update metadata."""
        ...

    def delete(self, content_id: str) -> bool:
        """Delete metadata by content ID."""
        ...

    def exists(self, content_id: str) -> bool:
        """Check if metadata exists."""
        ...

    def list_all(
        self,
        include_deleted: bool = False,
        *,
        project_id: str | None = None,
    ) -> list[ContentMetadata]:
        """List content metadata, optionally filtered by project."""
        ...


@runtime_checkable
class ArtifactStorageProtocol(Protocol):
    """
    Contract for artifact (file) management.

    Manages a per-content artifacts.json index file.
    """

    def register(
        self,
        content_id: str,
        path: str,
        *,
        kind: str,
        media_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register or update an artifact for a content item."""
        ...

    def list(self, content_id: str) -> list[dict[str, Any]]:
        """List all artifacts for a content item."""
        ...

    def remove(self, content_id: str, path: str) -> None:
        """Remove a specific artifact from the registry."""
        ...

    def remove_content(
        self,
        content_id: str,
        *,
        delete_files: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Remove all artifacts for a content item.

        Args:
            content_id: Content identifier
            delete_files: If True, also delete the actual artifact files

        Returns:
            List of deleted artifact records
        """
        ...

    def get_path(
        self,
        content_id: str,
        kind: str,
        *,
        fallback_kinds: list[str] | None = None,
    ) -> str | None:
        """
        Get absolute path for artifact by kind.

        Args:
            content_id: Content identifier
            kind: Artifact kind to look up
            fallback_kinds: Optional list of kinds to try if primary kind not found

        Returns:
            Absolute path if found, None otherwise
        """
        ...

    def get_by_kind(self, content_id: str, kind: str) -> dict[str, Any] | None:
        """
        Get artifact record by kind.

        Args:
            content_id: Content identifier
            kind: Artifact kind to look up

        Returns:
            Artifact record dict if found, None otherwise
        """
        ...
