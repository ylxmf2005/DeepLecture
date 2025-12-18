"""Repository-layer path resolver (filesystem).

Centralizes all path building for content-related files/directories and
protects against path traversal via safe_join().
"""

from __future__ import annotations

import shutil
from pathlib import Path


def validate_segment(segment: str, name: str = "segment") -> None:
    """Validate that a path segment is a single safe name.

    Rejects empty strings, path separators, and special names like "." or "..".
    This is a defense-in-depth check before safe_join().

    Args:
        segment: Path segment to validate.
        name: Parameter name for error messages.

    Raises:
        ValueError: If segment is invalid.
    """
    if not segment or "/" in segment or "\\" in segment or segment in (".", ".."):
        raise ValueError(f"Invalid {name}: {segment!r}")


def safe_join(base: Path, *paths: str) -> Path:
    """Join paths and ensure the result stays under the base directory.

    Protects against path traversal attacks by verifying that the resolved
    path is within the base directory.

    Args:
        base: Base directory path (all results must be under this).
        *paths: Path components to join to base.

    Returns:
        Absolute resolved Path (guaranteed to be under base).

    Raises:
        ValueError: If the resolved path escapes the base directory.
    """
    base_path = Path(base).expanduser().resolve(strict=False)
    target = base_path.joinpath(*paths).resolve(strict=False)

    try:
        target.relative_to(base_path)
    except ValueError:
        raise ValueError("Path traversal detected") from None

    return target


class PathResolver:
    """
    Concrete PathResolver implementation for filesystem paths.

    Keeps all "where things live on disk" rules in one place so UseCases
    don't build paths directly.
    """

    def __init__(
        self,
        content_dir: Path,
        temp_dir: Path,
        upload_dir: Path,
    ) -> None:
        self._content_dir = Path(content_dir).expanduser().resolve(strict=False)
        self._temp_dir = Path(temp_dir).expanduser().resolve(strict=False)
        self._upload_dir = Path(upload_dir).expanduser().resolve(strict=False)

    def _content_path(self, content_id: str, *subpaths: str) -> Path:
        """Get path under {content_dir}/{content_id}/[subpaths]."""
        validate_segment(content_id, "content_id")
        for i, sp in enumerate(subpaths):
            validate_segment(sp, f"subpath[{i}]")
        return safe_join(self._content_dir, str(content_id), *subpaths)

    def get_content_dir(self, content_id: str) -> str:
        """
        Get path to content directory without creating it.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to content/{content_id}
        """
        return str(self._content_path(content_id))

    def ensure_content_dir(self, content_id: str, namespace: str) -> str:
        """
        Ensure content directory exists and return path.

        Args:
            content_id: Content identifier
            namespace: Subdirectory name (e.g., "subtitle", "timeline")

        Returns:
            Absolute path to the directory
        """
        path = self._content_path(content_id, namespace)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

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
        if filename is None:
            return str(self._content_path(content_id, namespace))
        return str(self._content_path(content_id, namespace, filename))

    def ensure_notes_path(self, content_id: str) -> str:
        """
        Ensure notes directory exists and return path to notes.md.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to notes.md
        """
        notes_dir = self._content_path(content_id, "notes")
        notes_dir.mkdir(parents=True, exist_ok=True)
        return str(notes_dir / "notes.md")

    def ensure_ask_dir(self, content_id: str) -> str:
        """
        Ensure ask directory exists and return path.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to ask directory
        """
        return self.ensure_content_dir(content_id, "ask")

    def ensure_timeline_dir(self, content_id: str) -> str:
        """
        Ensure timeline directory exists and return path.

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to timeline directory
        """
        return self.ensure_content_dir(content_id, "timeline")

    def ensure_content_root(self, content_id: str) -> str:
        """
        Ensure content root directory exists (content/{content_id}).

        Args:
            content_id: Content identifier

        Returns:
            Absolute path to content/{content_id}
        """
        path = self._content_path(content_id)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def ensure_temp_dir(self, subdir: str) -> str:
        """
        Ensure temporary subdirectory exists and return path.

        Args:
            subdir: Subdirectory name under temp_dir

        Returns:
            Absolute path to temp/{subdir}
        """
        # Validate subdir to prevent traversal
        # Allow compound paths like "merge_uuid" but not ".." or absolute paths
        if ".." in subdir or subdir.startswith(("/", "\\")):
            raise ValueError(f"Invalid temp subdir: {subdir!r}")

        path = safe_join(self._temp_dir, subdir)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def cleanup_temp_dir(self, subdir: str) -> None:
        """
        Safely clean up a temporary subdirectory.

        Only removes directories under temp_dir to prevent path traversal.

        Args:
            subdir: Subdirectory name or path under temp_dir

        Raises:
            ValueError: If path escapes temp_dir
        """
        # Validate that path is under temp_dir
        path = Path(subdir).expanduser().resolve()
        try:
            path.relative_to(self._temp_dir)
        except ValueError:
            raise ValueError(f"Path escapes temp_dir: {subdir!r}") from None

        if path.exists():
            shutil.rmtree(str(path))

    @property
    def content_dir(self) -> str:
        """Base content directory."""
        return str(self._content_dir)

    @property
    def temp_dir(self) -> str:
        """Temporary directory."""
        return str(self._temp_dir)

    @property
    def upload_dir(self) -> str:
        """Upload directory."""
        return str(self._upload_dir)
