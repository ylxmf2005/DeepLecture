import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
from unittest import mock

import pytest

from deeplecture.transcription.voiceover import (
    SyncSegment,
    SubtitleSegment,
    SubtitleVoiceoverGenerator,
)


class _DummyTTS:
    """Minimal TTS stub; synthesize is never called in these unit tests."""

    file_extension = ".wav"

    def synthesize(self, text: str) -> bytes:  # pragma: no cover - not used here
        return b""


def _make_generator(silence_threshold: float = 1.0, max_speed: float = 2.5) -> SubtitleVoiceoverGenerator:
    return SubtitleVoiceoverGenerator(
        tts=_DummyTTS(),
        config={
            "tts": {"sample_rate": 16000},
            "voiceover": {
                "silence_threshold": silence_threshold,
                "max_speed_factor": max_speed,
            },
        },
    )


def _install_audio_stubs(
    gen: SubtitleVoiceoverGenerator,
    monkeypatch: pytest.MonkeyPatch,
    durations: Dict[str, float],
    pad_delta: float = 0.0,
    speed_delta: float = 0.0,
) -> Tuple[List[Tuple], List[Tuple], List[Tuple]]:
    """
    Replace ffmpeg-dependent helpers with cheap fakes backed by a duration map.
    """
    pad_calls: List[Tuple] = []
    speed_calls: List[Tuple] = []
    silence_calls: List[Tuple] = []

    def fake_get(audio_path: str) -> float:
        return durations.get(audio_path, 0.0)

    def fake_pad(input_file: str, output_file: str, target_duration: float, work_dir: str) -> None:
        durations[output_file] = target_duration + pad_delta
        Path(output_file).touch()
        pad_calls.append((input_file, output_file, target_duration))

    def fake_speed(input_file: str, output_file: str, speed: float, target_duration: float, work_dir: str) -> None:
        durations[output_file] = target_duration + speed_delta
        Path(output_file).touch()
        speed_calls.append((input_file, output_file, speed, target_duration))

    def fake_silence(output_file: str, duration: float) -> None:
        durations[output_file] = max(0.0, duration)
        Path(output_file).touch()
        silence_calls.append((output_file, duration))

    monkeypatch.setattr(gen, "_get_audio_duration", fake_get)
    monkeypatch.setattr(gen, "_pad_audio_to_duration", fake_pad)
    monkeypatch.setattr(gen, "_speed_up_audio", fake_speed)
    monkeypatch.setattr(gen, "_generate_silence_wav", fake_silence)
    return pad_calls, speed_calls, silence_calls


# ---------------------------------------------------------------------------
# _build_aligned_segments
# ---------------------------------------------------------------------------


def test_build_aligned_segments_large_gap_speed_calculated(monkeypatch, tmp_path):
    """Large gap triggers video speed-up; speed is calculated from actual durations."""
    gen = _make_generator(silence_threshold=1.0, max_speed=2.5)
    segments = [
        SubtitleSegment(0, 0.0, 1.0, "a"),
        SubtitleSegment(1, 5.0, 6.0, "b"),
    ]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    for idx, dur in enumerate([1.0, 1.0], start=1):
        path = seg_dir / f"subtitle_{idx}.wav"
        path.touch()
        durations[str(path)] = dur

    pad_calls, speed_calls, _ = _install_audio_stubs(gen, monkeypatch, durations)

    audio_files, timings = gen._build_aligned_segments(
        segments, str(seg_dir), video_duration=6.0
    )

    assert len(audio_files) == 2
    assert len(timings) == 2
    # First segment: slot = 5s (0->5), TTS = 1s
    # Gap = 4s > threshold 1s, video speeds up
    # Required speed = 5/1 = 5.0, capped to 2.5
    # Target duration = 5/2.5 = 2.0s
    assert pad_calls[0][2] == pytest.approx(2.0)
    # Speed = src_delta / dst_delta = 5.0 / 2.0 = 2.5
    assert timings[0].speed == pytest.approx(2.5)
    # Second stays at 1x
    assert timings[1].speed == 1.0


def test_build_aligned_segments_gap_equals_threshold_pad(monkeypatch, tmp_path):
    """When gap equals threshold, pad without triggering speed-up."""
    gen = _make_generator(silence_threshold=1.0, max_speed=3.0)
    segments = [
        SubtitleSegment(0, 0.0, 1.0, "a"),
        SubtitleSegment(1, 2.0, 3.0, "b"),
    ]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    for idx, dur in enumerate([1.0, 1.0], start=1):
        path = seg_dir / f"subtitle_{idx}.wav"
        path.touch()
        durations[str(path)] = dur

    pad_calls, speed_calls, _ = _install_audio_stubs(gen, monkeypatch, durations)

    audio_files, timings = gen._build_aligned_segments(
        segments, str(seg_dir), video_duration=3.0
    )

    assert len(audio_files) == 2
    assert len(timings) == 2
    # First slot = 2s (0->2), TTS = 1s, gap = 1s = threshold
    # Should pad, not speed up
    assert pad_calls[0][2] == pytest.approx(2.0)  # slot_duration 2s
    assert speed_calls == []
    assert timings[0].speed == 1.0


