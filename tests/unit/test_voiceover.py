import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
from unittest import mock

import pytest

from deeplecture.transcription.voiceover import (
    SegmentTiming,
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
# _build_aligned_segment_files
# ---------------------------------------------------------------------------


def test_build_aligned_segment_files_large_gap_speed_capped(monkeypatch, tmp_path):
    """大 gap 触发视频变速，speed 被 max_speed_factor 封顶并补足目标时长。"""
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

    audio_files, timings = gen._build_aligned_segment_files(
        segments, str(seg_dir), video_duration=6.0
    )

    assert len(audio_files) == 2
    assert len(timings) == 2
    # First segment hits max_speed_factor=2.5, target duration = 5/2.5 = 2.0
    assert pad_calls[0][2] == pytest.approx(2.0)
    assert timings[0].speed == pytest.approx(2.5)
    assert timings[0].out_duration == pytest.approx(2.0)
    # Second stays at 1x
    assert speed_calls == []
    assert timings[1].speed == 1.0


def test_build_aligned_segment_files_gap_equals_threshold_pad(monkeypatch, tmp_path):
    """gap 恰等于阈值时走补 pad 分支，不触发变速。"""
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

    audio_files, timings = gen._build_aligned_segment_files(
        segments, str(seg_dir), video_duration=3.0
    )

    assert len(audio_files) == 2
    assert len(timings) == 2
    assert pad_calls[0][2] == pytest.approx(2.0)  # slot_duration 2s
    assert speed_calls == []
    assert timings[0].speed == 1.0


def test_build_aligned_segment_files_tts_too_long_speeds_audio(monkeypatch, tmp_path):
    """TTS 长于槽位时触发音频加速并匹配槽位时长。"""
    gen = _make_generator(silence_threshold=1.0)
    segments = [SubtitleSegment(0, 0.0, 1.0, "long")]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    input_wav = seg_dir / "subtitle_1.wav"
    input_wav.touch()
    durations[str(input_wav)] = 1.6

    _, speed_calls, _ = _install_audio_stubs(gen, monkeypatch, durations)

    audio_files, timings = gen._build_aligned_segment_files(
        segments, str(seg_dir), video_duration=1.0
    )

    assert len(audio_files) == 1
    assert len(speed_calls) == 1
    # speed = raw_dur / slot_duration
    assert speed_calls[0][2] == pytest.approx(1.6)
    assert timings[0].out_duration == pytest.approx(1.0)
    assert timings[0].speed == 1.0


def test_build_aligned_segment_files_skip_tiny_slot(monkeypatch, tmp_path):
    """slot_duration<1e-3 的字幕被跳过且不会污染输出时间线。"""
    gen = _make_generator()
    segments = [SubtitleSegment(0, 0.0, 0.0005, "tiny")]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    input_wav = seg_dir / "subtitle_1.wav"
    input_wav.touch()
    durations[str(input_wav)] = 0.0004

    pad_calls, speed_calls, silence_calls = _install_audio_stubs(gen, monkeypatch, durations)

    audio_files, timings = gen._build_aligned_segment_files(
        segments, str(seg_dir), video_duration=0.0005
    )

    assert audio_files == []
    assert timings == []
    assert pad_calls == []
    assert speed_calls == []
    assert silence_calls == []


def test_build_aligned_segment_files_no_trailing_when_video_unknown(monkeypatch, tmp_path, caplog):
    """video_duration=None 时不补尾静音并记录警告。"""
    gen = _make_generator()
    segments = [SubtitleSegment(0, 0.0, 1.0, "a")]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    input_wav = seg_dir / "subtitle_1.wav"
    input_wav.touch()
    durations[str(input_wav)] = 1.0

    _install_audio_stubs(gen, monkeypatch, durations)

    caplog.set_level(logging.WARNING)
    audio_files, timings = gen._build_aligned_segment_files(
        segments, str(seg_dir), video_duration=None
    )

    assert len(audio_files) == 1
    assert len(timings) == 1
    assert "Could not determine video duration" in caplog.text


def test_build_aligned_segment_files_video_shorter_than_subtitles(monkeypatch, tmp_path):
    """视频总长短于最后字幕时不追加尾静音。"""
    gen = _make_generator()
    segments = [SubtitleSegment(0, 0.0, 3.5, "a")]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    input_wav = seg_dir / "subtitle_1.wav"
    input_wav.touch()
    durations[str(input_wav)] = 3.5

    _install_audio_stubs(gen, monkeypatch, durations)

    audio_files, timings = gen._build_aligned_segment_files(
        segments, str(seg_dir), video_duration=3.0
    )

    assert len(audio_files) == 1  # 没有 silence_tail
    assert timings[-1].src_end == pytest.approx(3.5)


def test_build_aligned_segment_files_leading_and_trailing_silence(monkeypatch, tmp_path):
    """首尾静音都会生成，各自保持 1x 速度。"""
    gen = _make_generator(silence_threshold=2.0)  # 避免中间被判定为大 gap
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

    audio_files, timings = gen._build_aligned_segment_files(
        segments, str(seg_dir), video_duration=5.0
    )

    assert len(audio_files) == 4  # leading + 2 adjusted + trailing
    assert len(timings) == 4
    assert silence_calls[0][1] == pytest.approx(0.75)  # leading
    assert silence_calls[-1][1] == pytest.approx(1.0)  # trailing
    assert all(t.speed == 1.0 for t in (timings[0], timings[-1]))
    assert speed_calls == []
    assert pad_calls  # 调整了正文


def test_build_aligned_segment_files_timing_diff_warning(monkeypatch, tmp_path, caplog):
    """音频总长与预期视频时长差值>0.02 时抛出警告。"""
    gen = _make_generator()
    segments = [SubtitleSegment(0, 0.0, 2.0, "drift")]
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    durations: Dict[str, float] = {}
    input_wav = seg_dir / "subtitle_1.wav"
    input_wav.touch()
    durations[str(input_wav)] = 2.0

    _install_audio_stubs(gen, monkeypatch, durations, pad_delta=0.2)  # 制造 0.2s 漂移

    caplog.set_level(logging.WARNING)
    gen._build_aligned_segment_files(segments, str(seg_dir), video_duration=2.0)

    assert "Timing mismatch detected" in caplog.text


# ---------------------------------------------------------------------------
# _speed_up_audio
# ---------------------------------------------------------------------------


def test_speed_up_audio_speed_one_copies_without_ffmpeg(monkeypatch, tmp_path):
    """speed≈1 直接 copy，不调用 ffmpeg。"""
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
    """极值与边界 speed 生成正确的 atempo 链并带上目标时长。"""
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
    """乱序字幕（含 BOM、Windows 换行）被正确解析，start/index 可供后续排序。"""
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
    """无效时间戳或空文本的块会被跳过，不影响后续解析。"""
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
    assert "Skipping subtitle block with invalid timestamp" in caplog.text


# ---------------------------------------------------------------------------
# _build_video_speed_filter
# ---------------------------------------------------------------------------


def test_build_video_speed_filter_mixed_speeds():
    """混合 speed>1 与 1.0 生成正确的 setpts 与 concat 数量。"""
    gen = _make_generator()
    timings = [
        SegmentTiming(0.0, 1.0, 0.0, 1.0, speed=1.0),
        SegmentTiming(1.0, 3.0, 1.0, 2.0, speed=2.0),
        SegmentTiming(3.0, 5.0, 3.0, 1.666, speed=1.2),
    ]

    filter_complex, n = gen._build_video_speed_filter(timings)

    assert n == 3
    assert "trim=start=0.000000:end=1.000000,setpts=PTS-STARTPTS[seg0]" in filter_complex
    assert "trim=start=1.000000:end=3.000000,setpts=PTS-STARTPTS,setpts=PTS/2.000000[seg1]" in filter_complex
    assert "trim=start=3.000000:end=5.000000,setpts=PTS-STARTPTS,setpts=PTS/1.200000[seg2]" in filter_complex
    assert "concat=n=3:v=1:a=0[vout]" in filter_complex


def test_build_video_speed_filter_all_unity_speed():
    """全部 speed=1.0 时不添加额外 setpts 分量。"""
    gen = _make_generator()
    timings = [
        SegmentTiming(0.0, 1.0, 0.0, 1.0, speed=1.0),
        SegmentTiming(1.0, 2.0, 1.0, 1.0, speed=1.0),
    ]

    filter_complex, n = gen._build_video_speed_filter(timings)

    assert n == 2
    assert "/1.000000" not in filter_complex
    assert "concat=n=2:v=1:a=0[vout]" in filter_complex


# ---------------------------------------------------------------------------
# _quantize_speed
# ---------------------------------------------------------------------------


def test_quantize_speed_below_one_returns_one():
    """speed<=1.0 直接返回 1.0，不触发量化。"""
    gen = _make_generator(max_speed=2.5)
    assert gen._quantize_speed(0.5) == 1.0
    assert gen._quantize_speed(1.0) == 1.0
    assert gen._quantize_speed(0.9) == 1.0


def test_quantize_speed_rounds_to_ceil_bucket():
    """speed>1 时量化到最小的 >= speed 的 bucket (ceil 策略)。"""
    gen = _make_generator(max_speed=2.5)
    # Buckets: [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]
    # Ceil strategy: find smallest bucket >= speed
    assert gen._quantize_speed(1.1) == 1.25  # 1.1 -> smallest bucket >= 1.1 is 1.25
    assert gen._quantize_speed(1.2) == 1.25  # 1.2 -> 1.25
    assert gen._quantize_speed(1.25) == 1.25  # exact match
    assert gen._quantize_speed(1.26) == 1.5  # 1.26 -> 1.5
    assert gen._quantize_speed(1.5) == 1.5  # exact match
    assert gen._quantize_speed(1.6) == 1.75  # 1.6 -> 1.75
    assert gen._quantize_speed(1.9) == 2.0  # 1.9 -> 2.0
    assert gen._quantize_speed(2.3) == 2.5  # 2.3 -> 2.5


def test_quantize_speed_respects_max_speed_factor():
    """量化结果不超过 max_speed_factor，超出时使用最大有效桶。"""
    gen = _make_generator(max_speed=1.5)
    # With max_speed=1.5, valid buckets are [1.0, 1.25, 1.5]
    # For speeds > max, we use the largest valid bucket (1.5)
    assert gen._quantize_speed(2.0) == 1.5  # capped at max
    assert gen._quantize_speed(1.8) == 1.5  # capped at max
    assert gen._quantize_speed(1.6) == 1.5  # capped at max (no bucket >= 1.6 within limit)
    assert gen._quantize_speed(1.4) == 1.5  # ceil to 1.5
    assert gen._quantize_speed(1.26) == 1.5  # ceil to 1.5


def test_quantize_speed_exact_bucket_values():
    """精确的 bucket 值直接返回。"""
    gen = _make_generator(max_speed=2.5)
    for bucket in [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]:
        assert gen._quantize_speed(bucket) == bucket


# ---------------------------------------------------------------------------
# _merge_segment_timings
# ---------------------------------------------------------------------------


def test_merge_segment_timings_empty_list():
    """空列表返回空列表。"""
    gen = _make_generator()
    assert gen._merge_segment_timings([]) == []


def test_merge_segment_timings_single_segment():
    """单个 segment 原样返回。"""
    gen = _make_generator()
    timings = [SegmentTiming(0.0, 1.0, 0.0, 1.0, speed=1.0)]
    result = gen._merge_segment_timings(timings)
    assert len(result) == 1
    assert result[0] == timings[0]


def test_merge_segment_timings_adjacent_same_speed():
    """相邻同速 segment 被合并。"""
    gen = _make_generator()
    timings = [
        SegmentTiming(0.0, 1.0, 0.0, 1.0, speed=1.5),
        SegmentTiming(1.0, 2.0, 1.0, 1.0, speed=1.5),
        SegmentTiming(2.0, 3.0, 2.0, 1.0, speed=1.5),
    ]
    result = gen._merge_segment_timings(timings)

    assert len(result) == 1
    assert result[0].src_start == 0.0
    assert result[0].src_end == 3.0
    assert result[0].out_start == 0.0
    assert result[0].out_duration == pytest.approx(3.0)
    assert result[0].speed == 1.5


def test_merge_segment_timings_different_speeds_not_merged():
    """不同速度的 segment 不会被合并。"""
    gen = _make_generator()
    timings = [
        SegmentTiming(0.0, 1.0, 0.0, 1.0, speed=1.0),
        SegmentTiming(1.0, 2.0, 1.0, 0.5, speed=2.0),
        SegmentTiming(2.0, 3.0, 1.5, 1.0, speed=1.0),
    ]
    result = gen._merge_segment_timings(timings)

    assert len(result) == 3
    assert result[0].speed == 1.0
    assert result[1].speed == 2.0
    assert result[2].speed == 1.0


def test_merge_segment_timings_non_contiguous_not_merged():
    """非连续的 segment（即使速度相同）不会被合并。"""
    gen = _make_generator()
    timings = [
        SegmentTiming(0.0, 1.0, 0.0, 1.0, speed=1.5),
        SegmentTiming(1.5, 2.5, 1.0, 1.0, speed=1.5),  # gap of 0.5s
    ]
    result = gen._merge_segment_timings(timings)

    assert len(result) == 2


def test_merge_segment_timings_mixed_scenario():
    """混合场景：部分合并，部分保留。"""
    gen = _make_generator()
    timings = [
        SegmentTiming(0.0, 1.0, 0.0, 1.0, speed=1.0),     # keep
        SegmentTiming(1.0, 2.0, 1.0, 1.0, speed=1.0),     # merge with prev
        SegmentTiming(2.0, 3.0, 2.0, 0.5, speed=2.0),     # new (diff speed)
        SegmentTiming(3.0, 4.0, 2.5, 0.5, speed=2.0),     # merge with prev
        SegmentTiming(4.0, 5.0, 3.0, 1.0, speed=1.0),     # new (diff speed)
    ]
    result = gen._merge_segment_timings(timings)

    assert len(result) == 3
    # First merged: 0-2s at 1.0x
    assert result[0].src_start == 0.0
    assert result[0].src_end == 2.0
    assert result[0].out_duration == pytest.approx(2.0)
    assert result[0].speed == 1.0
    # Second merged: 2-4s at 2.0x
    assert result[1].src_start == 2.0
    assert result[1].src_end == 4.0
    assert result[1].out_duration == pytest.approx(1.0)
    assert result[1].speed == 2.0
    # Third: 4-5s at 1.0x
    assert result[2].src_start == 4.0
    assert result[2].src_end == 5.0
    assert result[2].speed == 1.0


def test_merge_segment_timings_preserves_is_filler():
    """合并时 is_filler 只有在两段都为 filler 时才为 True。"""
    gen = _make_generator()
    # Both filler
    timings1 = [
        SegmentTiming(0.0, 1.0, 0.0, 1.0, speed=1.0, is_filler=True),
        SegmentTiming(1.0, 2.0, 1.0, 1.0, speed=1.0, is_filler=True),
    ]
    result1 = gen._merge_segment_timings(timings1)
    assert result1[0].is_filler is True

    # Mixed filler
    timings2 = [
        SegmentTiming(0.0, 1.0, 0.0, 1.0, speed=1.0, is_filler=True),
        SegmentTiming(1.0, 2.0, 1.0, 1.0, speed=1.0, is_filler=False),
    ]
    result2 = gen._merge_segment_timings(timings2)
    assert result2[0].is_filler is False


def test_merge_segment_timings_large_reduction(caplog):
    """大量同速 segment 合并时记录日志。"""
    gen = _make_generator()
    caplog.set_level(logging.INFO)
    # Simulate 100 consecutive 1x speed segments
    timings = [
        SegmentTiming(i * 1.0, (i + 1) * 1.0, i * 1.0, 1.0, speed=1.0)
        for i in range(100)
    ]
    result = gen._merge_segment_timings(timings)

    assert len(result) == 1
    assert result[0].src_start == 0.0
    assert result[0].src_end == 100.0
    assert result[0].out_duration == pytest.approx(100.0)
    assert "Merged 100 segments into 1" in caplog.text
    assert "99.0% reduction" in caplog.text
