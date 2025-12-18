"""Video processing protocol - abstraction for video I/O operations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VideoProcessorProtocol(Protocol):
    def build_still_segment(self, image_path: str, duration: float, output_path: str) -> None: ...

    def concat_segments(self, segment_paths: list[str], output_path: str) -> None: ...

    def mux_audio(self, video_path: str, audio_path: str, output_path: str) -> None: ...

    def probe_duration(self, path: str) -> float: ...
