"""Unit tests for UploadUseCase."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest

from deeplecture.domain.errors import UnsupportedFileFormatError
from deeplecture.use_cases.dto.upload import (
    UploadPDFRequest,
    UploadVideoRequest,
)
from deeplecture.use_cases.upload import UploadUseCase


@pytest.fixture
def mock_metadata_storage() -> MagicMock:
    """Create mock metadata storage."""
    return MagicMock()


@pytest.fixture
def mock_file_storage() -> MagicMock:
    """Create mock file storage."""
    return MagicMock()


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    """Create mock path resolver."""
    resolver = MagicMock()
    resolver.temp_dir = "/tmp/upload"
    resolver.ensure_content_root.return_value = "/data/content/test-id"
    return resolver


@pytest.fixture
def usecase(
    mock_metadata_storage: MagicMock,
    mock_file_storage: MagicMock,
    mock_path_resolver: MagicMock,
) -> UploadUseCase:
    """Create UploadUseCase with mocked dependencies."""
    return UploadUseCase(
        metadata_storage=mock_metadata_storage,
        file_storage=mock_file_storage,
        path_resolver=mock_path_resolver,
    )


class TestUploadUseCaseUploadVideo:
    """Tests for upload_video() method."""

    @pytest.mark.unit
    def test_upload_video_success(
        self,
        usecase: UploadUseCase,
        mock_metadata_storage: MagicMock,
        mock_file_storage: MagicMock,
    ) -> None:
        """upload_video() should create content and save file."""
        video_content = b"fake video content"

        request = UploadVideoRequest(
            content_id="test-content-id",
            filename="test.mp4",
            file_data=BytesIO(video_content),
        )
        result = usecase.upload_video(request)

        assert result.content_id == "test-content-id"
        assert result.content_type == "video"
        mock_metadata_storage.save.assert_called_once()
        mock_file_storage.save_file.assert_called_once()

    @pytest.mark.unit
    def test_upload_video_uses_original_filename(
        self,
        usecase: UploadUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """upload_video() should store original filename in metadata."""
        video_content = b"fake video content"

        request = UploadVideoRequest(
            content_id="test-content-id",
            filename="my_lecture.mp4",
            file_data=BytesIO(video_content),
        )
        usecase.upload_video(request)

        saved_metadata = mock_metadata_storage.save.call_args[0][0]
        assert saved_metadata.original_filename == "my_lecture.mp4"

    @pytest.mark.unit
    def test_upload_video_unsupported_format(
        self,
        usecase: UploadUseCase,
    ) -> None:
        """upload_video() should reject unsupported formats."""
        request = UploadVideoRequest(
            content_id="test-content-id",
            filename="test.txt",
            file_data=BytesIO(b"not a video"),
        )

        with pytest.raises(UnsupportedFileFormatError):
            usecase.upload_video(request)


class TestUploadUseCaseUploadPDF:
    """Tests for upload_pdf() method."""

    @pytest.mark.unit
    def test_upload_pdf_success(
        self,
        usecase: UploadUseCase,
        mock_metadata_storage: MagicMock,
        mock_file_storage: MagicMock,
    ) -> None:
        """upload_pdf() should create content and save file."""
        pdf_content = b"%PDF-1.4 fake pdf content"

        request = UploadPDFRequest(
            content_id="test-content-id",
            filename="slides.pdf",
            file_data=BytesIO(pdf_content),
        )
        result = usecase.upload_pdf(request)

        assert result.content_id == "test-content-id"
        assert result.content_type == "slide"
        mock_metadata_storage.save.assert_called_once()
        mock_file_storage.save_file.assert_called_once()

    @pytest.mark.unit
    def test_upload_pdf_unsupported_format(
        self,
        usecase: UploadUseCase,
    ) -> None:
        """upload_pdf() should reject non-PDF files."""
        request = UploadPDFRequest(
            content_id="test-content-id",
            filename="document.docx",
            file_data=BytesIO(b"not a pdf"),
        )

        with pytest.raises(UnsupportedFileFormatError):
            usecase.upload_pdf(request)
