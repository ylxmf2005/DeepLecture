"""Filesystem-backed voiceover metadata storage.

Stores per-content voiceover metadata in:
    content/{content_id}/voiceovers/voiceovers.json

The JSON index allows "processing" voiceovers to be visible before the
corresponding audio file exists.

Backward compatibility:
- If voiceovers.json does not exist (or is unreadable), list_all() falls back
  to scanning *.m4a files under content/{content_id}/voiceovers/.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deeplecture.infrastructure.repositories.path_resolver import validate_segment

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import PathResolverProtocol

logger = logging.getLogger(__name__)
UTC = timezone.utc


class FsVoiceoverStorage:
    """Filesystem-backed voiceover manifest storage."""

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver
        self._lock_map: dict[str, threading.RLock] = {}
        self._lock_guard = threading.Lock()

    def list_all(self, content_id: str) -> list[dict[str, Any]]:
        """List all voiceover entries (JSON ∪ file scan merged view).

        Always merges JSON entries with file scan results:
        - JSON entries take precedence (same id)
        - File scan fills in any .m4a files not in JSON
        """
        validate_segment(content_id, "content_id")
        lock = self._lock_for(content_id)

        with lock:
            voiceovers_dir = Path(self._paths.get_content_dir(content_id)) / "voiceovers"

            # Load JSON entries (may be empty dict/list)
            meta = self._load_meta(content_id)
            json_entries: list[dict[str, Any]] = []
            if meta is not None:
                raw = meta.get("voiceovers")
                if isinstance(raw, list):
                    json_entries = [dict(item) for item in raw if isinstance(item, dict)]

            # Scan filesystem for .m4a files
            scanned = self._scan_voiceovers(voiceovers_dir)

            # Merge: JSON takes precedence, scan fills gaps
            json_ids = {e.get("id") for e in json_entries}
            for scanned_entry in scanned:
                if scanned_entry.get("id") not in json_ids:
                    json_entries.append(scanned_entry)

            return json_entries

    def add_entry(self, content_id: str, entry: dict[str, Any]) -> None:
        """Add (or update) a voiceover entry in voiceovers.json.

        Preserves created_at from existing entry if updating.
        """
        validate_segment(content_id, "content_id")

        voiceover_id = entry.get("id")
        if not isinstance(voiceover_id, str) or not voiceover_id.strip():
            raise ValueError("Voiceover entry must include a non-empty 'id'")
        voiceover_id = voiceover_id.strip()
        validate_segment(voiceover_id, "voiceover_id")

        lock = self._lock_for(content_id)
        with lock:
            self._ensure_voiceovers_dir(content_id)
            meta = self._load_meta(content_id) or {"content_id": content_id, "voiceovers": []}

            voiceovers = meta.get("voiceovers")
            if not isinstance(voiceovers, list):
                voiceovers = []

            # Find existing entry to preserve created_at
            existing_created_at: str | None = None
            kept = []
            for item in voiceovers:
                if not isinstance(item, dict):
                    continue
                if item.get("id") == voiceover_id:
                    existing_created_at = item.get("created_at")
                else:
                    kept.append(item)

            normalized = dict(entry)
            normalized.setdefault("status", "processing")
            # Preserve original created_at if updating, else use current time
            if existing_created_at:
                normalized["created_at"] = existing_created_at
                normalized["updated_at"] = datetime.now(UTC).isoformat()
            else:
                normalized.setdefault("created_at", datetime.now(UTC).isoformat())
            kept.append(normalized)

            meta["content_id"] = content_id
            meta["voiceovers"] = kept
            self._save_meta(content_id, meta)

    def update_status(self, content_id: str, voiceover_id: str, status: str) -> bool:
        """Update status for an existing entry. Returns True if updated."""
        validate_segment(content_id, "content_id")

        if not isinstance(voiceover_id, str) or not voiceover_id.strip():
            raise ValueError("voiceover_id is required")
        voiceover_id = voiceover_id.strip()
        validate_segment(voiceover_id, "voiceover_id")

        if not isinstance(status, str) or not status.strip():
            raise ValueError("status is required")
        status = status.strip()

        lock = self._lock_for(content_id)
        with lock:
            meta = self._load_meta(content_id)
            if meta is None:
                return False

            voiceovers = meta.get("voiceovers")
            if not isinstance(voiceovers, list):
                return False

            updated = False
            now = datetime.now(UTC).isoformat()

            for item in voiceovers:
                if not isinstance(item, dict):
                    continue
                if item.get("id") != voiceover_id:
                    continue
                item["status"] = status
                item["updated_at"] = now
                updated = True
                break

            if updated:
                meta["voiceovers"] = voiceovers
                self._save_meta(content_id, meta)

            return updated

    def remove_entry(self, content_id: str, voiceover_id: str) -> bool:
        """Remove an entry from voiceovers.json. Returns True if removed."""
        validate_segment(content_id, "content_id")

        if not isinstance(voiceover_id, str) or not voiceover_id.strip():
            raise ValueError("voiceover_id is required")
        voiceover_id = voiceover_id.strip()
        validate_segment(voiceover_id, "voiceover_id")

        lock = self._lock_for(content_id)
        with lock:
            meta = self._load_meta(content_id)
            if meta is None:
                return False

            voiceovers = meta.get("voiceovers")
            if not isinstance(voiceovers, list):
                return False

            kept: list[dict[str, Any]] = []
            removed = False
            for item in voiceovers:
                if not isinstance(item, dict):
                    continue
                if item.get("id") == voiceover_id:
                    removed = True
                    continue
                kept.append(item)

            if not removed:
                return False

            meta["voiceovers"] = kept
            self._save_meta(content_id, meta)
            return True

    def _ensure_voiceovers_dir(self, content_id: str) -> Path:
        path = Path(self._paths.get_content_dir(content_id)) / "voiceovers"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _meta_path(self, content_id: str) -> Path:
        voiceovers_dir = Path(self._paths.get_content_dir(content_id)) / "voiceovers"
        return voiceovers_dir / "voiceovers.json"

    def _load_meta(self, content_id: str) -> dict[str, Any] | None:
        path = self._meta_path(content_id)
        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid voiceovers.json for %s: %s", content_id, exc)
            self._quarantine_corrupt(path)
            return None
        except OSError as exc:
            logger.warning("Failed to read voiceovers.json for %s: %s", content_id, exc)
            return None

        if not isinstance(data, dict):
            return None
        return data

    def _quarantine_corrupt(self, path: Path) -> None:
        ts = int(time.time())
        corrupt = path.with_name(f"{path.name}.corrupt.{ts}")
        with contextlib.suppress(OSError):
            os.replace(str(path), str(corrupt))

    def _save_meta(self, content_id: str, meta: dict[str, Any]) -> None:
        path = self._meta_path(content_id)
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
                json.dump(meta, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        finally:
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)

    def _scan_voiceovers(self, voiceovers_dir: Path) -> list[dict[str, Any]]:
        """Fallback: scan *.m4a files when voiceovers.json does not exist."""
        if not voiceovers_dir.is_dir():
            return []

        result: list[dict[str, Any]] = []
        for audio_file in sorted(voiceovers_dir.glob("*.m4a")):
            name = audio_file.stem
            timeline_file = voiceovers_dir / f"{name}_sync_timeline.json"

            try:
                created_at = datetime.fromtimestamp(audio_file.stat().st_mtime, tz=UTC).isoformat()
            except OSError:
                created_at = datetime.now(UTC).isoformat()

            language = "unknown"
            if "_" in name:
                language = name.rsplit("_", 1)[-1]

            result.append(
                {
                    "id": name,
                    "name": name,
                    "language": language,
                    "subtitle_source": "path",
                    "created_at": created_at,
                    "status": "done" if timeline_file.exists() else "processing",
                }
            )

        return result

    def _lock_for(self, content_id: str) -> threading.RLock:
        with self._lock_guard:
            lock = self._lock_map.get(content_id)
            if lock is None:
                lock = threading.RLock()
                self._lock_map[content_id] = lock
            return lock
