"""Unit tests for domain errors."""

import pytest

from deeplecture.domain.errors import (
    ContentNotFoundError,
    DomainError,
    InvalidFeatureStatusTransitionError,
    SubtitleError,
    SubtitleNotFoundError,
    TaskError,
    TaskNotFoundError,
    TaskQueueFullError,
    UploadError,
    VideoDownloadError,
)


class TestDomainError:
    """Tests for base DomainError."""

    @pytest.mark.unit
    def test_domain_error_is_exception(self) -> None:
        """DomainError should be a subclass of Exception."""
        assert issubclass(DomainError, Exception)

    @pytest.mark.unit
    def test_domain_error_message(self) -> None:
        """DomainError should store message."""
        error = DomainError("Something went wrong")
        assert str(error) == "Something went wrong"


class TestContentNotFoundError:
    """Tests for ContentNotFoundError."""

    @pytest.mark.unit
    def test_inheritance(self) -> None:
        """ContentNotFoundError should inherit from DomainError."""
        assert issubclass(ContentNotFoundError, DomainError)

    @pytest.mark.unit
    def test_error_message_includes_id(self) -> None:
        """Error message should include content ID."""
        error = ContentNotFoundError("content-123")
        assert "content-123" in str(error)


class TestTaskError:
    """Tests for TaskError and subclasses."""

    @pytest.mark.unit
    def test_task_error_inheritance(self) -> None:
        """TaskError should inherit from DomainError."""
        assert issubclass(TaskError, DomainError)

    @pytest.mark.unit
    def test_task_not_found_error(self) -> None:
        """TaskNotFoundError should include task ID."""
        assert issubclass(TaskNotFoundError, TaskError)
        error = TaskNotFoundError("task-456")
        assert "task-456" in str(error)

    @pytest.mark.unit
    def test_task_queue_full_error(self) -> None:
        """TaskQueueFullError should inherit from TaskError."""
        assert issubclass(TaskQueueFullError, TaskError)


class TestSubtitleError:
    """Tests for SubtitleError and subclasses."""

    @pytest.mark.unit
    def test_subtitle_error_inheritance(self) -> None:
        """SubtitleError should inherit from DomainError."""
        assert issubclass(SubtitleError, DomainError)

    @pytest.mark.unit
    def test_subtitle_not_found_error(self) -> None:
        """SubtitleNotFoundError should inherit from SubtitleError."""
        assert issubclass(SubtitleNotFoundError, SubtitleError)


class TestUploadError:
    """Tests for UploadError and subclasses."""

    @pytest.mark.unit
    def test_upload_error_inheritance(self) -> None:
        """UploadError should inherit from DomainError."""
        assert issubclass(UploadError, DomainError)

    @pytest.mark.unit
    def test_video_download_error(self) -> None:
        """VideoDownloadError should inherit from UploadError."""
        assert issubclass(VideoDownloadError, UploadError)


class TestFeatureError:
    """Tests for feature status errors."""

    @pytest.mark.unit
    def test_invalid_transition_inheritance(self) -> None:
        """InvalidFeatureStatusTransitionError should inherit from DomainError."""
        assert issubclass(InvalidFeatureStatusTransitionError, DomainError)
