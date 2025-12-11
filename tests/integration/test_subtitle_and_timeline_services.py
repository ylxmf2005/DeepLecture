from __future__ import annotations

from pathlib import Path

from deeplecture.storage.artifact_registry import ArtifactRegistry
from deeplecture.storage.fs_subtitle_storage import FsSubtitleStorage
from deeplecture.storage.fs_timeline_storage import FsTimelineStorage
from deeplecture.storage.metadata_storage import ContentMetadata, MetadataStorage
from deeplecture.services.content_service import ContentService
from deeplecture.services.subtitle_service import SubtitleService
from deeplecture.services.timeline_service import TimelineService


def test_subtitle_service_generates_original_srt(tmp_path) -> None:
    content_service, metadata_storage = _build_content_env(tmp_path, "video1")
    storage = FsSubtitleStorage(path_resolver=content_service)

    class _FakeEngine:
        def generate_subtitles(self, video_path: str, output_path: str, language: str = "en") -> bool:
            assert Path(video_path).exists()
            Path(output_path).write_text("dummy subtitle", encoding="utf-8")
            return True

    # Mock LLM factory to avoid AppContext initialization
    class _FakeLLMFactory:
        def get_llm_for_task(self, task_name: str):
            return object()

    service = SubtitleService(
        storage=storage,
        subtitle_engine=_FakeEngine(),
        content_service=content_service,
        llm_factory=_FakeLLMFactory(),
    )

    service.generate_subtitles_sync("video1", "en")

    record = storage.get_original("video1")
    assert record is not None
    assert Path(record.path).read_text(encoding="utf-8") == "dummy subtitle"

    metadata = metadata_storage.get("video1")
    assert metadata is not None
    assert metadata.subtitle_status == "ready"
    assert metadata.subtitle_path == record.path


def test_subtitle_service_translation_path_and_exists(tmp_path) -> None:
    content_service, metadata_storage = _build_content_env(tmp_path, "video2")
    storage = FsSubtitleStorage(path_resolver=content_service)

    original_path = storage.build_original_path("video2")
    Path(original_path).write_text("src", encoding="utf-8")
    content_service.mark_subtitles_generated("video2", original_path)

    class _FakeEnhanceTranslator:
        def process_to_entries(self, srt_content: str, target_language: str = "zh"):
            assert "src" in srt_content
            return (
                [{"start": 0.0, "end": 1.0, "text_en": "src", "text_zh": f"translated-{target_language}"}],
                {"topic": "test", "characters": []},
            )

        def _reconstruct_srt(self, entries):
            """Build SRT format from entries."""
            lines = []
            for i, e in enumerate(entries, 1):
                start_ms = int(e["start"] * 1000)
                end_ms = int(e["end"] * 1000)
                start_str = f"{start_ms // 3600000:02d}:{(start_ms // 60000) % 60:02d}:{(start_ms // 1000) % 60:02d},{start_ms % 1000:03d}"
                end_str = f"{end_ms // 3600000:02d}:{(end_ms // 60000) % 60:02d}:{(end_ms // 1000) % 60:02d},{end_ms % 1000:03d}"
                text = (e.get("text_en") or "").strip()
                lines.append(f"{i}\n{start_str} --> {end_str}\n{text}\n")
            return "\n".join(lines)

    # Mock LLM factory to avoid AppContext initialization
    class _FakeLLMFactory:
        def get_llm_for_task(self, task_name: str):
            return object()

    service = SubtitleService(
        storage=storage,
        enhance_translator=_FakeEnhanceTranslator(),
        content_service=content_service,
        llm_factory=_FakeLLMFactory(),
    )

    service.enhance_and_translate_sync("video2", "zh")

    translated_path = service.resolve_translation_path("video2", "zh")
    assert Path(translated_path).exists()
    # The translated content is in SRT format now with text_zh
    translated_content = Path(translated_path).read_text(encoding="utf-8")
    assert "translated-zh" in translated_content
    assert service.translation_exists("video2", "zh") is True

    metadata = metadata_storage.get("video2")
    assert metadata is not None
    assert metadata.translation_status == "ready"
    assert metadata.translated_subtitle_path == translated_path


def test_timeline_service_generates_placeholder_and_schedules(tmp_path) -> None:
    subtitle_path = tmp_path / "video3.srt"
    subtitle_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    content_service, metadata_storage = _build_content_env(
        tmp_path,
        "video3",
        subtitle_path=subtitle_path,
        subtitle_status="ready",
    )
    storage = FsTimelineStorage(path_resolver=content_service)

    class _FakeLLMFactory:
        def get_llm(self):
            return object()

    class _FakeTimelineGenerator:
        def __init__(self, _llm) -> None:
            pass

        def generate_from_srt(self, srt_path: str, *, language: str | None = None, learner_profile=None):
            assert Path(srt_path).exists()
            return []

    service = TimelineService(
        storage=storage,
        content_service=content_service,
        llm_factory=_FakeLLMFactory(),
        timeline_generator_factory=lambda _llm: _FakeTimelineGenerator(_llm),
    )

    response = service.generate_timeline(
        video_id="video3",
        language="zh",
        learner_profile=None,
        force=False,
    )

    assert response["video_id"] == "video3"
    assert response["cached"] is False
    assert response["timeline"] == []


def _build_content_env(
    tmp_path,
    content_id: str,
    subtitle_path: Path | None = None,
    *,
    subtitle_status: str = "none",
) -> tuple[ContentService, MetadataStorage]:
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir(exist_ok=True)
    outputs.mkdir(exist_ok=True)

    metadata_storage = MetadataStorage(metadata_folder=str(outputs / "metadata"))
    artifact_registry = ArtifactRegistry(registry_folder=str(outputs / "artifacts"))
    content_service = ContentService(
        metadata_storage=metadata_storage,
        artifact_registry=artifact_registry,
        upload_folder=str(uploads),
        output_folder=str(outputs),
    )

    video_path = uploads / f"{content_id}.mp4"
    video_path.write_bytes(b"video")
    now = "2025-01-01T00:00:00Z"
    metadata_storage.save(
        ContentMetadata(
            id=content_id,
            type="video",
            original_filename=f"{content_id}.mp4",
            created_at=now,
            updated_at=now,
            source_file=str(video_path),
            video_file=str(video_path),
            subtitle_status=subtitle_status,
            subtitle_path=str(subtitle_path) if subtitle_path else None,
        )
    )

    return content_service, metadata_storage
