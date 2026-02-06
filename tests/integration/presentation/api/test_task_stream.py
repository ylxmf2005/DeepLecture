"""Task stream endpoint integration tests.

Tests SSE stream snapshot-on-connect and reconciliation behavior.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def flask_app():
    """Create a test Flask app with task routes."""
    from deeplecture.presentation.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(flask_app, test_settings, reset_container):
    """Create a test client with isolated container."""
    with flask_app.test_client() as c:
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
        """After implementation, the first SSE frame should be retry: <ms>."""
        response = client.get("/api/task/stream/test_content_123")
        # Read enough data to get the first frames
        data = b""
        for chunk in response.response:
            data += chunk if isinstance(chunk, bytes) else chunk.encode()
            if len(data) > 100:
                break

        text = data.decode("utf-8")
        # After implementation, first frame should be retry:
        # For now this may fail (expected in TDD red phase)
        lines = text.strip().split("\n")
        assert any(
            line.startswith("retry:") for line in lines
        ), f"Expected retry: frame in SSE stream, got: {text[:200]}"

    def test_stream_initial_events_have_ids(self, client) -> None:
        """After implementation, initial snapshot events should have id: fields."""
        from deeplecture.di import get_container

        container = get_container()

        # Submit a task so there's something in the snapshot
        def noop(_ctx):
            pass

        container.task_manager.submit(
            content_id="test_content_123",
            task_type="subtitle_generation",
            task=noop,
        )

        response = client.get("/api/task/stream/test_content_123")
        data = b""
        for chunk in response.response:
            data += chunk if isinstance(chunk, bytes) else chunk.encode()
            if len(data) > 500:
                break

        text = data.decode("utf-8")
        # Should contain id: fields for initial events
        assert "id:" in text or "id: " in text, f"Expected id: field in SSE events, got: {text[:300]}"
