"""
Fake implementations of ports for unit testing.

These are in-memory implementations that simulate real adapters
without actual I/O, network calls, or external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from deeplecture.domain.entities import ContentMetadata


# =============================================================================
# FAKE METADATA STORAGE
# =============================================================================


@dataclass
class FakeMetadataStorage:
    """In-memory metadata storage for testing."""

    _data: dict[str, ContentMetadata] = field(default_factory=dict)

    def save(self, metadata: ContentMetadata) -> None:
        self._data[metadata.id] = metadata

    def get(self, content_id: str) -> ContentMetadata | None:
        return self._data.get(content_id)

    def exists(self, content_id: str) -> bool:
        return content_id in self._data

    def list_all(self, include_deleted: bool = False) -> list[ContentMetadata]:
        if include_deleted:
            return list(self._data.values())
        return [m for m in self._data.values() if not getattr(m, "deleted", False)]

    def delete(self, content_id: str) -> bool:
        if content_id in self._data:
            del self._data[content_id]
            return True
        return False


# =============================================================================
# FAKE LLM (aligned with LLMProtocol)
# =============================================================================


@dataclass
class FakeLLM:
    """
    Fake LLM for testing.

    Implements LLMProtocol: complete() and stream().
    """

    responses: list[str] = field(default_factory=list)
    _call_count: int = 0
    _calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Return configured response or default."""
        self._calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                **kwargs,
            }
        )

        if self._call_count < len(self.responses):
            response = self.responses[self._call_count]
            self._call_count += 1
            return response

        self._call_count += 1
        return f"[FAKE LLM RESPONSE #{self._call_count}]"

    def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream configured response as chunks."""
        response = self.complete(prompt, system_prompt=system_prompt, **kwargs)
        for word in response.split():
            yield word + " "


# =============================================================================
# FAKE TTS (aligned with TTSProtocol)
# =============================================================================


@dataclass
class FakeTTS:
    """
    Fake TTS for testing.

    Implements TTSProtocol: synthesize() and synthesize_to_file().
    """

    audio_data: bytes = b"\x00" * 1024  # Minimal fake audio
    _calls: list[dict[str, Any]] = field(default_factory=list)
    should_fail: bool = False
    fail_message: str = "TTS synthesis failed"

    def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        """Return configured audio data."""
        self._calls.append({"text": text, "voice": voice})

        if self.should_fail:
            raise RuntimeError(self.fail_message)

        return self.audio_data

    def synthesize_to_file(
        self,
        text: str,
        output_path: Path,
        *,
        voice: str | None = None,
    ) -> None:
        """Write audio data to file."""
        self._calls.append({"text": text, "output_path": output_path, "voice": voice})

        if self.should_fail:
            raise RuntimeError(self.fail_message)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.audio_data)


# =============================================================================
# FAKE ASR (aligned with ASRProtocol)
# =============================================================================


@dataclass
class FakeASR:
    """
    Fake ASR (Automatic Speech Recognition) for testing.

    Implements ASRProtocol: transcribe() returns list[Segment].
    """

    _calls: list[dict[str, Any]] = field(default_factory=list)
    should_fail: bool = False
    fail_message: str = "Transcription failed"

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str = "en",
    ) -> list:
        """Return list of Segment objects."""
        from deeplecture.domain.entities import Segment

        self._calls.append({"audio_path": audio_path, "language": language})

        if self.should_fail:
            raise RuntimeError(self.fail_message)

        # Return default fake segments
        return [
            Segment(start=0.0, end=2.0, text="This is a fake transcript."),
            Segment(start=2.0, end=4.0, text="For testing purposes only."),
        ]


# =============================================================================
# FAKE EVENT PUBLISHER
# =============================================================================


@dataclass
class FakeEventPublisher:
    """
    Fake event publisher for testing.

    Captures all published events for assertion.
    """

    events: list[dict[str, Any]] = field(default_factory=list)

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Capture published event."""
        self.events.append({"type": event_type, "data": data})

    def subscribe(self, subscriber_id: str) -> Any:
        """Return a mock subscription."""
        return iter([])

    def unsubscribe(self, subscriber_id: str) -> None:
        """No-op unsubscribe."""

    def clear(self) -> None:
        """Clear captured events."""
        self.events.clear()


# =============================================================================
# FAKE ARTIFACT STORAGE
# =============================================================================


@dataclass
class FakeArtifactStorage:
    """Fake artifact storage for testing."""

    _removed: list[str] = field(default_factory=list)

    def remove_content(self, content_id: str, *, delete_files: bool = True) -> None:
        """Track removed content."""
        self._removed.append(content_id)