def test_build_aligned_segments_tts_too_long_speeds_audio(monkeypatch, tmp_path):
    """When TTS is longer than slot, speed up audio to fit."""
    gen = _make_generator(silence_threshold=1.0)
    segments = [SubtitleSegment(0, 0.0, 1.0, "long")]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    input_wav = seg_dir / "subtitle_1.wav"
    input_wav.touch()
    durations[str(input_wav)] = 1.6

    _, speed_calls, _ = _install_audio_stubs(gen, monkeypatch, durations)

    audio_files, timings = gen._build_aligned_segments(
        segments, str(seg_dir), video_duration=1.0
    )

    assert len(audio_files) == 1
    assert len(speed_calls) == 1
    # speed = raw_dur / slot_duration = 1.6 / 1.0
    assert speed_calls[0][2] == pytest.approx(1.6)
    # dst_end - dst_start should be ~1.0
    dst_dur = timings[0].dst_end - timings[0].dst_start
    assert dst_dur == pytest.approx(1.0)
    assert timings[0].speed == 1.0


def test_build_aligned_segments_skip_tiny_slot(monkeypatch, tmp_path):
    """Tiny slot (<1e-3s) is skipped without polluting output."""
    gen = _make_generator()
    segments = [SubtitleSegment(0, 0.0, 0.0005, "tiny")]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    input_wav = seg_dir / "subtitle_1.wav"
    input_wav.touch()
    durations[str(input_wav)] = 0.0004

    pad_calls, speed_calls, silence_calls = _install_audio_stubs(gen, monkeypatch, durations)

    audio_files, timings = gen._build_aligned_segments(
        segments, str(seg_dir), video_duration=0.0005
    )

    assert audio_files == []
    assert timings == []
    assert pad_calls == []
    assert speed_calls == []
    assert silence_calls == []


def test_build_aligned_segments_leading_and_trailing_silence(monkeypatch, tmp_path):
    """Leading and trailing silence are generated with speed=1.0."""
    gen = _make_generator(silence_threshold=2.0)  # High threshold to avoid speed-up
    segments = [
        SubtitleSegment(0, 0.75, 1.75, "first"),
        SubtitleSegment(1, 3.0, 4.0, "second"),
    ]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    for idx, dur in enumerate([1.0, 1.0], start=1):
        path = seg_dir / f"subtitle_{idx}.wav"
        path.touch()
        durations[str(path)] = dur

    pad_calls, speed_calls, silence_calls = _install_audio_stubs(gen, monkeypatch, durations)

    audio_files, timings = gen._build_aligned_segments(
        segments, str(seg_dir), video_duration=5.0
    )

    assert len(audio_files) == 4  # leading + 2 adjusted + trailing
    assert len(timings) == 4
    assert silence_calls[0][1] == pytest.approx(0.75)  # leading
    assert silence_calls[-1][1] == pytest.approx(1.0)  # trailing
    assert all(t.speed == 1.0 for t in (timings[0], timings[-1]))
    assert speed_calls == []
    assert pad_calls  # padded content segments


# ---------------------------------------------------------------------------
# _speed_up_audio
# ---------------------------------------------------------------------------


def test_speed_up_audio_speed_one_copies_without_ffmpeg(monkeypatch, tmp_path):
    """Speed ≈ 1 copies directly without calling ffmpeg."""
    gen = _make_generator()
    run_calls = []
    copy_calls = []

    monkeypatch.setattr(
        shutil, "copy2", lambda src, dst: copy_calls.append((src, dst))
    )
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: run_calls.append((a, k))
    )

    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    src.touch()

    gen._speed_up_audio(str(src), str(dst), 1.0, 1.0, str(tmp_path))

    assert copy_calls == [(str(src), str(dst))]
    assert run_calls == []


