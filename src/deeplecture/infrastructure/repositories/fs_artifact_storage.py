"""Filesystem implementation of ArtifactStorageProtocol.

Stores a per-content artifacts.json index file at:
    content/{content_id}/artifacts.json

Thread-safe with per-content locking.

Security:
- All returned paths are validated against allowed roots (content_dir)
- Path traversal attacks are blocked via validate_segment + safe_join
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deeplecture.infrastructure.repositories.path_resolver import validate_segment

if TYPE_CHECKING:
    from deeplecture.infrastructure.repositories.path_resolver import PathResolver

logger = logging.getLogger(__name__)
UTC = timezone.utc


class FsArtifactStorage:
    """
    Filesystem-backed artifact registry using per-content JSON indexes.

    Design:
    - Each content has its own artifacts.json in content/{id}/
    - Thread-safe via per-content RLock (single-process only)
    - Atomic writes using temp file + rename
    - Corrupt index files are quarantined, not deleted
    - All paths validated against allowed roots before return
    """

    def __init__(self, path_resolver: PathResolver) -> None:
        self._resolver = path_resolver
        self._lock_map: dict[str, threading.RLock] = {}
        self._lock_guard = threading.Lock()
        # Base content directory for fallback validation
        self._content_root = Path(path_resolver.content_dir).resolve()

    def register(
        self,
        content_id: str,
        path: str,
        *,
        kind: str,
        media_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Register or update an artifact for a content item.

        Security: Only paths within the content's own directory are accepted.
        """
        validate_segment(content_id, "content_id")
        if not path:
            raise ValueError("Artifact path cannot be empty")
        if not kind:
            raise ValueError("Artifact kind cannot be empty")

        abs_path = os.path.abspath(path)

        # SECURITY: Reject paths outside this content's directory
        if not self._is_path_allowed_for_content(abs_path, content_id):
            raise ValueError(f"Path must be within content/{content_id}/ directory: {path}")

        lock = self._lock_for(content_id)

        with lock:
            self._ensure_content_dir(content_id)
            records = self._load_records(content_id)
            now = self._utc_now_iso()

            # Find existing record by kind (not path) for idempotent updates
            record = next((r for r in records if r.get("kind") == kind), None)

            if record is None:
                records.append(
                    {
                        "artifact_id": str(uuid.uuid4()),
                        "content_id": content_id,
                        "path": abs_path,
                        "kind": kind,
                        "media_type": media_type,
                        "metadata": dict(metadata or {}),
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            else:
                record["path"] = abs_path
                if media_type is not None:
                    record["media_type"] = media_type
                existing_meta = record.get("metadata")
                if not isinstance(existing_meta, dict):
                    existing_meta = {}
                    record["metadata"] = existing_meta
                existing_meta.update(metadata or {})
                record["updated_at"] = now

            self._save_records(content_id, records)

    def list(self, content_id: str) -> list[dict[str, Any]]:
        """List all artifacts for a content item."""
        validate_segment(content_id, "content_id")
        lock = self._lock_for(content_id)
        with lock:
            return [dict(r) for r in self._load_records(content_id)]

    def remove(self, content_id: str, path: str) -> None:
        """Remove a specific artifact from the registry by path."""
        validate_segment(content_id, "content_id")
        if not path:
            return

        abs_path = os.path.abspath(path)
        lock = self._lock_for(content_id)

        with lock:
            records = self._load_records(content_id)
            filtered = [r for r in records if r.get("path") != abs_path]
            if len(filtered) == len(records):
                return
            self._save_records(content_id, filtered)

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
            delete_files: If True, also delete the actual artifact files.
                         If False (default), only removes the index.

        Returns:
            List of deleted artifact records (for logging/auditing)

        Note:
            When delete_files=True, each file path is validated against
            allowed roots before deletion for security.
        """
        validate_segment(content_id, "content_id")
        lock = self._lock_for(content_id)

        with lock:
            records = [dict(r) for r in self._load_records(content_id)]

            # Optionally delete actual files
            if delete_files:
                for record in records:
                    path = record.get("path")
                    if not isinstance(path, str) or not path:
                        continue
                    # SECURITY: Validate path is within THIS content's directory
                    if not self._is_path_allowed_for_content(path, content_id):
                        logger.warning(
                            "Skipped deletion of file outside content/%s: %s",
                            content_id,
                            path,
                        )
                        continue
                    try:
                        file_path = Path(path).resolve()
                        # Re-validate after resolve to prevent symlink attacks
                        if not self._is_path_allowed_for_content(str(file_path), content_id):
                            logger.warning(
                                "Skipped deletion after resolve (symlink?): %s",
                                path,
                            )
                            continue
                        if file_path.exists() and file_path.is_file():
                            file_path.unlink()
                            logger.debug("Deleted artifact file: %s", path)
                    except OSError as e:
                        logger.warning("Failed to delete artifact file %s: %s", path, e)

            # Delete the index file
            record_path = self._record_path(content_id)
            if record_path.exists():
                with contextlib.suppress(OSError):
                    record_path.unlink()

            return records

    def get_by_kind(self, content_id: str, kind: str) -> dict[str, Any] | None:
        """Get artifact record by kind."""
        validate_segment(content_id, "content_id")
        lock = self._lock_for(content_id)

        with lock:
            for record in self._load_records(content_id):
                if record.get("kind") == kind:
                    return dict(record)
        return None

    def get_path(
        self,
        content_id: str,
        kind: str,
        *,
        fallback_kinds: list[str] | None = None,
    ) -> str | None:
        """
        Get absolute path for artifact by kind, with optional fallback kinds.

        Security: All returned paths are validated to be within this content's
        own directory. Paths outside content/{content_id}/ are rejected.

        Example:
            # Get video path, falling back to source if no generated video
            path = storage.get_path(id, "video", fallback_kinds=["source"])
        """
        kinds_to_try = [kind] + (fallback_kinds or [])

        for try_kind in kinds_to_try:
            record = self.get_by_kind(content_id, try_kind)
            if record is None:
                continue

            path = record.get("path")
            if not isinstance(path, str) or not path:
                continue

            # SECURITY: Validate path is within THIS content's directory
            if not self._is_path_allowed_for_content(path, content_id):
                logger.warning(
                    "Blocked access to path outside content/%s: %s (kind=%s)",
                    content_id,
                    path,
                    try_kind,
                )
                continue

            return path

        return None

    def _is_path_allowed_for_content(self, path: str, content_id: str) -> bool:
        """
        Check if path is within this specific content's directory.

        This is more restrictive than checking against the global content_dir:
        each content can only access files in its own content/{content_id}/ folder.
        """
        try:
            resolved = Path(path).resolve()
            content_root = Path(self._resolver.get_content_dir(content_id)).resolve()
            resolved.relative_to(content_root)
            return True
        except ValueError:
            return False

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _ensure_content_dir(self, content_id: str) -> None:
        Path(self._resolver.get_content_dir(content_id)).mkdir(parents=True, exist_ok=True)

    def _record_path(self, content_id: str) -> Path:
        return Path(self._resolver.get_content_dir(content_id)) / "artifacts.json"

    def _load_records(self, content_id: str) -> list[dict[str, Any]]:
        path = self._record_path(content_id)
        if not path.exists():
            return []

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Corrupt artifact index for %s (JSON decode error), quarantining", content_id)
            self._quarantine_index(path)
            return []
        except OSError as e:
            logger.error("Failed to read artifact index for %s: %s", content_id, e)
            return []

        # SECURITY: Validate payload structure to prevent DoS from malformed data
        if not isinstance(payload, dict):
            logger.warning("Corrupt artifact index for %s (not a dict), quarantining", content_id)
            self._quarantine_index(path)
            return []

        artifacts = payload.get("artifacts", [])
        if not isinstance(artifacts, list):
            logger.warning("Corrupt artifact index for %s (artifacts not a list), quarantining", content_id)
            self._quarantine_index(path)
            return []

        return [item for item in artifacts if isinstance(item, dict)]

    def _save_records(self, content_id: str, records: list[dict[str, Any]]) -> None:
        path = self._record_path(content_id)
        folder = path.parent
        folder.mkdir(parents=True, exist_ok=True)

        payload = {
            "content_id": content_id,
            "artifacts": records,
            "updated_at": self._utc_now_iso(),
        }

        # Atomic write: temp file → fsync → rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(folder),
            prefix=path.name + ".",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, str(path))
        finally:
            if os.path.exists(tmp_path):
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)

    def _lock_for(self, content_id: str) -> threading.RLock:
        with self._lock_guard:
            lock = self._lock_map.get(content_id)
            if lock is None:
                lock = threading.RLock()
                self._lock_map[content_id] = lock
            return lock

    def _quarantine_index(self, path: Path) -> None:
        if not path.exists():
            return

        base = Path(f"{path}.corrupt")
        target = base
        counter = 1
        while target.exists():
            target = Path(f"{base}.{counter}")
            counter += 1

        with contextlib.suppress(OSError):
            os.replace(str(path), str(target))
            logger.info("Quarantined corrupt index %s → %s", path, target)

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(UTC).isoformat()
