"""Unit tests for NoteUseCase."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from deeplecture.domain import ContentMetadata, ContentType
from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.dto.note import (
    GenerateNoteRequest,
    SaveNoteRequest,
)
from deeplecture.use_cases.note import NoteUseCase

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_metadata_storage() -> MagicMock:
    """Create mock metadata storage."""
    storage = MagicMock()
    storage.get.return_value = None
    storage.save.return_value = None
    return storage


@pytest.fixture
def mock_note_storage() -> MagicMock:
    """Create mock note storage."""
    storage = MagicMock()
    storage.load.return_value = None
    storage.save.return_value = datetime.now(timezone.utc)
    storage.exists.return_value = False
    return storage


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    """Create mock subtitle storage."""
    storage = MagicMock()
    storage.list_languages.return_value = []
    return storage


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    """Create mock path resolver."""
    resolver = MagicMock()
    resolver.build_content_path.return_value = "/tmp/test/slide/slide.pdf"
    return resolver


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create mock LLM instance."""
    llm = MagicMock()
    llm.complete.return_value = '{"parts": []}'
    return llm


@pytest.fixture
def mock_llm_provider(mock_llm: MagicMock) -> MagicMock:
    """Create mock LLM provider that returns mock_llm."""
    provider = MagicMock()
    provider.get.return_value = mock_llm
    return provider


@pytest.fixture
def mock_prompt_builder() -> MagicMock:
    """Create mock prompt builder."""
    builder = MagicMock()
    spec = MagicMock()
    spec.user_prompt = "test user prompt"
    spec.system_prompt = "test system prompt"
    builder.build.return_value = spec
    return builder


@pytest.fixture
def mock_prompt_registry(mock_prompt_builder: MagicMock) -> MagicMock:
    """Create mock prompt registry."""
    registry = MagicMock()
    registry.get.return_value = mock_prompt_builder
    return registry


@pytest.fixture
def mock_parallel_runner() -> MagicMock:
    """Create mock parallel runner with map_ordered support."""
    runner = MagicMock()

    def map_ordered_impl(
        items: list[Any],
        func: Any,
        group: str = "",
        on_error: Any = None,
    ) -> list[Any]:
        results = []
        for item in items:
            try:
                results.append(func(item))
            except Exception as e:
                if on_error:
                    results.append(on_error(e, item))
                else:
                    raise
        return results

    runner.map_ordered.side_effect = map_ordered_impl
    return runner


@pytest.fixture
def mock_pdf_extractor() -> MagicMock:
    """Create mock PDF text extractor."""
    extractor = MagicMock()
    extractor.extract_text.return_value = ""
    return extractor


@pytest.fixture
def usecase(
    mock_metadata_storage: MagicMock,
    mock_note_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_path_resolver: MagicMock,
    mock_llm_provider: MagicMock,
    mock_prompt_registry: MagicMock,
    mock_parallel_runner: MagicMock,
    mock_pdf_extractor: MagicMock,
) -> NoteUseCase:
    """Create NoteUseCase with mocked dependencies."""
    return NoteUseCase(
        metadata_storage=mock_metadata_storage,
        note_storage=mock_note_storage,
        subtitle_storage=mock_subtitle_storage,
        path_resolver=mock_path_resolver,
        llm_provider=mock_llm_provider,
        prompt_registry=mock_prompt_registry,
        parallel_runner=mock_parallel_runner,
        pdf_text_extractor=mock_pdf_extractor,
    )


@pytest.fixture
def sample_metadata() -> ContentMetadata:
    """Create sample content metadata for video."""
    return ContentMetadata(
        id="test-content-id",
        type=ContentType.VIDEO,
        original_filename="test.mp4",
        source_file="/tmp/test.mp4",
    )


@pytest.fixture
def sample_pdf_metadata() -> ContentMetadata:
    """Create sample content metadata for PDF/slide content."""
    return ContentMetadata(
        id="test-pdf-id",
        type=ContentType.SLIDE,
        original_filename="test.pdf",
        source_file="/tmp/test.pdf",
    )


# =============================================================================
# TEST: get_note()
# =============================================================================


class TestNoteUseCaseGetNote:
    """Tests for get_note() method."""

    @pytest.mark.unit
    def test_get_note_success(
        self,
        usecase: NoteUseCase,
        mock_note_storage: MagicMock,
    ) -> None:
        """get_note() should return note when it exists."""
        mock_note_storage.load.return_value = (
            "# Test Note\nThis is content.",
            datetime.now(timezone.utc),
        )

        result = usecase.get_note("test-content-id")

        assert result is not None
        assert result.content_id == "test-content-id"
        assert "Test Note" in result.content
        mock_note_storage.load.assert_called_once_with("test-content-id")

    @pytest.mark.unit
    def test_get_note_not_found(
        self,
        usecase: NoteUseCase,
        mock_note_storage: MagicMock,
    ) -> None:
        """get_note() should return None when note doesn't exist."""
        mock_note_storage.load.return_value = None

        result = usecase.get_note("nonexistent-id")

        assert result is None