@pytest.mark.parametrize(
    "speed,expected_filter",
    [
        (8.0, "atempo=2.0,atempo=2.0,atempo=2.000000"),
        (0.2, "atempo=0.5,atempo=0.5,atempo=0.800000"),
        (2.0, "atempo=2.000000"),
        (0.5, "atempo=0.500000"),
    ],
)
def test_speed_up_audio_builds_correct_atempo_chain(monkeypatch, tmp_path, speed, expected_filter):
    """Extreme and boundary speeds generate correct atempo chains with target duration."""
    gen = _make_generator()
    run_args = []

    def fake_run(cmd, cwd=None, capture_output=None, check=None, text=None):
        run_args.append(cmd)
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "copy2", lambda *a, **k: (_ for _ in ()).throw(AssertionError("copy not expected")))

    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    src.touch()

    gen._speed_up_audio(str(src), str(dst), speed, 1.234567, str(tmp_path))

    assert len(run_args) == 1
    cmd = run_args[0]
    assert "-filter:a" in cmd
    filter_pos = cmd.index("-filter:a") + 1
    assert cmd[filter_pos] == expected_filter
    t_pos = cmd.index("-t") + 1
    assert cmd[t_pos] == f"{1.234567:.6f}"


# ---------------------------------------------------------------------------
# _parse_srt
# ---------------------------------------------------------------------------


def test_parse_srt_orders_out_of_sequence_and_handles_bom(tmp_path):
    """Out-of-order subtitles with BOM and Windows line endings are parsed correctly."""
    gen = _make_generator()
    srt_path = tmp_path / "sample.srt"
    content = "\ufeff3\r\n00:00:02,000 --> 00:00:03,000\r\nThird\r\n\r\n" \
              "1\r\n00:00:00,500 --> 00:00:01,000\r\nFirst\r\n\r\n" \
              "2\r\n00:00:01,000 --> 00:00:01,500\r\nSecond\r\n"
    srt_path.write_text(content, encoding="utf-8")

    segments = gen._parse_srt(str(srt_path))
    assert len(segments) == 3

    ordered = sorted(segments, key=lambda s: (s.start, s.index))
    assert [s.index for s in ordered] == [1, 2, 3]
    assert [s.start for s in ordered] == [0.5, 1.0, 2.0]
    assert ordered[0].text == "First"


def test_parse_srt_skips_invalid_timestamp_and_empty_text(tmp_path, caplog):
    """Blocks with invalid timestamps or empty text are skipped."""
    gen = _make_generator()
    srt_path = tmp_path / "invalid.srt"
    content = (
        "1\ninvalid timestamp\nBad\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\n\n\n"
        "3\n00:00:02,000 --> 00:00:03,000\nGood line\n"
    )
    srt_path.write_text(content, encoding="utf-8")

    caplog.set_level(logging.WARNING)
    segments = gen._parse_srt(str(srt_path))

    assert len(segments) == 1
    assert segments[0].index == 3
    assert "Skipping block with invalid timestamp" in caplog.text


# ---------------------------------------------------------------------------
# _quantize_speed
# ---------------------------------------------------------------------------


def test_quantize_speed_below_one_returns_one():
    """Speed <= 1.0 returns 1.0 without quantization."""
    gen = _make_generator(max_speed=2.5)
    assert gen._quantize_speed(0.5) == 1.0
    assert gen._quantize_speed(1.0) == 1.0
    assert gen._quantize_speed(0.9) == 1.0


def test_quantize_speed_rounds_to_ceil_bucket():
    """Speed > 1 is quantized to smallest bucket >= speed (ceil strategy)."""
    gen = _make_generator(max_speed=2.5)
    # Buckets: [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]
    assert gen._quantize_speed(1.1) == 1.25  # 1.1 -> 1.25
    assert gen._quantize_speed(1.2) == 1.25  # 1.2 -> 1.25
    assert gen._quantize_speed(1.25) == 1.25  # exact match
    assert gen._quantize_speed(1.26) == 1.5  # 1.26 -> 1.5
    assert gen._quantize_speed(1.5) == 1.5  # exact match
    assert gen._quantize_speed(1.6) == 1.75  # 1.6 -> 1.75
    assert gen._quantize_speed(1.9) == 2.0  # 1.9 -> 2.0
    assert gen._quantize_speed(2.3) == 2.5  # 2.3 -> 2.5


def test_quantize_speed_respects_max_speed_factor():
    """Quantization does not exceed max_speed_factor."""
    gen = _make_generator(max_speed=1.5)
    # Valid buckets: [1.0, 1.25, 1.5]
    assert gen._quantize_speed(2.0) == 1.5  # capped at max
    assert gen._quantize_speed(1.8) == 1.5  # capped at max
    assert gen._quantize_speed(1.6) == 1.5  # capped at max
    assert gen._quantize_speed(1.4) == 1.5  # ceil to 1.5
    assert gen._quantize_speed(1.26) == 1.5  # ceil to 1.5


def test_quantize_speed_exact_bucket_values():
    """Exact bucket values are returned directly."""
    gen = _make_generator(max_speed=2.5)
    for bucket in [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]:
        assert gen._quantize_speed(bucket) == bucket


# ---------------------------------------------------------------------------
# _merge_sync_segments
# ---------------------------------------------------------------------------


