"""Filesystem implementation of AskStorageProtocol.

Stores conversation JSON files at:
    content/{content_id}/ask/{conversation_id}.json

Design goals:
- Simple, deterministic layout (one conversation per file).
- Atomic writes to prevent partial/corrupt saves.
- Corrupt JSON is quarantined, not silently ignored.
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
from deeplecture.use_cases.dto.ask import Conversation, ConversationSummary, Message

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import PathResolverProtocol

logger = logging.getLogger(__name__)
UTC = timezone.utc


class FsAskStorage:
    """Filesystem-backed conversation storage."""

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver
        self._lock_map: dict[str, threading.RLock] = {}
        self._lock_guard = threading.Lock()

    def list_conversations(self, content_id: str) -> list[ConversationSummary]:
        validate_segment(content_id, "content_id")

        lock = self._lock_for(content_id)
        with lock:
            ask_dir = Path(self._paths.ensure_ask_dir(content_id))
            if not ask_dir.exists():
                return []

            items: list[ConversationSummary] = []

            for path in sorted(ask_dir.glob("*.json")):
                conv_id = path.stem
                if not conv_id:
                    continue

                data = self._load_json_or_quarantine(path)
                if not data:
                    continue

                summary = self._build_summary(content_id, conv_id, data)
                if summary:
                    items.append(summary)

            # ISO8601 timestamps sort lexicographically in the intended order.
            items.sort(key=lambda s: s.updated_at, reverse=True)
            return items

    def get_conversation(self, content_id: str, conversation_id: str) -> Conversation | None:
        validate_segment(content_id, "content_id")
        validate_segment(conversation_id, "conversation_id")

        lock = self._lock_for(content_id)
        with lock:
            path = self._conversation_path(content_id, conversation_id)
            if not path.exists():
                return None

            data = self._load_json_or_quarantine(path)
            if not data:
                return None

            try:
                return self._parse_conversation(content_id, conversation_id, data)
            except Exception as exc:
                logger.warning("Failed to parse conversation %s: %s", path, exc)
                return None

    def save_conversation(self, conversation: Conversation) -> None:
        validate_segment(conversation.content_id, "content_id")
        validate_segment(conversation.id, "conversation_id")

        lock = self._lock_for(conversation.content_id)
        with lock:
            ask_dir = Path(self._paths.ensure_ask_dir(conversation.content_id))
            ask_dir.mkdir(parents=True, exist_ok=True)

            path = self._conversation_path(conversation.content_id, conversation.id)

            payload = conversation.to_dict()
            # Redundant storage helps debugging and keeps file self-contained.
            payload["content_id"] = conversation.content_id
            payload["schema_version"] = 1

            self._atomic_write_json(path, payload)

    def delete_conversation(self, content_id: str, conversation_id: str) -> bool:
        validate_segment(content_id, "content_id")
        validate_segment(conversation_id, "conversation_id")

        lock = self._lock_for(content_id)
        with lock:
            path = self._conversation_path(content_id, conversation_id)
            if not path.exists():
                return False
            try:
                path.unlink()
                return True
            except OSError as exc:
                logger.warning("Failed to delete conversation %s: %s", path, exc)
                return False

    def _conversation_path(self, content_id: str, conversation_id: str) -> Path:
        directory = Path(self._paths.ensure_ask_dir(content_id))
        filename = f"{conversation_id}.json"
        return safe_join(directory, filename)

    def _lock_for(self, content_id: str) -> threading.RLock:
        with self._lock_guard:
            lock = self._lock_map.get(content_id)
            if lock is None:
                lock = threading.RLock()
                self._lock_map[content_id] = lock
            return lock

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
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
                f.write(serialized)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        finally:
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)

    @staticmethod
    def _load_json_or_quarantine(path: Path) -> dict[str, Any] | None:
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Corrupt JSON, quarantining: %s (%s)", path, exc)
            FsAskStorage._quarantine_corrupt_file(path)
            return None
        except OSError as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None

        if not isinstance(data, dict):
            logger.warning("Invalid JSON type in %s: %s", path, type(data))
            return None
        return data

    @staticmethod
    def _quarantine_corrupt_file(path: Path) -> None:
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        quarantine = path.with_suffix(path.suffix + f".corrupt.{ts}")
        with contextlib.suppress(OSError):
            os.replace(str(path), str(quarantine))

    @staticmethod
    def _parse_conversation(content_id: str, conversation_id: str, data: dict[str, Any]) -> Conversation:
        title = str(data.get("title", "") or "").strip() or "New chat"
        created_at = str(data.get("created_at", "") or "").strip()
        updated_at = str(data.get("updated_at", "") or "").strip()

        messages_raw = data.get("messages", [])
        messages: list[Message] = []
        if isinstance(messages_raw, list):
            for item in messages_raw:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role", "") or "").strip()
                content = str(item.get("content", "") or "")
                msg_created_at = str(item.get("created_at", "") or "").strip()
                if role not in ("user", "assistant"):
                    continue
                messages.append(Message(role=role, content=content, created_at=msg_created_at))

        return Conversation(
            id=conversation_id,
            content_id=content_id,
            title=title,
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _build_summary(
        content_id: str,
        conversation_id: str,
        data: dict[str, Any],
    ) -> ConversationSummary | None:
        try:
            conv = FsAskStorage._parse_conversation(content_id, conversation_id, data)
        except Exception:
            return None

        last_preview = ""
        if conv.messages:
            last_preview = (conv.messages[-1].content or "").strip()
        last_preview = last_preview.replace("\n", " ").strip()
        if len(last_preview) > 160:
            last_preview = last_preview[:157] + "..."

        return ConversationSummary(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            last_message_preview=last_preview,
        )
