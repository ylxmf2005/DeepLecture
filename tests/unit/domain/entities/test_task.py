"""Unit tests for Task entity."""

import pytest

from deeplecture.domain.entities.task import Task, TaskStatus


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    @pytest.mark.unit
    def test_is_terminal_for_ready(self) -> None:
        """READY status should be terminal."""
        assert TaskStatus.READY.is_terminal() is True

    @pytest.mark.unit
    def test_is_terminal_for_error(self) -> None:
        """ERROR status should be terminal."""
        assert TaskStatus.ERROR.is_terminal() is True

    @pytest.mark.unit
    def test_is_terminal_for_pending(self) -> None:
        """PENDING status should not be terminal."""
        assert TaskStatus.PENDING.is_terminal() is False

    @pytest.mark.unit
    def test_is_terminal_for_processing(self) -> None:
        """PROCESSING status should not be terminal."""
        assert TaskStatus.PROCESSING.is_terminal() is False

    @pytest.mark.unit
    def test_status_values(self) -> None:
        """Verify all status string values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.READY.value == "ready"
        assert TaskStatus.ERROR.value == "error"


class TestTask:
    """Tests for Task entity."""

    @pytest.fixture
    def sample_task(self) -> Task:
        """Create a sample task for testing."""
        return Task(
            id="task-123",
            type="subtitle",
            content_id="content-456",
        )

    @pytest.mark.unit
    def test_default_status_is_pending(self, sample_task: Task) -> None:
        """New tasks should default to PENDING status."""
        assert sample_task.status == TaskStatus.PENDING

    @pytest.mark.unit
    def test_default_progress_is_zero(self, sample_task: Task) -> None:
        """New tasks should have zero progress."""
        assert sample_task.progress == 0

    @pytest.mark.unit
    def test_is_pending(self, sample_task: Task) -> None:
        """is_pending should return True for PENDING status."""
        assert sample_task.is_pending() is True
        assert sample_task.is_processing() is False

    @pytest.mark.unit
    def test_is_processing(self) -> None:
        """is_processing should return True for PROCESSING status."""
        task = Task(
            id="t1",
            type="test",
            content_id="c1",
            status=TaskStatus.PROCESSING,
        )
        assert task.is_processing() is True
        assert task.is_pending() is False

    @pytest.mark.unit
    def test_is_ready(self) -> None:
        """is_ready should return True for READY status."""
        task = Task(
            id="t1",
            type="test",
            content_id="c1",
            status=TaskStatus.READY,
        )
        assert task.is_ready() is True
        assert task.is_terminal() is True

    @pytest.mark.unit
    def test_is_error(self) -> None:
        """is_error should return True for ERROR status."""
        task = Task(
            id="t1",
            type="test",
            content_id="c1",
            status=TaskStatus.ERROR,
            error="Something went wrong",
        )
        assert task.is_error() is True
        assert task.is_terminal() is True
        assert task.error == "Something went wrong"

    @pytest.mark.unit
    def test_metadata_default_empty(self, sample_task: Task) -> None:
        """Metadata should default to empty dict."""
        assert sample_task.metadata == {}

    @pytest.mark.unit
    def test_task_with_metadata(self) -> None:
        """Task should accept custom metadata."""
        task = Task(
            id="t1",
            type="test",
            content_id="c1",
            metadata={"key": "value", "count": 42},
        )
        assert task.metadata["key"] == "value"
        assert task.metadata["count"] == 42
