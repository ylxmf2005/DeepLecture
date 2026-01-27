"""Path resolution protocol."""

from __future__ import annotations

from typing import Protocol


class PathResolverProtocol(Protocol):
    """
    Path resolution contract.

    Provides unified path management for content directories
    and various artifact types.
    """

    def get_content_dir(self, content_id: str) -> str:
        """
        Get path to content directory without creating it.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to content/{content_id}
        """
        ...

    def ensure_content_dir(self, content_id: str, namespace: str) -> str:
        """
        Ensure content directory exists and return path.

        Args:
            content_id: Content identifier
            namespace: Subdirectory name (e.g., "subtitle", "timeline")

        Returns:
            Absolute path to the directory
        """
        ...

    def ensure_content_root(self, content_id: str) -> str:
        """
        Ensure content root directory exists (content/{content_id}).

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to content/{content_id}
        """
        ...

    def build_content_path(
        self,
        content_id: str,
        namespace: str,
        filename: str | None = None,
    ) -> str:
        """
        Build a path under content/{content_id}/{namespace}/[filename].

        Args:
            content_id: Content identifier
            namespace: Subdirectory name
            filename: Optional filename to append

        Returns:
            Absolute path
        """
        ...

    def build_notes_path(self, content_id: str) -> str:
        """
        Build path to notes.md without creating directories.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to notes.md
        """
        ...

    def build_cheatsheet_path(self, content_id: str) -> str:
        """
        Build path to cheatsheet.md without creating directories.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to cheatsheet.md
        """
        ...

    def ensure_notes_path(self, content_id: str) -> str:
        """
        Ensure notes directory exists and return path to notes.md.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to notes.md
        """
        ...

    def ensure_ask_dir(self, content_id: str) -> str:
        """
        Ensure ask directory exists and return path.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to ask directory
        """
        ...

    def ensure_timeline_dir(self, content_id: str) -> str:
        """
        Ensure timeline directory exists and return path.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to timeline directory
        """
        ...

    def ensure_temp_dir(self, subdir: str) -> str:
        """
        Ensure temporary subdirectory exists and return path.

        Args:
            subdir: Subdirectory name under temp_dir

        Returns:
            Absolute path to temp/{subdir}
        """
        ...

    def cleanup_temp_dir(self, subdir: str) -> None:
        """
        Safely clean up a temporary subdirectory.

        Only removes directories under temp_dir to prevent path traversal.

        Args:
            subdir: Subdirectory name or path under temp_dir

        Raises:
            ValueError: If path escapes temp_dir
        """
        ...

    @property
    def content_dir(self) -> str:
        """Base content directory."""
        ...

    @property
    def temp_dir(self) -> str:
        """Temporary directory."""
        ...

    @property
    def upload_dir(self) -> str:
        """Upload directory."""
        ...
