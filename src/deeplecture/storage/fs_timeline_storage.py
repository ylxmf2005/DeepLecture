from __future__ import annotations

import os
from typing import Any, Dict, Optional

from deeplecture.dto.storage import TimelineRecord
from deeplecture.storage.path_resolver import PathResolver, resolve_path_resolver
from deeplecture.storage.timeline_io import load_timeline_from_file, save_timeline_to_file


class TimelineStorage:
    """
    Storage abstraction for timeline JSON payloads.
    """

    def build_timeline_dir(self, video_id: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def build_timeline_path(self, video_id: str, language: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def load(self, video_id: str, language: str) -> Optional[Dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError

    def save(
        self,
        payload: Dict[str, Any],
        video_id: str,
        language: str,
        learner_profile: Optional[str],
    ) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class FsTimelineStorage(TimelineStorage):
    """
    File-system based implementation that uses the existing helper
    functions from deeplecture.transcription.interactive to persist and load timelines.
    """

    def __init__(self, path_resolver: Optional[PathResolver] = None) -> None:
        self._path_resolver = resolve_path_resolver(path_resolver)

    def build_timeline_dir(self, video_id: str) -> str:
        return self._path_resolver.ensure_timeline_dir(video_id)

    def build_timeline_path(self, video_id: str, language: str) -> str:
        normalized = self._normalize_language(language)
        directory = self.build_timeline_dir(video_id)
        return os.path.join(directory, f"timeline_{normalized}.json")

    def load(self, video_id: str, language: str) -> Optional[Dict[str, Any]]:
        path = self.build_timeline_path(video_id, language)
        return load_timeline_from_file(path)

    def save(
        self,
        payload: Dict[str, Any],
        video_id: str,
        language: str,
        learner_profile: Optional[str],
    ) -> str:
        normalized = self._normalize_language(language)
        directory = self.build_timeline_dir(video_id)
        status = str(payload.get("status", "ready"))
        error = payload.get("error")
        entries = payload.get("timeline", [])

        path = save_timeline_to_file(
            entries,
            video_id=video_id,
            language=normalized,
            output_dir=directory,
            learner_profile=learner_profile,
            status=status,
            error=error,
        )
        return path

    @staticmethod
    def _normalize_language(language: str) -> str:
        value = (language or "").strip()
        return value or "default"


def get_default_timeline_storage(path_resolver: Optional[PathResolver] = None) -> FsTimelineStorage:
    return FsTimelineStorage(path_resolver=path_resolver)
