"""Unit tests for SlideLectureUseCase."""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from deeplecture.config.settings import SlideLectureConfig
from deeplecture.domain import ContentMetadata, ContentType, Segment
from deeplecture.use_cases.dto.slide import PageWorkPlan, SlideGenerationRequest, TranscriptPage, TranscriptSegment
from deeplecture.use_cases.slide_lecture import SlideLectureUseCase


@pytest.fixture
def mock_file_storage() -> MagicMock:
    """Create mock file storage."""
    return MagicMock()


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    """Create mock path resolver with deterministic content paths."""
    resolver = MagicMock()

    def _build_content_path(content_id: str, namespace: str, filename: str | None = None) -> str:
        if namespace == "slide" and filename == "slide.pdf":
            return f"/data/content/{content_id}/slide/slide.pdf"
        if namespace == "source.pdf" and filename is None:
            return f"/data/content/{content_id}/source.pdf"
        if namespace == "source" and filename == "source.pdf":
            return f"/data/content/{content_id}/source/source.pdf"
        raise AssertionError(f"Unexpected build_content_path args: {content_id=}, {namespace=}, {filename=}")

    resolver.build_content_path.side_effect = _build_content_path
    return resolver


@pytest.fixture
def usecase(
    mock_file_storage: MagicMock,
    mock_path_resolver: MagicMock,
) -> SlideLectureUseCase:
    """Create SlideLectureUseCase with mocked dependencies."""
    return SlideLectureUseCase(
        audio_processor=MagicMock(),
        video_processor=MagicMock(),
        file_storage=mock_file_storage,
        pdf_renderer=MagicMock(),
        tts_provider=MagicMock(),
        llm_provider=MagicMock(),
        prompt_registry=MagicMock(),
        path_resolver=mock_path_resolver,
        metadata_storage=MagicMock(),
        subtitle_storage=MagicMock(),
        config=SlideLectureConfig(),
        parallel_runner=MagicMock(),
    )


class TestSlideLectureResolvePdfPath:
    """Tests for slide PDF path resolution order."""

    @pytest.mark.unit
    def test_resolve_pdf_path_prefers_metadata_source_file(
        self,
        usecase: SlideLectureUseCase,
        mock_file_storage: MagicMock,
    ) -> None:
        """metadata.source_file should win over legacy slide/slide.pdf when both exist."""
        content_id = "test-content-id"
        metadata = ContentMetadata(
            id=content_id,
            type=ContentType.SLIDE,
            original_filename="slides.pdf",
            source_file=f"/data/content/{content_id}/source_v2.pdf",
        )

        mock_file_storage.file_exists.side_effect = lambda p: p in {
            metadata.source_file,
            f"/data/content/{content_id}/slide/slide.pdf",
        }

        resolved = usecase._resolve_pdf_path(content_id, metadata=metadata)

        assert resolved == metadata.source_file
        assert mock_file_storage.file_exists.call_args_list[0].args[0] == metadata.source_file

    @pytest.mark.unit
    def test_resolve_pdf_path_falls_back_when_metadata_source_missing(
        self,
        usecase: SlideLectureUseCase,
        mock_file_storage: MagicMock,
    ) -> None:
        """Should fall back to conventional source.pdf when metadata source is stale."""
        content_id = "test-content-id"
        metadata = ContentMetadata(
            id=content_id,
            type=ContentType.SLIDE,
            original_filename="slides.pdf",
            source_file=f"/data/content/{content_id}/stale.pdf",
        )

        expected = f"/data/content/{content_id}/source.pdf"
        mock_file_storage.file_exists.side_effect = lambda p: p == expected

        resolved = usecase._resolve_pdf_path(content_id, metadata=metadata)

        assert resolved == expected


@pytest.mark.unit
def test_generate_saves_source_enhanced_subtitles(
    usecase: SlideLectureUseCase,
    mock_path_resolver: MagicMock,
) -> None:
    content_id = "test-content-id"
    metadata = ContentMetadata(
        id=content_id,
        type=ContentType.SLIDE,
        original_filename="slides.pdf",
        source_file=f"/data/content/{content_id}/source.pdf",
    )
    usecase._metadata.get.return_value = metadata

    mock_path_resolver.ensure_content_dir.return_value = f"/data/content/{content_id}/slide_lecture"
    mock_path_resolver.temp_dir = "/tmp"

    plan = PageWorkPlan(
        page_index=1,
        image_path="/tmp/page_001.png",
        transcript_json_path="/tmp/page_001.json",
        page_audio_wav_path="/tmp/page_001.wav",
        segment_video_path="/tmp/page_001.mp4",
    )
    page = TranscriptPage(
        deck_id=content_id,
        page_index=1,
        source_language="en",
        target_language="zh",
        segments=[TranscriptSegment(id=1, source="hello", target="你好")],
    )
    segments_source = [Segment(start=0.0, end=1.0, text="hello")]
    segments_target = [Segment(start=0.0, end=1.0, text="你好")]

    usecase._resolve_pdf_path = MagicMock(return_value=f"/data/content/{content_id}/source.pdf")
    usecase._render_pdf_pages = MagicMock(return_value={1: "/tmp/page_001.png"})
    usecase._plan_pages = MagicMock(return_value=[plan])
    usecase._llm_provider.get.return_value = MagicMock()
    usecase._generate_page_raw = MagicMock(return_value="{}")
    usecase._parse_page_raw = MagicMock(return_value=page)
    usecase._write_page_json = MagicMock()
    usecase._render_page_audio = MagicMock(return_value=("/tmp/page_001.wav", 1.0, [(1, 1.0)]))
    usecase._build_subtitle_segments = MagicMock(return_value=(segments_source, segments_target))

    usecase._audio.concat_wavs_to_wav = MagicMock()
    usecase._audio.probe_duration_seconds.return_value = 1.0
    usecase._video.build_still_segment = MagicMock()
    usecase._video.concat_segments = MagicMock()
    usecase._video.mux_audio = MagicMock()
    usecase._video.probe_duration.return_value = 1.0

    def _map_ordered(items, fn, *, group, on_error=None):
        results = []
        for item in items:
            try:
                results.append(fn(item))
            except Exception as exc:  # pragma: no cover - defensive path
                if on_error is None:
                    raise
                results.append(on_error(exc, item))
        return results

    usecase._parallel.map_ordered.side_effect = _map_ordered

    result = usecase.generate(
        SlideGenerationRequest(
            content_id=content_id,
            source_language="en",
            target_language="zh",
        )
    )

    assert result.content_id == content_id

    usecase._subtitle_storage.delete.assert_has_calls(
        [
            call(content_id, "en"),
            call(content_id, "en_enhanced"),
            call(content_id, "zh"),
        ]
    )

    usecase._subtitle_storage.save.assert_has_calls(
        [
            call(content_id, segments_source, "en"),
            call(content_id, segments_source, "en_enhanced"),
            call(content_id, segments_target, "zh"),
        ]
    )
