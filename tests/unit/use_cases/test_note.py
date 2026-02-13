"""Unit tests for NoteUseCase."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from deeplecture.domain import ContentMetadata, ContentType
from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.dto.note import (
    GenerateNoteRequest,
    NotePart,
    SaveNoteRequest,
)
from deeplecture.use_cases.note import NoteUseCase


@pytest.fixture
def mock_metadata_storage() -> MagicMock:
    """Create mock metadata storage."""
    return MagicMock()


@pytest.fixture
def mock_note_storage() -> MagicMock:
    """Create mock note storage."""
    return MagicMock()


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    """Create mock subtitle storage."""
    return MagicMock()


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    """Create mock path resolver."""
    return MagicMock()


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create mock LLM service."""
    return MagicMock()


@pytest.fixture
def mock_llm_provider(mock_llm: MagicMock) -> MagicMock:
    """Create mock LLM provider."""
    provider = MagicMock()
    provider.get.return_value = mock_llm
    return provider


@pytest.fixture
def mock_prompt_registry() -> MagicMock:
    """Create mock prompt registry."""
    registry = MagicMock()
    builder = MagicMock()
    builder.build.return_value = MagicMock(system_prompt="system", user_prompt="user")
    registry.get.return_value = builder
    return registry


@pytest.fixture
def mock_parallel_runner() -> MagicMock:
    """Create mock parallel runner."""
    runner = MagicMock()
    runner.run.side_effect = lambda tasks: [task() for task in tasks]
    return runner


@pytest.fixture
def mock_pdf_extractor() -> MagicMock:
    """Create mock PDF text extractor."""
    return MagicMock()


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
    """Create sample content metadata."""
    return ContentMetadata(
        id="test-content-id",
        type=ContentType.VIDEO,
        original_filename="test.mp4",
        source_file="/tmp/test.mp4",
    )


class TestNoteUseCaseGetNote:
    """Tests for get_note() method."""

    @pytest.mark.unit
    def test_get_note_success(
        self,
        usecase: NoteUseCase,
        mock_note_storage: MagicMock,
    ) -> None:
        """get_note() should return note when it exists."""
        # load() returns tuple (content, updated_at)
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
        """save_note() should save content and update metadata."""
        mock_metadata_storage.get.return_value = sample_metadata

        request = SaveNoteRequest(
            content_id="test-content-id",
            content="# My Note\nSome content here.",
        )
        result = usecase.save_note(request)

        assert result.content_id == "test-content-id"
        assert "My Note" in result.content
        mock_note_storage.save.assert_called_once()


class TestNoteUseCaseGenerateNote:
    """Tests for generate_note() method."""

    @pytest.mark.unit
    def test_generate_note_requires_llm(
        self,
        mock_metadata_storage: MagicMock,
        mock_note_storage: MagicMock,
        mock_path_resolver: MagicMock,
        mock_parallel_runner: MagicMock,
        sample_metadata: ContentMetadata,
    ) -> None:
        """generate_note() should raise when LLM not available."""
        mock_llm_provider = MagicMock()
        mock_llm_provider.get.side_effect = ValueError("LLM not configured")

        usecase = NoteUseCase(
            metadata_storage=mock_metadata_storage,
            note_storage=mock_note_storage,
            path_resolver=mock_path_resolver,
            llm_provider=mock_llm_provider,
            prompt_registry=MagicMock(),
            parallel_runner=mock_parallel_runner,
        )
        mock_metadata_storage.get.return_value = sample_metadata

        request = GenerateNoteRequest(
            content_id="test-content-id",
            language="en",
        )

        with pytest.raises(ValueError, match="LLM"):
            usecase.generate_note(request)

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
    def test_generate_note_raises_when_generated_content_is_effectively_empty(
        self,
        usecase: NoteUseCase,
        mock_metadata_storage: MagicMock,
        mock_note_storage: MagicMock,
        sample_metadata: ContentMetadata,
    ) -> None:
        """generate_note() should fail instead of saving blank placeholder output."""
        mock_metadata_storage.get.return_value = sample_metadata
        usecase._load_context = MagicMock(return_value=("context", ["subtitle"]))  # type: ignore[method-assign]
        usecase._build_outline = MagicMock(  # type: ignore[method-assign]
            return_value=[NotePart(id=1, title="Part 1", summary="", focus_points=[])]
        )
        usecase._generate_parts_parallel = MagicMock(return_value=" \n <br /> \n ")  # type: ignore[method-assign]

        request = GenerateNoteRequest(
            content_id="test-content-id",
            language="en",
        )

        with pytest.raises(ValueError, match="empty note content"):
            usecase.generate_note(request)

        mock_note_storage.save.assert_not_called()


class TestNoteUseCaseSelectSources:
    """Tests for _select_sources() helper."""

    @pytest.mark.unit
    def test_select_sources_both_uses_available_sources(self) -> None:
        """Mode 'both' should not require both sources to exist."""
        assert NoteUseCase._select_sources(mode="both", has_subtitle=True, has_slides=False) == (True, False)
        assert NoteUseCase._select_sources(mode="both", has_subtitle=False, has_slides=True) == (False, True)
        assert NoteUseCase._select_sources(mode="both", has_subtitle=True, has_slides=True) == (True, True)

    @pytest.mark.unit
    def test_select_sources_auto_uses_available_sources(self) -> None:
        """Mode 'auto' should behave like 'both' (use what's available)."""
        assert NoteUseCase._select_sources(mode="auto", has_subtitle=True, has_slides=False) == (True, False)
        assert NoteUseCase._select_sources(mode="auto", has_subtitle=False, has_slides=True) == (False, True)
        assert NoteUseCase._select_sources(mode="auto", has_subtitle=True, has_slides=True) == (True, True)

    @pytest.mark.unit
    def test_select_sources_requires_any_source(self) -> None:
        """No available sources should still raise."""
        with pytest.raises(ValueError, match="no transcript or slides"):
            NoteUseCase._select_sources(mode="both", has_subtitle=False, has_slides=False)


class TestNoteUseCaseOutlinePassthrough:
    """Tests that outline is passed to part prompt builder."""

    @pytest.mark.unit
    def test_generate_parts_parallel_passes_outline_to_prompt_builder(
        self,
        usecase: NoteUseCase,
        mock_llm: MagicMock,
        mock_prompt_registry: MagicMock,
        mock_parallel_runner: MagicMock,
    ) -> None:
        """_generate_parts_parallel must pass outline to prompt_builder.build()."""
        outline = [
            NotePart(id=1, title="Part A", summary="Summary A", focus_points=["fp1"]),
            NotePart(id=2, title="Part B", summary="Summary B", focus_points=["fp2"]),
        ]

        # Make parallel runner execute the functions directly
        mock_parallel_runner.map_ordered.side_effect = lambda items, fn, **kw: [fn(item) for item in items]
        mock_llm.complete.return_value = "## Part 1: Part A\n\nContent here."

        usecase._generate_parts_parallel(
            outline=outline,
            language="English",
            context_block="Some context.",
            instruction="",
            profile="",
            llm=mock_llm,
            prompts=None,
        )

        # Verify prompt builder was called with outline kwarg
        builder = mock_prompt_registry.get.return_value
        calls = builder.build.call_args_list
        assert len(calls) == 2

        for call in calls:
            assert "outline" in call.kwargs
            assert call.kwargs["outline"] is outline
