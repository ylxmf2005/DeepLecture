"""Filesystem-backed global configuration storage."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path

from deeplecture.domain.entities.config import ContentConfig

logger = logging.getLogger(__name__)


class FsGlobalConfigStorage:
    """Stores a single service-level config at data/config/global/config.json."""

    REL_PATH = ("config", "global", "config.json")

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir).expanduser().resolve(strict=False)

    def _path(self) -> Path:
        return self._data_dir.joinpath(*self.REL_PATH)

    def load(self) -> ContentConfig | None:
        path = self._path()
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read global config %s: %s", path, exc)
            return None
        return ContentConfig.from_dict(data)

    def save(self, config: ContentConfig) -> None:
        path = self._path()
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

    def delete(self) -> None:
        path = self._path()
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
