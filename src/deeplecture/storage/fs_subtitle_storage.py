from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from deeplecture.dto.storage import SubtitleRecord
from deeplecture.storage.path_resolver import PathResolver, resolve_path_resolver


class SubtitleStorage:
    """
    Storage abstraction for subtitle files.

    This implementation focuses on mapping (video_id, language) pairs to
    concrete subtitle files on disk so that higher layers no longer need
    to know about OUTPUT_FOLDER or filename conventions.
    """

    def get_original(self, video_id: str) -> Optional[SubtitleRecord]:  # pragma: no cover - interface
        raise NotImplementedError

    def get_translation(self, video_id: str, target_language: str) -> Optional[SubtitleRecord]:  # pragma: no cover - interface
        raise NotImplementedError

    def get_enhanced(self, video_id: str) -> Optional[SubtitleRecord]:  # pragma: no cover - interface
        raise NotImplementedError

    def build_original_path(self, video_id: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def build_translation_path(self, video_id: str, target_language: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def build_enhanced_path(self, video_id: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def build_background_path(self, video_id: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class FsSubtitleStorage(SubtitleStorage):
    """
    Content-aware subtitle storage that scopes every file under
    outputs/subtitles/<content_id>/.
    """

    def __init__(self, path_resolver: Optional[PathResolver] = None) -> None:
        self._path_resolver = resolve_path_resolver(path_resolver)

    def build_original_path(self, video_id: str) -> str:
        directory = self._ensure_subtitle_dir(video_id)
        return os.path.join(directory, "original.srt")

    def build_translation_path(self, video_id: str, target_language: str) -> str:
        directory = self._ensure_translations_dir(video_id)
        normalized = self._normalize_language(target_language)
        return os.path.join(directory, f"{normalized}.srt")

    def build_enhanced_path(self, video_id: str) -> str:
        directory = self._ensure_subtitle_dir(video_id)
        return os.path.join(directory, "enhanced.srt")

    def build_background_path(self, video_id: str) -> str:
        directory = self._ensure_subtitle_dir(video_id)
        return os.path.join(directory, "background.json")

    def get_original(self, video_id: str) -> Optional[SubtitleRecord]:
        path = self._resolve_original_path(video_id)
        if not os.path.exists(path):
            return None
        created_at = datetime.fromtimestamp(os.path.getctime(path))
        return SubtitleRecord(
            video_id=video_id,
            language="original",
            path=path,
            is_translation=False,
            created_at=created_at,
        )

    def get_translation(self, video_id: str, target_language: str) -> Optional[SubtitleRecord]:
        path = self._resolve_translation_path(video_id, target_language)
        if not os.path.exists(path):
            return None
        created_at = datetime.fromtimestamp(os.path.getctime(path))
        return SubtitleRecord(
            video_id=video_id,
            language=self._normalize_language(target_language),
            path=path,
            is_translation=True,
            created_at=created_at,
        )

    def get_enhanced(self, video_id: str) -> Optional[SubtitleRecord]:
        path = self._resolve_enhanced_path(video_id)
        if not os.path.exists(path):
            return None
        created_at = datetime.fromtimestamp(os.path.getctime(path))
        return SubtitleRecord(
            video_id=video_id,
            language="enhanced",
            path=path,
            is_translation=False,
            created_at=created_at,
            is_enhanced=True,
        )

    def _resolve_original_path(self, video_id: str) -> str:
        directory = self._subtitles_dir(video_id)
        return os.path.join(directory, "original.srt")

    def _resolve_translation_path(self, video_id: str, target_language: str) -> str:
        directory = self._translations_dir(video_id)
        normalized = self._normalize_language(target_language)
        return os.path.join(directory, f"{normalized}.srt")

    def _resolve_enhanced_path(self, video_id: str) -> str:
        directory = self._subtitles_dir(video_id)
        return os.path.join(directory, "enhanced.srt")

    def _ensure_subtitle_dir(self, video_id: str) -> str:
        return self._path_resolver.ensure_content_dir(video_id, "subtitles")

    def _ensure_translations_dir(self, video_id: str) -> str:
        base = self._ensure_subtitle_dir(video_id)
        directory = os.path.join(base, "translations")
        os.makedirs(directory, exist_ok=True)
        return directory

    def _subtitles_dir(self, video_id: str) -> str:
        return self._path_resolver.build_content_path(video_id, "subtitles")

    def _translations_dir(self, video_id: str) -> str:
        return os.path.join(self._subtitles_dir(video_id), "translations")

    @staticmethod
    def _normalize_language(language: str) -> str:
        value = (language or "").strip().lower()
        return value or "default"


def get_default_subtitle_storage(path_resolver: Optional[PathResolver] = None) -> FsSubtitleStorage:
    return FsSubtitleStorage(path_resolver=path_resolver)
