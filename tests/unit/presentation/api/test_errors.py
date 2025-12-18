"""Unit tests for API error handling."""

import pytest

from deeplecture.domain.errors import ContentNotFoundError, TaskError


class TestAPIErrors:
    """Tests for API error handling utilities."""

    @pytest.mark.unit
    def test_domain_errors_are_catchable(self) -> None:
        """Domain errors should be catchable as exceptions."""
        with pytest.raises(ContentNotFoundError):
            raise ContentNotFoundError("test-123")

    @pytest.mark.unit
    def test_task_errors_are_catchable(self) -> None:
        """Task errors should be catchable."""
        with pytest.raises(TaskError):
            raise TaskError("Task failed")