def test_merge_sync_segments_empty_list():
    """Empty list returns empty list."""
    gen = _make_generator()
    assert gen._merge_sync_segments([]) == []


def test_merge_sync_segments_single_segment():
    """Single segment is returned as-is."""
    gen = _make_generator()
    segments = [SyncSegment(dst_start=0.0, dst_end=1.0, src_start=0.0, src_end=1.0, speed=1.0)]
    result = gen._merge_sync_segments(segments)
    assert len(result) == 1
    assert result[0] == segments[0]


def test_merge_sync_segments_adjacent_same_speed():
    """Adjacent segments with same speed are merged."""
    gen = _make_generator()
    segments = [
        SyncSegment(dst_start=0.0, dst_end=1.0, src_start=0.0, src_end=1.5, speed=1.5),
        SyncSegment(dst_start=1.0, dst_end=2.0, src_start=1.5, src_end=3.0, speed=1.5),
        SyncSegment(dst_start=2.0, dst_end=3.0, src_start=3.0, src_end=4.5, speed=1.5),
    ]
    result = gen._merge_sync_segments(segments)

    assert len(result) == 1
    assert result[0].src_start == 0.0
    assert result[0].src_end == 4.5
    assert result[0].dst_start == 0.0
    assert result[0].dst_end == 3.0
    assert result[0].speed == 1.5


def test_merge_sync_segments_different_speeds_not_merged():
    """Segments with different speeds are not merged."""
    gen = _make_generator()
    segments = [
        SyncSegment(dst_start=0.0, dst_end=1.0, src_start=0.0, src_end=1.0, speed=1.0),
        SyncSegment(dst_start=1.0, dst_end=1.5, src_start=1.0, src_end=2.0, speed=2.0),
        SyncSegment(dst_start=1.5, dst_end=2.5, src_start=2.0, src_end=3.0, speed=1.0),
    ]
    result = gen._merge_sync_segments(segments)

    assert len(result) == 3
    assert result[0].speed == 1.0
    assert result[1].speed == 2.0
    assert result[2].speed == 1.0


def test_merge_sync_segments_non_contiguous_not_merged():
    """Non-contiguous segments (even with same speed) are not merged."""
    gen = _make_generator()
    segments = [
        SyncSegment(dst_start=0.0, dst_end=1.0, src_start=0.0, src_end=1.5, speed=1.5),
        SyncSegment(dst_start=1.5, dst_end=2.5, src_start=2.0, src_end=3.5, speed=1.5),  # gap
    ]
    result = gen._merge_sync_segments(segments)

    assert len(result) == 2


def test_merge_sync_segments_mixed_scenario():
    """Mixed scenario: some merged, some kept."""
    gen = _make_generator()
    segments = [
        SyncSegment(dst_start=0.0, dst_end=1.0, src_start=0.0, src_end=1.0, speed=1.0),  # keep
        SyncSegment(dst_start=1.0, dst_end=2.0, src_start=1.0, src_end=2.0, speed=1.0),  # merge
        SyncSegment(dst_start=2.0, dst_end=2.5, src_start=2.0, src_end=3.0, speed=2.0),  # new
        SyncSegment(dst_start=2.5, dst_end=3.0, src_start=3.0, src_end=4.0, speed=2.0),  # merge
        SyncSegment(dst_start=3.0, dst_end=4.0, src_start=4.0, src_end=5.0, speed=1.0),  # new
    ]
    result = gen._merge_sync_segments(segments)

    assert len(result) == 3
    # First merged: 0-2s src at 1.0x
    assert result[0].src_start == 0.0
    assert result[0].src_end == 2.0
    assert result[0].dst_end == 2.0
    assert result[0].speed == 1.0
    # Second merged: 2-4s src at 2.0x
    assert result[1].src_start == 2.0
    assert result[1].src_end == 4.0
    assert result[1].speed == 2.0
    # Third: 4-5s src at 1.0x
    assert result[2].src_start == 4.0
    assert result[2].src_end == 5.0
    assert result[2].speed == 1.0


def test_merge_sync_segments_large_reduction(caplog):
    """Large merge produces info log."""
    gen = _make_generator()
    caplog.set_level(logging.INFO)
    # Simulate 100 consecutive 1x speed segments
    segments = [
        SyncSegment(dst_start=i * 1.0, dst_end=(i + 1) * 1.0,
                    src_start=i * 1.0, src_end=(i + 1) * 1.0, speed=1.0)
        for i in range(100)
    ]
    result = gen._merge_sync_segments(segments)

    assert len(result) == 1
    assert result[0].src_start == 0.0
    assert result[0].src_end == 100.0
    assert "Merged 100 sync segments into 1" in caplog.text
    assert "99.0% reduction" in caplog.text
