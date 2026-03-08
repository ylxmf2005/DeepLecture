"""Integration tests for read-aloud routes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import deeplecture.presentation.api.routes.read_aloud as read_aloud_routes


class _ImmediateThread:
    """Thread stub that executes target synchronously."""

    def __init__(self, *, target=None, args=(), kwargs=None, **_kwargs) -> None:
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        if self._target is not None:
            self._target(*self._args, **self._kwargs)


class _NoopThread:
    """Thread stub that never executes target."""

    def __init__(self, **_kwargs) -> None:
        pass

    def start(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _clear_active_runs() -> None:
    """Ensure active run registry does not leak between tests."""
    read_aloud_routes._ACTIVE_RUNS.clear()
    yield
    read_aloud_routes._ACTIVE_RUNS.clear()


class TestReadAloudAPI:
    @pytest.mark.integration
    def test_stream_uses_session_scoped_channel_and_request(self, client, mock_container: MagicMock) -> None:
        mock_container.event_publisher = MagicMock()

        def _fake_stream(_channel, *, initial_events_factory=None, **_kwargs):
            if initial_events_factory is not None:
                initial_events_factory()
            yield ": keepalive\n\n"

        mock_container.event_publisher.stream.side_effect = _fake_stream
        mock_container.read_aloud_usecase = MagicMock()

        with (
            patch(
                "deeplecture.presentation.api.routes.read_aloud.resolve_models_for_task",
                return_value=(None, "edge-default"),
            ),
            patch(
                "deeplecture.presentation.api.routes.read_aloud.threading.Thread",
                _ImmediateThread,
            ),
        ):
            response = client.get("/api/read-aloud/stream/content123?target_language=en")

        assert response.status_code == 200
        assert response.content_type.startswith("text/event-stream")

        stream_call = mock_container.event_publisher.stream.call_args
        channel = stream_call.args[0]
        assert channel.startswith("read_aloud:content123:")
        session_id = channel.split(":")[-1]

        uc_call = mock_container.read_aloud_usecase.generate_stream.call_args
        req = uc_call.args[0]
        assert req.content_id == "content123"
        assert req.session_id == session_id
        assert req.tts_model == "edge-default"
        assert "stop_event" in uc_call.kwargs

    @pytest.mark.integration
    def test_stream_starts_generation_only_after_initial_events_factory(
        self, client, mock_container: MagicMock
    ) -> None:
        mock_container.event_publisher = MagicMock()
        mock_container.event_publisher.stream.return_value = iter([": keepalive\n\n"])
        mock_container.read_aloud_usecase = MagicMock()

        with (
            patch(
                "deeplecture.presentation.api.routes.read_aloud.resolve_models_for_task",
                return_value=(None, "edge-default"),
            ),
            patch(
                "deeplecture.presentation.api.routes.read_aloud.threading.Thread",
                _ImmediateThread,
            ),
        ):
            response = client.get("/api/read-aloud/stream/content123?target_language=en")

        assert response.status_code == 200
        assert mock_container.read_aloud_usecase.generate_stream.call_count == 0

        stream_call = mock_container.event_publisher.stream.call_args
        initial_events_factory = stream_call.kwargs["initial_events_factory"]
        assert callable(initial_events_factory)
        initial_events = list(initial_events_factory())
        assert initial_events and initial_events[0]["event"] == "read_aloud_session"
        assert mock_container.read_aloud_usecase.generate_stream.call_count == 1

    @pytest.mark.integration
    def test_audio_endpoint_requires_variant_key(self, client, mock_container: MagicMock) -> None:
        mock_container.read_aloud_cache = MagicMock()

        response = client.get("/api/read-aloud/audio/content123/p0_s0")

        assert response.status_code == 400
        assert response.json["success"] is False
        assert "variant_key" in response.json["error"]
        mock_container.read_aloud_cache.load_audio.assert_not_called()

    @pytest.mark.integration
    def test_audio_endpoint_loads_variant_scoped_audio(self, client, mock_container: MagicMock) -> None:
        mock_container.read_aloud_cache = MagicMock()
        mock_container.read_aloud_cache.load_audio.return_value = b"audio-bytes"

        response = client.get("/api/read-aloud/audio/content123/p0_s0?variant_key=variant12345")

        assert response.status_code == 200
        assert response.content_type.startswith("audio/mpeg")
        mock_container.read_aloud_cache.load_audio.assert_called_once_with("content123", "variant12345", "p0_s0")

    @pytest.mark.integration
    def test_cancel_endpoint_cancels_matching_active_session(self, client, mock_container: MagicMock) -> None:
        mock_container.event_publisher = MagicMock()

        def _fake_stream(_channel, *, initial_events_factory=None, **_kwargs):
            if initial_events_factory is not None:
                initial_events_factory()
            yield ": keepalive\n\n"

        mock_container.event_publisher.stream.side_effect = _fake_stream
        mock_container.read_aloud_usecase = MagicMock()

        with (
            patch(
                "deeplecture.presentation.api.routes.read_aloud.resolve_models_for_task",
                return_value=(None, "edge-default"),
            ),
            patch(
                "deeplecture.presentation.api.routes.read_aloud.threading.Thread",
                _NoopThread,
            ),
        ):
            stream_response = client.get("/api/read-aloud/stream/content123")
            assert stream_response.status_code == 200

        stream_call = mock_container.event_publisher.stream.call_args
        channel = stream_call.args[0]
        session_id = channel.split(":")[-1]

        response = client.post(f"/api/read-aloud/cancel/content123?session_id={session_id}")

        assert response.status_code == 200
        assert response.json["success"] is True
        assert response.json["data"]["cancelled"] is True
        assert response.json["data"]["session_id"] == session_id
