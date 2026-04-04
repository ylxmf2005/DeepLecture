"""Task stream endpoint integration tests.

Tests SSE stream contract: content-type, cache headers, retry frame, and event IDs.
Uses a minimal Flask app with only the task blueprint to avoid full DI dependency.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from deeplecture.presentation.api.routes.task import bp as task_bp


@pytest.fixture
def minimal_app():
    """Create a minimal Flask app with only the task blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(task_bp, url_prefix="/api/task")
    return app


@pytest.fixture
def mock_container():
    """Mock the DI container with minimal task manager and event publisher."""
    container = MagicMock()
    container.task_manager.get_tasks_by_content.return_value = []
    container.content_usecase.get_content.side_effect = Exception("no content")

    # Mock event_publisher.stream to yield retry frame then a keepalive
    def fake_stream(_content_id, *, initial_events_factory, retry_ms, **_kwargs):
        yield f"retry: {retry_ms}\n\n"
        # Emit initial events if factory provided
        if initial_events_factory:
            for _evt in initial_events_factory():
                yield 'id: 1\ndata: {"event": "initial"}\n\n'
        yield ": keepalive\n\n"

    container.event_publisher.stream.side_effect = fake_stream
    return container


@pytest.fixture
def client(minimal_app, mock_container):
    """Create test client with mocked container."""
    with (
        patch("deeplecture.presentation.api.routes.task.get_container", return_value=mock_container),
        patch("deeplecture.presentation.api.routes.task._reconcile_stale_tasks_on_connect"),
        minimal_app.test_client() as c,
    ):
        yield c


class TestTaskStreamEndpoint:
    """Test /api/task/stream/<content_id> SSE endpoint."""

    def test_stream_returns_event_stream_content_type(self, client) -> None:
        response = client.get("/api/task/stream/test_content_123")
        assert response.content_type.startswith("text/event-stream")

    def test_stream_includes_no_cache_headers(self, client) -> None:
        response = client.get("/api/task/stream/test_content_123")
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("X-Accel-Buffering") == "no"

    def test_stream_first_frame_is_retry(self, client) -> None:
        """First SSE frame should be retry: <ms>."""
        response = client.get("/api/task/stream/test_content_123")
        data = b""
        for chunk in response.response:
            data += chunk if isinstance(chunk, bytes) else chunk.encode()
            if len(data) > 50:
                break

        text = data.decode("utf-8")
        lines = text.strip().split("\n")
        assert any(
            line.startswith("retry:") for line in lines
        ), f"Expected retry: frame in SSE stream, got: {text[:200]}"

    def test_stream_initial_events_have_ids(self, client, mock_container) -> None:
        """Initial snapshot events should have id: fields."""
        # Make the factory return one task so initial events are emitted
        mock_task = MagicMock()
        mock_task.id = "t1"
        mock_task.type = "subtitle_generation"
        mock_task.content_id = "test_content_123"
        mock_task.status = "pending"
        mock_task.progress = 0
        mock_task.error = None
        mock_task.metadata = {}
        mock_task.created_at = None
        mock_task.updated_at = None
        mock_container.task_manager.get_tasks_by_content.return_value = [mock_task]

        response = client.get("/api/task/stream/test_content_123")
        data = b""
        for chunk in response.response:
            data += chunk if isinstance(chunk, bytes) else chunk.encode()
            if len(data) > 300:
                break

        text = data.decode("utf-8")
        assert "id:" in text or "id: " in text, f"Expected id: field in SSE events, got: {text[:300]}"

    def test_stream_serializes_task_metadata_payload(self, client, mock_container) -> None:
        """Initial task snapshots should preserve metadata for clients."""
        mock_task = MagicMock()
        mock_task.id = "t1"
        mock_task.type = "subtitle_generation"
        mock_task.content_id = "test_content_123"
        mock_task.status = "ready"
        mock_task.progress = 100
        mock_task.error = None
        mock_task.metadata = {
            "language": "auto",
            "resolved_language": "ja",
            "detected_source_language": "ja",
        }
        mock_task.created_at = None
        mock_task.updated_at = None
        mock_container.task_manager.get_tasks_by_content.return_value = [mock_task]

        response = client.get("/api/task/content/test_content_123")

        assert response.status_code == 200
        task = response.json["data"]["tasks"][0]
        assert task["metadata"]["language"] == "auto"
        assert task["metadata"]["resolved_language"] == "ja"
        assert task["metadata"]["detected_source_language"] == "ja"
