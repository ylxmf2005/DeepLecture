"""Unit tests for ContentUseCase."""

from datetime import timezone
from unittest.mock import MagicMock, create_autospec

import pytest

from deeplecture.domain import ContentMetadata
from deeplecture.domain.entities.content import ContentType
from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.content import ContentUseCase
from deeplecture.use_cases.interfaces import (
    ArtifactStorageProtocol,
    FileStorageProtocol,
    MetadataStorageProtocol,
    PathResolverProtocol,
)

UTC = timezone.utc


class TestContentUseCase:
    """Tests for ContentUseCase."""

    @pytest.fixture
    def mock_metadata_storage(self) -> MagicMock:
        """Create mock metadata storage."""
        return create_autospec(MetadataStorageProtocol, instance=True)

    @pytest.fixture
    def mock_artifact_storage(self) -> MagicMock:
        """Create mock artifact storage."""
        return create_autospec(ArtifactStorageProtocol, instance=True)

    @pytest.fixture
    def mock_file_storage(self) -> MagicMock:
        """Create mock file storage."""
        return create_autospec(FileStorageProtocol, instance=True)

    @pytest.fixture
    def mock_path_resolver(self) -> MagicMock:
        """Create mock path resolver."""
        mock = create_autospec(PathResolverProtocol, instance=True)
        mock.get_content_dir.return_value = "/data/content/content-123"
        return mock

    @pytest.fixture
    def usecase(
        self,
        mock_metadata_storage: MagicMock,
        mock_artifact_storage: MagicMock,
        mock_file_storage: MagicMock,
        mock_path_resolver: MagicMock,
    ) -> ContentUseCase:
        """Create ContentUseCase with mocked dependencies."""
        return ContentUseCase(
            metadata_storage=mock_metadata_storage,
            artifact_storage=mock_artifact_storage,
            file_storage=mock_file_storage,
            path_resolver=mock_path_resolver,
        )

    @pytest.fixture
    def sample_content(self) -> ContentMetadata:
        """Create sample content metadata."""
        return ContentMetadata(
            id="content-123",
            type=ContentType.VIDEO,
            original_filename="lecture.mp4",
            source_file="/data/content/content-123/source.mp4",
        )

    # =========================================================================
    # get_content tests
    # =========================================================================

    @pytest.mark.unit
    def test_get_content_success(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
        sample_content: ContentMetadata,
    ) -> None:
        """get_content should return metadata when content exists."""
        mock_metadata_storage.get.return_value = sample_content

        result = usecase.get_content("content-123")

        assert result == sample_content
        mock_metadata_storage.get.assert_called_once_with("content-123")

    @pytest.mark.unit
    def test_get_content_not_found(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """get_content should raise ContentNotFoundError when content doesn't exist."""
        mock_metadata_storage.get.return_value = None

        with pytest.raises(ContentNotFoundError) as exc_info:
            usecase.get_content("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    # =========================================================================
    # rename_content tests
    # =========================================================================

    @pytest.mark.unit
    def test_rename_content_success(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
        sample_content: ContentMetadata,
    ) -> None:
        """rename_content should update filename and save."""
        mock_metadata_storage.get.return_value = sample_content

        result = usecase.rename_content("content-123", "new_name.mp4")

        assert result.original_filename == "new_name.mp4"
        mock_metadata_storage.save.assert_called_once()

    @pytest.mark.unit
    def test_rename_content_not_found(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """rename_content should raise ContentNotFoundError."""
        mock_metadata_storage.get.return_value = None

        with pytest.raises(ContentNotFoundError):
            usecase.rename_content("nonexistent", "new_name.mp4")

    @pytest.mark.unit
    def test_rename_content_updates_timestamp(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
        sample_content: ContentMetadata,
    ) -> None:
        """rename_content should update updated_at timestamp."""
        original_time = sample_content.updated_at
        mock_metadata_storage.get.return_value = sample_content

        result = usecase.rename_content("content-123", "new_name.mp4")

        assert result.updated_at >= original_time

    # =========================================================================
    # delete_content tests
    # =========================================================================

    @pytest.mark.unit
    def test_delete_content_success(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
        mock_artifact_storage: MagicMock,
        mock_file_storage: MagicMock,
        mock_path_resolver: MagicMock,
    ) -> None:
        """delete_content should delete metadata and cleanup artifacts."""
        mock_metadata_storage.exists.return_value = True
        mock_metadata_storage.delete.return_value = True

        result = usecase.delete_content("content-123")

        assert result is True
        mock_metadata_storage.delete.assert_called_once_with("content-123")
        mock_artifact_storage.remove_content.assert_called_once_with("content-123", delete_files=True)
        mock_path_resolver.get_content_dir.assert_called_once_with("content-123")
        mock_file_storage.remove_dir.assert_called_once_with("/data/content/content-123")

    @pytest.mark.unit
    def test_delete_content_not_found(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """delete_content should return False when content doesn't exist."""
        mock_metadata_storage.exists.return_value = False

        result = usecase.delete_content("nonexistent")

        assert result is False
        mock_metadata_storage.delete.assert_not_called()

    @pytest.mark.unit
    def test_delete_content_artifact_cleanup_failure(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
        mock_artifact_storage: MagicMock,
        mock_file_storage: MagicMock,
        mock_path_resolver: MagicMock,
    ) -> None:
        """delete_content should succeed even if artifact cleanup fails."""
        mock_metadata_storage.exists.return_value = True
        mock_metadata_storage.delete.return_value = True
        mock_artifact_storage.remove_content.side_effect = RuntimeError("Cleanup failed")

        result = usecase.delete_content("content-123")

        # Should still return True because metadata deletion succeeded
        assert result is True
        mock_path_resolver.get_content_dir.assert_called_once_with("content-123")
        mock_file_storage.remove_dir.assert_called_once_with("/data/content/content-123")

    # =========================================================================
    # update_feature_status tests
    # =========================================================================

    @pytest.mark.unit
    def test_update_feature_status(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
        sample_content: ContentMetadata,
    ) -> None:
        """update_feature_status should update status and save."""
        mock_metadata_storage.get.return_value = sample_content

        result = usecase.update_feature_status("content-123", "subtitle", "processing", job_id="job-789")

        assert result.subtitle_status == "processing"
        assert result.subtitle_job_id == "job-789"
        mock_metadata_storage.save.assert_called_once()

    @pytest.mark.unit
    def test_update_feature_status_not_found(
        self,
        usecase: ContentUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """update_feature_status should raise ContentNotFoundError."""
        mock_metadata_storage.get.return_value = None

        with pytest.raises(ContentNotFoundError):
            usecase.update_feature_status("nonexistent", "subtitle", "processing")
