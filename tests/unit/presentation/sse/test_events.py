"""SSE event frame format tests.

Verifies that EventPublisher emits correct SSE frames with id: and retry: fields.
"""

from __future__ import annotations

import json

from deeplecture.presentation.sse.events import EventPublisher


class TestSSEFrameFormat:
    """Test SSE wire format compliance."""

    def test_format_sse_includes_id_when_provided(self) -> None:
        pub = EventPublisher()
        frame = pub._format_sse({"event": "progress", "task_id": "t1"}, event_id=42)
        lines = frame.strip().split("\n")
        assert lines[0] == "id: 42"
        assert lines[1].startswith("data: ")

    def test_format_sse_omits_id_when_none(self) -> None:
        pub = EventPublisher()
        frame = pub._format_sse({"event": "progress"})
        assert not frame.startswith("id:")
        assert frame.startswith("data: ")

    def test_format_sse_data_is_valid_json(self) -> None:
        pub = EventPublisher()
        payload = {"event": "completed", "task": {"id": "t1", "status": "ready"}}
        frame = pub._format_sse(payload, event_id=1)
        data_line = next(line for line in frame.strip().split("\n") if line.startswith("data: "))
        json_str = data_line[len("data: ") :]
        parsed = json.loads(json_str)
        assert parsed["event"] == "completed"
        assert parsed["task"]["status"] == "ready"

    def test_frame_ends_with_double_newline(self) -> None:
        pub = EventPublisher()
        frame = pub._format_sse({"event": "test"}, event_id=1)
        assert frame.endswith("\n\n")


class TestSSEStreamRetry:
    """Test retry: frame emission on stream start."""

    def test_stream_emits_retry_frame(self) -> None:
        pub = EventPublisher()
        gen = pub.stream("test_content", timeout=0.1, send_initial=False, retry_ms=3000, max_idle_keepalives=1)
        first_frame = next(gen)
        assert first_frame == "retry: 3000\n\n"

    def test_stream_without_retry_skips_frame(self) -> None:
        pub = EventPublisher()
        gen = pub.stream("test_content", timeout=0.1, send_initial=True, max_idle_keepalives=1)
        first_frame = next(gen)
        # Should be the connected event, not a retry frame
        assert "connected" in first_frame or first_frame == ": keepalive\n\n"

    def test_stream_events_have_monotonic_ids(self) -> None:
        pub = EventPublisher()

        def initial_factory():
            return [
                {"event": "initial", "task": {"id": "t1"}},
                {"event": "initial", "task": {"id": "t2"}},
            ]

        gen = pub.stream(
            "test_content",
            timeout=0.1,
            send_initial=False,
            retry_ms=3000,
            initial_events_factory=initial_factory,
            max_idle_keepalives=1,
        )

        frames = []
        for frame in gen:
            frames.append(frame)
            if len(frames) >= 4:  # retry + 2 initial + 1 keepalive
                break

        # First frame is retry
        assert frames[0].startswith("retry:")

        # Extract ids from initial event frames
        ids = []
        for f in frames[1:]:
            for line in f.strip().split("\n"):
                if line.startswith("id: "):
                    ids.append(int(line[4:]))

        assert len(ids) >= 2
        assert ids == sorted(ids), "IDs should be monotonically increasing"
        assert ids[1] > ids[0], "Each ID should be unique and increasing"
