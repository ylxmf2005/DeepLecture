from __future__ import annotations

from typing import Iterable, Optional


def stream_video(
    video_path: str,
    byte1: int = 0,
    byte2: Optional[int] = None,
    *,
    chunk_size: int = 1024 * 1024,
) -> Iterable[bytes]:
    """
    Stream a video file in chunks for HTTP range responses.

    This helper is intentionally dumb: it only knows how to read a file
    from disk and yield byte chunks. Range parsing and HTTP headers are
    handled at the route layer.
    """
    with open(video_path, "rb") as video:
        video.seek(byte1)
        remaining = byte2 - byte1 + 1 if byte2 is not None else None

        while True:
            size = chunk_size if remaining is None else min(chunk_size, remaining)
            data = video.read(size)
            if not data:
                break

            if remaining is not None:
                remaining -= len(data)

            yield data