# =============================================================================
# TEST: save_note()
# =============================================================================


class TestNoteUseCaseSaveNote:
    """Tests for save_note() method."""

    @pytest.mark.unit
    def test_save_note_success(
        self,
        usecase: NoteUseCase,
        mock_note_storage: MagicMock,
        mock_metadata_storage: MagicMock,
        sample_metadata: ContentMetadata,
    ) -> None:
        """save_note() should save content and update metadata status."""
        mock_metadata_storage.get.return_value = sample_metadata

        request = SaveNoteRequest(
            content_id="test-content-id",
            content="# My Note\nSome content here.",
        )
        result = usecase.save_note(request)

        assert result.content_id == "test-content-id"
        assert "My Note" in result.content
        mock_note_storage.save.assert_called_once()
        # Verify metadata status was updated
        mock_metadata_storage.save.assert_called_once()

    @pytest.mark.unit
    def test_save_note_updates_status_to_ready(
        self,
        usecase: NoteUseCase,
        mock_note_storage: MagicMock,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """save_note() should set notes_status to READY."""
        # Use MagicMock for metadata to allow mocking with_status
        mock_metadata = MagicMock()
        updated_metadata = MagicMock()
        mock_metadata.with_status.return_value = updated_metadata
        mock_metadata_storage.get.return_value = mock_metadata

        request = SaveNoteRequest(content_id="test-content-id", content="content")
        usecase.save_note(request)

        mock_metadata.with_status.assert_called_once_with("notes", "ready")
        mock_metadata_storage.save.assert_called_once_with(updated_metadata)


# =============================================================================
# TEST: generate_note()
# =============================================================================


class TestNoteUseCaseGenerateNote:
    """Tests for generate_note() method."""

    @pytest.mark.unit
    def test_generate_note_content_not_found(
        self,
        usecase: NoteUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """generate_note() should raise when content doesn't exist."""
        mock_metadata_storage.get.return_value = None

        request = GenerateNoteRequest(
            content_id="nonexistent-id",
            language="en",
        )

        with pytest.raises(ContentNotFoundError):
            usecase.generate_note(request)

    @pytest.mark.unit
    def test_generate_note_calls_llm_provider(
        self,
        usecase: NoteUseCase,
        mock_metadata_storage: MagicMock,
        mock_llm_provider: MagicMock,
        mock_subtitle_storage: MagicMock,
        sample_metadata: ContentMetadata,
    ) -> None:
        """generate_note() should get LLM from provider."""
        mock_metadata_storage.get.return_value = sample_metadata
        mock_subtitle_storage.list_languages.return_value = ["en"]

        # Mock subtitle loading
        with patch.object(
            usecase, "_load_subtitle_context", return_value="Test transcript"
        ):
            request = GenerateNoteRequest(
                content_id="test-content-id",
                language="en",
                context_mode="subtitle",
                llm_model="gpt-4",
            )

            with contextlib.suppress(Exception):
                usecase.generate_note(request)

            mock_llm_provider.get.assert_called_with("gpt-4")


# =============================================================================
# TEST: _select_sources() - Context Mode Selection
# =============================================================================


class TestSelectSources:
    """Tests for _select_sources() static method."""

    @pytest.mark.unit
    def test_select_sources_subtitle_mode(self) -> None:
        """subtitle mode should only use subtitle when available."""
        use_sub, use_slide = NoteUseCase._select_sources(
            mode="subtitle",
            content_type="video",
            has_subtitle=True,
            has_slides=True,
        )
        assert use_sub is True
        assert use_slide is False

    @pytest.mark.unit
    def test_select_sources_subtitle_mode_not_available(self) -> None:
        """subtitle mode should raise when subtitles not available."""
        with pytest.raises(ValueError, match="no subtitles"):
            NoteUseCase._select_sources(
                mode="subtitle",
                content_type="video",
                has_subtitle=False,
                has_slides=True,
            )

    @pytest.mark.unit
    def test_select_sources_slide_mode(self) -> None:
        """slide mode should only use slides when available."""
        use_sub, use_slide = NoteUseCase._select_sources(
            mode="slide",
            content_type="pdf",
            has_subtitle=True,
            has_slides=True,
        )
        assert use_sub is False
        assert use_slide is True

    @pytest.mark.unit
    def test_select_sources_slide_mode_not_available(self) -> None:
        """slide mode should raise when slides not available."""
        with pytest.raises(ValueError, match="no slide deck"):
            NoteUseCase._select_sources(
                mode="slide",
                content_type="pdf",
                has_subtitle=True,
                has_slides=False,
            )

    @pytest.mark.unit
    def test_select_sources_both_mode_uses_available(self) -> None:
        """both mode should use all available sources (not require both)."""
        # Only subtitle available
        use_sub, use_slide = NoteUseCase._select_sources(
            mode="both",
            content_type="video",
            has_subtitle=True,
            has_slides=False,
        )
        assert use_sub is True
        assert use_slide is False

        # Only slides available
        use_sub, use_slide = NoteUseCase._select_sources(
            mode="both",
            content_type="pdf",
            has_subtitle=False,
            has_slides=True,
        )
        assert use_sub is False
        assert use_slide is True

        # Both available
        use_sub, use_slide = NoteUseCase._select_sources(
            mode="both",
            content_type="video",
            has_subtitle=True,
            has_slides=True,
        )
        assert use_sub is True
        assert use_slide is True

    @pytest.mark.unit
    def test_select_sources_auto_mode_video_prefers_subtitle(self) -> None:
        """auto mode for video should prefer subtitle."""
        use_sub, _use_slide = NoteUseCase._select_sources(
            mode="auto",
            content_type="video",
            has_subtitle=True,
            has_slides=True,
        )
        assert use_sub is True
        # May also include slides

    @pytest.mark.unit
    def test_select_sources_auto_mode_video_fallback_to_slides(self) -> None:
        """auto mode for video should fallback to slides if no subtitle."""
        use_sub, use_slide = NoteUseCase._select_sources(
            mode="auto",
            content_type="video",
            has_subtitle=False,
            has_slides=True,
        )
        assert use_sub is False
        assert use_slide is True

    @pytest.mark.unit
    def test_select_sources_auto_mode_pdf_prefers_slides(self) -> None:
        """auto mode for PDF should prefer slides."""
        _use_sub, use_slide = NoteUseCase._select_sources(
            mode="auto",
            content_type="pdf",
            has_subtitle=True,
            has_slides=True,
        )
        assert use_slide is True
        # May also include subtitle

    @pytest.mark.unit
    def test_select_sources_no_sources_available_video(self) -> None:
        """Should raise with helpful message for video with no sources."""
        with pytest.raises(ValueError, match="subtitles"):
            NoteUseCase._select_sources(
                mode="auto",
                content_type="video",
                has_subtitle=False,
                has_slides=False,
            )

    @pytest.mark.unit
    def test_select_sources_no_sources_available_pdf(self) -> None:
        """Should raise when no sources available for PDF."""
        with pytest.raises(ValueError, match="no transcript or slides"):
            NoteUseCase._select_sources(
                mode="auto",
                content_type="pdf",
                has_subtitle=False,
                has_slides=False,
            )

    @pytest.mark.unit
    def test_select_sources_invalid_mode(self) -> None:
        """Should raise for unsupported context_mode."""
        with pytest.raises(ValueError, match="Unsupported context_mode"):
            NoteUseCase._select_sources(
                mode="invalid",
                content_type="video",
                has_subtitle=True,
                has_slides=True,
            )


# =============================================================================
# TEST: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in note generation."""

    @pytest.mark.unit
    def test_render_error_does_not_leak_exception_details(
        self,
        usecase: NoteUseCase,
        mock_metadata_storage: MagicMock,
        mock_llm: MagicMock,
        mock_parallel_runner: MagicMock,
        mock_prompt_registry: MagicMock,
        sample_metadata: ContentMetadata,
    ) -> None:
        """Error rendering should not expose internal exception details."""
        mock_metadata_storage.get.return_value = sample_metadata

        # Make outline generation return valid parts
        mock_llm.complete.side_effect = [
            '{"parts": [{"id": 1, "title": "Test", "summary": "Test", "focus_points": []}]}',
            Exception("Internal error with /secret/path"),
        ]

        # Capture what parallel_runner receives
        def capture_map_ordered(items, func, group="", on_error=None):
            results = []
            for item in items:
                try:
                    results.append(func(item))
                except Exception as e:
                    if on_error:
                        result = on_error(e, item)
                        # Verify error message doesn't contain internal details
                        assert "/secret/path" not in result
                        assert "Internal error" not in result
                        assert "Generation failed" in result
                        results.append(result)
                    else:
                        raise
            return results

        mock_parallel_runner.map_ordered.side_effect = capture_map_ordered

        with patch.object(usecase, "_load_subtitle_context", return_value="Test"):
            request = GenerateNoteRequest(
                content_id="test-content-id",
                language="en",
                context_mode="subtitle",
            )
            # This should complete without exposing exception details
            with contextlib.suppress(Exception):
                usecase.generate_note(request)
