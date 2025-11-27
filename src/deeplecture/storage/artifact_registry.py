from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import uuid
from typing import Dict, List, Optional

from deeplecture.app_context import AppContext, get_app_context
from deeplecture.dto.storage import ArtifactRecord, _utc_now

logger = logging.getLogger(__name__)


class ArtifactRegistry:
    """
    Persisted index of on-disk artifacts per content item.

    New structure: data/content/{content_id}/artifacts.json
    """

    def __init__(
        self,
        *,
        app_context: Optional[AppContext] = None,
        registry_folder: Optional[str] = None,
    ) -> None:
        if registry_folder:
            self._content_dir = registry_folder
            os.makedirs(self._content_dir, exist_ok=True)
        else:
            ctx = app_context or get_app_context()
            ctx.init_paths()
            self._content_dir = ctx.content_dir
        self._lock_map: Dict[str, threading.RLock] = {}
        self._lock_guard = threading.Lock()

    def list(self, content_id: str) -> List[ArtifactRecord]:
        lock = self._lock_for(content_id)
        with lock:
            return list(self._load_records(content_id))

    def register(
        self,
        content_id: str,
        path: str,
        *,
        kind: str,
        media_type: Optional[str] = None,
        is_directory: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ArtifactRecord:
        if not path:
            raise ValueError("Artifact path cannot be empty")

        lock = self._lock_for(content_id)
        with lock:
            abs_path = os.path.abspath(path)
            os.makedirs(self._content_path(content_id), exist_ok=True)

            records = self._load_records(content_id)
            match = next((r for r in records if r.path == abs_path), None)
            now = _utc_now()

            if match:
                match.kind = kind
                match.media_type = media_type or match.media_type
                match.metadata.update(metadata or {})
                if is_directory is not None:
                    match.is_directory = bool(is_directory)
                elif os.path.exists(abs_path):
                    match.is_directory = os.path.isdir(abs_path)
                match.updated_at = now
                self._save_records(content_id, records)
                return match

            record = ArtifactRecord(
                artifact_id=str(uuid.uuid4()),
                content_id=content_id,
                path=abs_path,
                kind=kind,
                media_type=media_type,
                is_directory=bool(is_directory) if is_directory is not None else os.path.isdir(abs_path),
                metadata=dict(metadata or {}),
                created_at=now,
                updated_at=now,
            )
            records.append(record)
            self._save_records(content_id, records)
            return record

    def remove_content(self, content_id: str) -> List[ArtifactRecord]:
        lock = self._lock_for(content_id)
        with lock:
            records = self._load_records(content_id)
            record_path = self._record_path(content_id)
            if os.path.exists(record_path):
                try:
                    os.remove(record_path)
                except Exception as exc:
                    logger.error("Failed to remove artifact index for %s: %s", content_id, exc)
            return records

    def remove(self, content_id: str, path: str) -> None:
        if not path:
            return
        lock = self._lock_for(content_id)
        with lock:
            abs_path = os.path.abspath(path)
            records = self._load_records(content_id)
            filtered = [r for r in records if r.path != abs_path]
            if len(filtered) == len(records):
                return
            self._save_records(content_id, filtered)

    def _content_path(self, content_id: str) -> str:
        return os.path.join(self._content_dir, content_id)

    def _record_path(self, content_id: str) -> str:
        return os.path.join(self._content_path(content_id), "artifacts.json")

    def _load_records(self, content_id: str) -> List[ArtifactRecord]:
        path = self._record_path(content_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            logger.error("Failed to read artifact index %s: %s", path, exc)
            self._quarantine_index(path)
            return []
        except Exception as exc:
            logger.error("Failed to read artifact index %s: %s", path, exc)
            return []

        records: List[ArtifactRecord] = []
        for item in payload.get("artifacts", []):
            try:
                records.append(ArtifactRecord.from_dict(item))
            except Exception as exc:
                logger.warning("Skipping malformed artifact entry for %s: %s", content_id, exc)
        return records

    def _save_records(self, content_id: str, records: List[ArtifactRecord]) -> None:
        path = self._record_path(content_id)
        payload = {
            "content_id": content_id,
            "artifacts": [r.to_dict() for r in records],
            "updated_at": _utc_now(),
        }
        folder = os.path.dirname(path)
        os.makedirs(folder, exist_ok=True)
        prefix = os.path.basename(path) + "."
        fd, tmp_path = tempfile.mkstemp(dir=folder, prefix=prefix, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _lock_for(self, content_id: str) -> threading.RLock:
        key = str(content_id)
        with self._lock_guard:
            lock = self._lock_map.get(key)
            if lock is None:
                lock = threading.RLock()
                self._lock_map[key] = lock
        return lock

    def _quarantine_index(self, path: str) -> None:
        if not os.path.exists(path):
            return
        base = f"{path}.corrupt"
        target = base
        counter = 1
        while os.path.exists(target):
            target = f"{base}.{counter}"
            counter += 1
        try:
            os.replace(path, target)
            logger.warning("Quarantined corrupt artifact index %s -> %s", path, target)
        except Exception as exc:
            logger.warning("Failed to quarantine corrupt artifact index %s: %s", path, exc)


_default_registry: Optional[ArtifactRegistry] = None


def get_default_artifact_registry() -> ArtifactRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ArtifactRegistry()
    return _default_registry
