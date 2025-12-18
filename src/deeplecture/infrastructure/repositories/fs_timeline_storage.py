"""Filesystem implementation of TimelineStorageProtocol.

Stores timeline JSON payloads at:
    content/{content_id}/timeline/timeline_{language}.json

Notes:
- Uses PathResolverProtocol for path construction and directory creation.
- Uses atomic writes (temp file + os.replace) to avoid partial writes.
- Corrupt JSON is quarantined (renamed) instead of silently overwritten.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deeplecture.infrastructure.repositories.path_resolver import safe_join, validate_segment

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import PathResolverProtocol

logger = logging.getLogger(__name__)
UTC = timezone.utc


class FsTimelineStorage:
    """Filesystem-backed timeline storage."""

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver
        self._lock_map: dict[str, threading.RLock] = {}
        self._lock_guard = threading.Lock()

    def load(self, content_id: str, language: str) -> dict[str, Any] | None:
        validate_segment(content_id, "content_id")
        validate_segment(language, "language")

        lock = self._lock_for(content_id)
        with lock:
            path = self._timeline_path(content_id, language)
            if not path.exists():
                return None

            try:
                raw = path.read_text(encoding="utf-8")
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                logger.warning("Corrupt timeline JSON, quarantining: %s (%s)", path, exc)
                self._quarantine_corrupt_file(path)
                return None
            except OSError as exc:
                logger.warning("Failed to read timeline file %s: %s", path, exc)
                return None

            if not isinstance(data, dict):
                logger.warning("Invalid timeline payload type in %s: %s", path, type(data))
                return None

            return data

    def save(
        self,
        payload: dict[str, Any],
        content_id: str,
        language: str,
        learner_profile: str | None = None,
    ) -> None:
        validate_segment(content_id, "content_id")
        validate_segment(language, "language")

        lock = self._lock_for(content_id)
        with lock:
            timeline_dir = Path(self._paths.ensure_timeline_dir(content_id))
            timeline_dir.mkdir(parents=True, exist_ok=True)
            path = self._timeline_path(content_id, language)

            # Keep payload self-contained for later cache checks.
            if learner_profile is not None:
                payload = dict(payload)
                payload["learner_profile"] = learner_profile

            serialized = json.dumps(payload, ensure_ascii=False, indent=2)
            self._atomic_write_text(path, serialized)

    def exists(self, content_id: str, language: str) -> bool:
        validate_segment(content_id, "content_id")
        validate_segment(language, "language")
        return self._timeline_path(content_id, language).exists()

    def _timeline_path(self, content_id: str, language: str) -> Path:
        directory = Path(self._paths.ensure_timeline_dir(content_id))
        filename = f"timeline_{language}.json"
        return safe_join(directory, filename)

    def _lock_for(self, content_id: str) -> threading.RLock:
        with self._lock_guard:
            lock = self._lock_map.get(content_id)
            if lock is None:
                lock = threading.RLock()
                self._lock_map[content_id] = lock
            return lock

    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(path.parent),
                delete=False,
            ) as f:
                tmp_path = f.name
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        finally:
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)

    @staticmethod
    def _quarantine_corrupt_file(path: Path) -> None:
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        quarantine = path.with_suffix(path.suffix + f".corrupt.{ts}")
        with contextlib.suppress(OSError):
            os.replace(str(path), str(quarantine))
