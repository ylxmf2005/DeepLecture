"""Filesystem implementation of ContentConfigStorageProtocol.

Stores a single JSON file per content item at:
    content/{content_id}/config/config.json
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from deeplecture.domain.entities.config import ContentConfig
from deeplecture.infrastructure.repositories.path_resolver import validate_segment

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import PathResolverProtocol

logger = logging.getLogger(__name__)


class FsContentConfigStorage:
    """Filesystem-backed per-video configuration storage."""

    NAMESPACE = "config"
    FILENAME = "config.json"

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver

    def _get_path(self, content_id: str) -> Path:
        """Get path to config file."""
        validate_segment(content_id, "content_id")
        return Path(self._paths.build_content_path(content_id, self.NAMESPACE, self.FILENAME))

    def load(self, content_id: str) -> ContentConfig | None:
        """Load per-video config from filesystem.

        Args:
            content_id: Content identifier.

        Returns:
            ContentConfig if exists, None otherwise.
        """
        path = self._get_path(content_id)

        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read content config %s: %s", path, exc)
            return None

        return ContentConfig.from_dict(data)

    def save(self, content_id: str, config: ContentConfig) -> None:
        """Save per-video config to filesystem.

        Uses atomic write (tempfile + os.replace) for safety.

        Args:
            content_id: Content identifier.
            config: Configuration to save.
        """
        path = self._get_path(content_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = config.to_sparse_dict()

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(path.parent),
                delete=False,
            ) as f:
                tmp_path = f.name
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        finally:
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)

    def delete(self, content_id: str) -> None:
        """Delete per-video config file.

        Args:
            content_id: Content identifier.
        """
        path = self._get_path(content_id)
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
