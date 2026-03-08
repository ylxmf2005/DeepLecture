"""Unit tests for ReadAloudUseCase."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from unittest.mock import ANY, MagicMock

import pytest

from deeplecture.config.settings import ReadAloudConfig
from deeplecture.use_cases.dto.read_aloud import ReadAloudRequest
from deeplecture.use_cases.interfaces.text_filter import FilteredParagraph
from deeplecture.use_cases.read_aloud import ReadAloudUseCase


@pytest.fixture
def usecase_deps() -> dict[str, MagicMock]:
    """Create mocked dependencies for ReadAloudUseCase."""
    note_storage = MagicMock()
    text_filter = MagicMock()
    translator = MagicMock()
    tts_provider = MagicMock()
    cache = MagicMock()
    cache.load_audio.return_value = None
    events = MagicMock()
    events.subscriber_count.return_value = 1

    tts_impl = MagicMock()
    tts_impl.synthesize.return_value = b"mp3-bytes"
    tts_provider.get.return_value = tts_impl
    translator.is_available.return_value = False

    return {
        "note_storage": note_storage,
        "text_filter": text_filter,
        "translator": translator,
        "tts_provider": tts_provider,
        "cache": cache,
        "events": events,
        "tts_impl": tts_impl,
    }


@pytest.fixture
def usecase(usecase_deps: dict[str, MagicMock]) -> ReadAloudUseCase:
    """Create ReadAloudUseCase with mocked dependencies."""
    return ReadAloudUseCase(
        note_storage=usecase_deps["note_storage"],
        text_filter=usecase_deps["text_filter"],
        translation_provider=usecase_deps["translator"],
        tts_provider=usecase_deps["tts_provider"],
        cache=usecase_deps["cache"],
        event_publisher=usecase_deps["events"],
        config=ReadAloudConfig(default_voice="en-US-AriaNeural", tts_model="edge-default"),
    )


class TestReadAloudUseCase:
    """Tests for ReadAloudUseCase.generate_stream()."""

    @pytest.mark.unit
    def test_generate_stream_publishes_session_scoped_events_and_caches_audio(
        self,
        usecase: ReadAloudUseCase,
        usecase_deps: dict[str, MagicMock],
    ) -> None:
        usecase_deps["note_storage"].load.return_value = (
            "# Intro\nHello world.",
            datetime(2026, 3, 3, 10, 30, tzinfo=timezone.utc),
        )
        usecase_deps["text_filter"].filter_to_sentences.return_value = [
            FilteredParagraph(index=0, title="Intro", sentences=["Hello world."])
        ]

        request = ReadAloudRequest(
            content_id="content123",
            session_id="session123",
            target_language="en",
            source_language=None,
            tts_model="edge-default",
            start_paragraph=0,
        )

        usecase.generate_stream(request)

        # Audio cache now includes a deterministic variant key.
        usecase_deps["cache"].save_audio.assert_called_once_with("content123", ANY, "p0_s0", b"mp3-bytes")
        variant_key = usecase_deps["cache"].save_audio.call_args.args[1]
        assert len(variant_key) == 24
        assert all(ch in "0123456789abcdef" for ch in variant_key)

        calls = usecase_deps["events"].publish.call_args_list
        event_types = [c.args[1] for c in calls]
        assert event_types == [
            "read_aloud_meta",
            "paragraph_start",
            "sentence_ready",
            "paragraph_end",
            "read_aloud_complete",
        ]

        first_channel = calls[0].args[0]
        assert first_channel == "read_aloud:content123:session123"
        assert calls[0].args[2]["session_id"] == "session123"
        assert calls[2].args[2]["session_id"] == "session123"
        assert calls[2].args[2]["variant_key"] == variant_key
        assert calls[2].args[2]["cached"] is False
        assert calls[-1].args[2]["session_id"] == "session123"

    @pytest.mark.unit
    def test_generate_stream_uses_cached_audio_without_synthesizing(
        self,
        usecase: ReadAloudUseCase,
        usecase_deps: dict[str, MagicMock],
    ) -> None:
        usecase_deps["note_storage"].load.return_value = ("# Intro\nHello world.", None)
        usecase_deps["text_filter"].filter_to_sentences.return_value = [
            FilteredParagraph(index=0, title="Intro", sentences=["Hello world."])
        ]
        usecase_deps["cache"].load_audio.return_value = b"cached-bytes"

        request = ReadAloudRequest(
            content_id="content123",
            session_id="session123",
            target_language="en",
            source_language=None,
            tts_model="edge-default",
            start_paragraph=0,
        )

        usecase.generate_stream(request)

        usecase_deps["tts_impl"].synthesize.assert_not_called()
        usecase_deps["cache"].save_audio.assert_not_called()

        calls = usecase_deps["events"].publish.call_args_list
        sentence_ready = next(call for call in calls if call.args[1] == "sentence_ready")
        assert sentence_ready.args[2]["cached"] is True

    @pytest.mark.unit
    def test_generate_stream_honors_stop_event_before_processing(
        self,
        usecase: ReadAloudUseCase,
        usecase_deps: dict[str, MagicMock],
    ) -> None:
        stop_event = threading.Event()
        stop_event.set()

        request = ReadAloudRequest(
            content_id="content123",
            session_id="session-stop",
            target_language="en",
            source_language=None,
            tts_model="edge-default",
            start_paragraph=0,
        )

        usecase.generate_stream(request, stop_event=stop_event)

        usecase_deps["note_storage"].load.assert_not_called()
        usecase_deps["cache"].save_audio.assert_not_called()

        usecase_deps["events"].publish.assert_called_once()
        call = usecase_deps["events"].publish.call_args
        assert call.args[1] == "read_aloud_complete"
        assert call.args[2]["cancelled"] is True
        assert call.args[2]["session_id"] == "session-stop"
