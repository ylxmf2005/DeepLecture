from __future__ import annotations

import os
import re
from typing import List, Optional

from deeplecture.dto.storage import ConversationRecord
from deeplecture.storage.path_resolver import PathResolver, resolve_path_resolver

try:
    import json_repair  # type: ignore[import]
    import json as _std_json

    class _JsonWrapper:
        @staticmethod
        def load(file_obj):
            return json_repair.load(file_obj)

        @staticmethod
        def dump(obj, file_obj, **kwargs):
            return _std_json.dump(obj, file_obj, **kwargs)

    json = _JsonWrapper()
except ImportError:  # pragma: no cover - fallback
    import json  # type: ignore

def _sanitize_id(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(raw))


class AskStorage:
    """Filesystem-backed storage for Ask tab conversations."""

    def __init__(self, path_resolver: Optional[PathResolver] = None) -> None:
        self._path_resolver = resolve_path_resolver(path_resolver)

    def _conversations_dir(self, video_id: str) -> str:
        return self._path_resolver.ensure_ask_dir(video_id)

    def _conversation_path(self, video_id: str, conversation_id: str) -> str:
        safe_conv = _sanitize_id(conversation_id)
        return os.path.join(self._conversations_dir(video_id), f"{safe_conv}.json")

    def list_conversations(self, video_id: str) -> List[ConversationRecord]:
        directory = self._conversations_dir(video_id)
        if not os.path.exists(directory):
            return []

        items: List[ConversationRecord] = []
        for filename in os.listdir(directory):
            if not filename.endswith(".json"):
                continue
            conv_id = os.path.splitext(filename)[0]
            path = os.path.join(directory, filename)
            record = self._load_file(video_id, conv_id, path)
            if record:
                items.append(record)

        items.sort(key=lambda r: r.updated_at or "", reverse=True)
        return items

    def get_conversation(self, video_id: str, conversation_id: str) -> Optional[ConversationRecord]:
        path = self._conversation_path(video_id, conversation_id)
        return self._load_file(video_id, conversation_id, path)

    def save_conversation(self, record: ConversationRecord) -> ConversationRecord:
        path = self._conversation_path(record.video_id, record.conversation_id)
        payload = record.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        record.path = path
        return record

    def delete_conversation(self, video_id: str, conversation_id: str) -> bool:
        path = self._conversation_path(video_id, conversation_id)
        if not os.path.exists(path):
            return False
        os.remove(path)
        return True

    def _load_file(
        self,
        video_id: str,
        conversation_id: str,
        path: str,
    ) -> Optional[ConversationRecord]:
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None

        title = str(data.get("title") or "").strip() or f"Chat {conversation_id}"
        messages = data.get("messages") or []
        created_at = data.get("created_at")
        updated_at = data.get("updated_at") or created_at
        return ConversationRecord(
            video_id=video_id,
            conversation_id=conversation_id,
            title=title,
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
            path=path,
        )


_default_ask_storage: Optional[AskStorage] = None


def get_default_ask_storage(path_resolver: Optional[PathResolver] = None) -> AskStorage:
    global _default_ask_storage
    if path_resolver is not None:
        return AskStorage(path_resolver=path_resolver)
    if _default_ask_storage is None:
        _default_ask_storage = AskStorage()
    return _default_ask_storage
