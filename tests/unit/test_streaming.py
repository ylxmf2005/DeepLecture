from __future__ import annotations

from deeplecture.utils.streaming import stream_video


def test_stream_video_full_file(tmp_path) -> None:
    video_path = tmp_path / "video.bin"
    content = b"0123456789" * 100
    video_path.write_bytes(content)

    chunks = list(stream_video(str(video_path)))
    combined = b"".join(chunks)

    assert combined == content


def test_stream_video_range(tmp_path) -> None:
    video_path = tmp_path / "video.bin"
    content = b"abcdef" * 10
    video_path.write_bytes(content)

    # Read a slice from the middle
    byte1 = 5
    byte2 = 20
    expected = content[byte1 : byte2 + 1]

    chunks = list(stream_video(str(video_path), byte1=byte1, byte2=byte2, chunk_size=4))
    combined = b"".join(chunks)

    assert combined == expected
