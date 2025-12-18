"""Unit tests for NoteUseCase."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from deeplecture.domain import ContentMetadata, ContentType
from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.dto.note import (
    GenerateNoteRequest,
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
    mock_llm: MagicMock,
    mock_parallel_runner: MagicMock,
    mock_pdf_extractor: MagicMock,
) -> NoteUseCase:
    """Create NoteUseCase with mocked dependencies."""
    return NoteUseCase(
        metadata_storage=mock_metadata_storage,
        note_storage=mock_note_storage,
        subtitle_storage=mock_subtitle_storage,
        path_resolver=mock_path_resolver,
        llm=mock_llm,
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
        usecase = NoteUseCase(
            metadata_storage=mock_metadata_storage,
            note_storage=mock_note_storage,
            path_resolver=mock_path_resolver,
            llm=None,
            parallel_runner=mock_parallel_runner,
        )
        mock_metadata_storage.get.return_value = sample_metadata

        request = GenerateNoteRequest(
            content_id="test-content-id",
            language="en",
        )

        with pytest.raises(RuntimeError, match="LLM"):
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
