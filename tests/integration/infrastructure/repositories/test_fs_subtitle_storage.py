"""Integration tests for FsSubtitleStorage."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from deeplecture.domain import Segment
from deeplecture.infrastructure.repositories.fs_subtitle_storage import FsSubtitleStorage


class TestFsSubtitleStorage:
    """Integration tests for FsSubtitleStorage."""

    @pytest.fixture
    def storage(self, test_data_dir: Path) -> FsSubtitleStorage:
        """Create FsSubtitleStorage with test directory."""
        content_dir = test_data_dir / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        return FsSubtitleStorage(content_dir)

    @pytest.fixture
    def sample_segments(self) -> list[Segment]:
        """Create sample segments for testing."""
        return [
            Segment(start=0.0, end=2.5, text="Hello, welcome to the lecture."),
            Segment(start=2.5, end=5.0, text="Today we'll discuss testing."),
            Segment(start=5.0, end=8.0, text="Let's get started."),
        ]

    @pytest.mark.integration
    def test_save_and_load(self, storage: FsSubtitleStorage, sample_segments: list[Segment]) -> None:
        """save() should persist segments that can be loaded."""
        storage.save("test-123", sample_segments, "en")
        loaded = storage.load("test-123", "en")

        assert loaded is not None
        assert len(loaded) == len(sample_segments)
        assert loaded[0].text == sample_segments[0].text
        assert loaded[0].start == sample_segments[0].start
        assert loaded[0].end == sample_segments[0].end

    @pytest.mark.integration
    def test_load_nonexistent(self, storage: FsSubtitleStorage) -> None:
        """load() should return None for nonexistent subtitles."""
        result = storage.load("nonexistent-id", "en")
        assert result is None

    @pytest.mark.integration
    def test_exists_true(self, storage: FsSubtitleStorage, sample_segments: list[Segment]) -> None:
        """exists() should return True for saved subtitles."""
        storage.save("test-123", sample_segments, "en")
        assert storage.exists("test-123", "en") is True

    @pytest.mark.integration
    def test_exists_false(self, storage: FsSubtitleStorage) -> None:
        """exists() should return False for nonexistent subtitles."""
        assert storage.exists("nonexistent-id", "en") is False

    @pytest.mark.integration
    def test_multiple_languages(self, storage: FsSubtitleStorage, sample_segments: list[Segment]) -> None:
        """Different languages should be stored separately."""
        segments_zh = [
            Segment(start=0.0, end=2.5, text="你好，欢迎来到讲座。"),
            Segment(start=2.5, end=5.0, text="今天我们讨论测试。"),
        ]

        storage.save("test-123", sample_segments, "en")
        storage.save("test-123", segments_zh, "zh")

        loaded_en = storage.load("test-123", "en")
        loaded_zh = storage.load("test-123", "zh")

        assert loaded_en is not None
        assert loaded_zh is not None
        assert len(loaded_en) == 3
        assert len(loaded_zh) == 2
        assert loaded_en[0].text == "Hello, welcome to the lecture."
        assert loaded_zh[0].text == "你好，欢迎来到讲座。"

    @pytest.mark.integration
    def test_srt_format_round_trip(self, storage: FsSubtitleStorage, sample_segments: list[Segment]) -> None:
        """Segments should survive SRT format conversion."""
        storage.save("test-format", sample_segments, "en")
        loaded = storage.load("test-format", "en")

        assert loaded is not None
        for original, loaded_seg in zip(sample_segments, loaded, strict=False):
            # Floating point comparison with tolerance
            assert abs(original.start - loaded_seg.start) < 0.001
            assert abs(original.end - loaded_seg.end) < 0.001
            assert original.text == loaded_seg.text

    @pytest.mark.integration
    def test_save_background(self, storage: FsSubtitleStorage) -> None:
        """save_background() should persist background context as JSON."""
        background_data = {
            "context": "This is a computer science lecture",
            "speaker": "Professor Smith",
        }

        storage.save_background("test-bg", background_data)

        # Verify file was created
        import json
        from pathlib import Path

        bg_path = Path(storage._content_dir) / "test-bg" / "background.json"
        assert bg_path.exists()

        loaded = json.loads(bg_path.read_text(encoding="utf-8"))
        assert loaded == background_data

    @pytest.mark.integration
    def test_path_traversal_protection(self, storage: FsSubtitleStorage) -> None:
        """Storage should reject path traversal attempts."""
        segments = [Segment(start=0.0, end=1.0, text="Test")]

        with pytest.raises(ValueError):
            storage.save("../evil", segments, "en")

    @pytest.mark.integration
    def test_overwrite_existing(self, storage: FsSubtitleStorage, sample_segments: list[Segment]) -> None:
        """save() should overwrite existing subtitles."""
        storage.save("test-overwrite", sample_segments, "en")

        new_segments = [Segment(start=0.0, end=1.0, text="Replaced content")]
        storage.save("test-overwrite", new_segments, "en")

        loaded = storage.load("test-overwrite", "en")
        assert loaded is not None
        assert len(loaded) == 1
        assert loaded[0].text == "Replaced content"
