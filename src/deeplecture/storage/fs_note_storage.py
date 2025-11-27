from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from deeplecture.dto.storage import NoteRecord
from deeplecture.storage.path_resolver import PathResolver, resolve_path_resolver


class NoteStorage:
    """Filesystem-backed storage that delegates path resolution to ContentService."""

    def __init__(self, path_resolver: Optional[PathResolver] = None) -> None:
        self._path_resolver = resolve_path_resolver(path_resolver)

    def build_note_path(self, video_id: str) -> str:
        return self._path_resolver.ensure_notes_path(video_id)

    def load(self, video_id: str) -> Optional[NoteRecord]:
        note_path = self.build_note_path(video_id)
        if not os.path.exists(note_path):
            return None

        with open(note_path, "r", encoding="utf-8") as f:
            content = f.read()
        updated_at = datetime.fromtimestamp(os.path.getmtime(note_path))
        return NoteRecord(
            video_id=video_id,
            path=note_path,
            content=content,
            updated_at=updated_at,
        )

    def save(self, video_id: str, content: str) -> NoteRecord:
        note_path = self.build_note_path(video_id)
        os.makedirs(os.path.dirname(note_path), exist_ok=True)
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(content)
        updated_at = datetime.now()
        return NoteRecord(
            video_id=video_id,
            path=note_path,
            content=content,
            updated_at=updated_at,
        )


_default_note_storage: Optional[NoteStorage] = None


def get_default_note_storage(path_resolver: Optional[PathResolver] = None) -> NoteStorage:
    global _default_note_storage
    if path_resolver is not None:
        return NoteStorage(path_resolver=path_resolver)
    if _default_note_storage is None:
        _default_note_storage = NoteStorage()
    return _default_note_storage
