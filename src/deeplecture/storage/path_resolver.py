from __future__ import annotations

import os
from typing import Optional, Protocol

from deeplecture.utils.fs import safe_join


class PathResolver(Protocol):
    """
    Minimal path helper contract so storage implementations don't depend on
    the full ContentService.
    """

    def ensure_content_dir(self, content_id: str, namespace: str) -> str:
        ...

    def build_content_path(self, content_id: str, namespace: str, filename: Optional[str] = None) -> str:
        ...

    def ensure_notes_path(self, content_id: str) -> str:
        ...

    def ensure_ask_dir(self, content_id: str) -> str:
        ...

    def ensure_timeline_dir(self, content_id: str) -> str:
        ...


class DefaultPathResolver:
    """
    Concrete implementation of PathResolver that handles file system paths
    independently of ContentService.

    This allows Storage classes to resolve paths without depending on the
    full ContentService, achieving proper dependency inversion.
    """

    def __init__(self, content_dir: Optional[str] = None) -> None:
        if content_dir is not None:
            self._content_dir = content_dir
        else:
            from deeplecture.app_context import get_app_context
            ctx = get_app_context()
            ctx.init_paths()
            self._content_dir = ctx.content_dir

    def _content_path(self, content_id: str, *subpaths: str) -> str:
        """Get path under {content_dir}/{content_id}/[subpaths]"""
        return safe_join(self._content_dir, str(content_id), *subpaths)

    def ensure_content_dir(self, content_id: str, namespace: str) -> str:
        """Ensure content directory exists and return path."""
        path = self._content_path(content_id, namespace)
        os.makedirs(path, exist_ok=True)
        return path

    def build_content_path(self, content_id: str, namespace: str, filename: Optional[str] = None) -> str:
        """Build a path under content/{content_id}/{namespace}/[filename]."""
        if filename:
            return self._content_path(content_id, namespace, filename)
        return self._content_path(content_id, namespace)

    def ensure_notes_path(self, content_id: str) -> str:
        """Ensure notes directory exists and return path to notes.md."""
        notes_dir = self.ensure_content_dir(content_id, "notes")
        return os.path.join(notes_dir, "notes.md")

    def ensure_ask_dir(self, content_id: str) -> str:
        """Ensure ask directory exists and return path."""
        return self.ensure_content_dir(content_id, "ask")

    def ensure_timeline_dir(self, content_id: str) -> str:
        """Ensure timeline directory exists and return path."""
        return self.ensure_content_dir(content_id, "timeline")


# Singleton instance for default usage
_default_path_resolver: Optional[DefaultPathResolver] = None


def get_default_path_resolver() -> DefaultPathResolver:
    """Get or create the default PathResolver singleton."""
    global _default_path_resolver
    if _default_path_resolver is None:
        _default_path_resolver = DefaultPathResolver()
    return _default_path_resolver


def resolve_path_resolver(path_resolver: Optional[PathResolver]) -> PathResolver:
    """
    Resolve a PathResolver instance.

    If path_resolver is provided, return it directly.
    Otherwise, return the default DefaultPathResolver singleton.

    This function is used by Storage classes to get a PathResolver
    without depending on ContentService.
    """
    if path_resolver is not None:
        return path_resolver
    return get_default_path_resolver()
