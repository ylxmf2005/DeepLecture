"""Integration tests for media download route."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _write_bytes(path: Path, data: bytes = b"data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class TestMediaDownloadAPI:
    @pytest.mark.integration
    def test_download_original_mp4_without_export(self, client, mock_container: MagicMock, tmp_path: Path) -> None:
        content_dir = tmp_path / "content-c1"
        video_path = _write_bytes(content_dir / "video.mp4", b"fake-mp4")

        metadata = SimpleNamespace(video_file=str(video_path), source_file=None, original_filename="lesson.mp4")
        mock_container.content_usecase.get_content.return_value = metadata
        mock_container.path_resolver.get_content_dir.return_value = str(content_dir)
        mock_container.video_processor = MagicMock()

        response = client.get("/api/content/c1/video/download")

        assert response.status_code == 200
        assert response.content_type.startswith("video/mp4")
        assert "attachment" in response.headers.get("Content-Disposition", "")
        mock_container.video_processor.export_mp4.assert_not_called()

    @pytest.mark.integration
    def test_download_with_voiceover_and_source_hard_subtitle_uses_export(
        self,
        client,
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        content_dir = tmp_path / "content-c1"
        video_path = _write_bytes(content_dir / "video.mkv", b"fake-mkv")
        audio_path = _write_bytes(content_dir / "voiceovers" / "track-a.m4a", b"fake-m4a")

        metadata = SimpleNamespace(video_file=str(video_path), source_file=None, original_filename="lesson.mkv")
        mock_container.content_usecase.get_content.return_value = metadata
        mock_container.path_resolver.get_content_dir.return_value = str(content_dir)

        mock_container.subtitle_storage = MagicMock()
        source_segments = [SimpleNamespace(start=0.0, end=1.0, text="Hello world")]

        def _load(_content_id: str, language: str):
            if language == "en_enhanced":
                return source_segments
            return None

        mock_container.subtitle_storage.load.side_effect = _load
        mock_container.video_processor = MagicMock()

        def _fake_export(video_path_arg: str, output_path_arg: str, **_kwargs) -> None:
            _write_bytes(Path(output_path_arg), b"rendered-mp4")

        mock_container.video_processor.export_mp4.side_effect = _fake_export

        response = client.get(
            "/api/content/c1/video/download"
            "?audio_track=track-a&burn_source_subtitle=1&burn_target_subtitle=0&source_language=en"
        )

        assert response.status_code == 200
        assert response.content_type.startswith("video/mp4")
        mock_container.video_processor.export_mp4.assert_called_once()

        _, kwargs = mock_container.video_processor.export_mp4.call_args
        assert kwargs["audio_path"] == str(audio_path.resolve(strict=False))
        subtitle_path = Path(kwargs["subtitle_path"])
        assert subtitle_path.is_file()
        assert "Hello world" in subtitle_path.read_text(encoding="utf-8")

    @pytest.mark.integration
    def test_download_with_dual_hard_subtitle_builds_combined_srt(
        self,
        client,
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        content_dir = tmp_path / "content-c1"
        video_path = _write_bytes(content_dir / "video.mp4", b"fake-mp4")

        metadata = SimpleNamespace(video_file=str(video_path), source_file=None, original_filename="lesson.mp4")
        mock_container.content_usecase.get_content.return_value = metadata
        mock_container.path_resolver.get_content_dir.return_value = str(content_dir)

        mock_container.subtitle_storage = MagicMock()
        source_segments = [SimpleNamespace(start=0.0, end=1.0, text="Hello")]
        target_segments = [SimpleNamespace(start=0.0, end=1.0, text="你好")]

        def _load(_content_id: str, language: str):
            if language == "en_enhanced":
                return source_segments
            if language == "zh_enhanced":
                return target_segments
            return None

        mock_container.subtitle_storage.load.side_effect = _load
        mock_container.video_processor = MagicMock()

        def _fake_export(video_path_arg: str, output_path_arg: str, **_kwargs) -> None:
            _write_bytes(Path(output_path_arg), b"rendered-mp4")

        mock_container.video_processor.export_mp4.side_effect = _fake_export

        response = client.get(
            "/api/content/c1/video/download"
            "?burn_source_subtitle=1&burn_target_subtitle=1&source_language=en&target_language=zh"
        )

        assert response.status_code == 200
        assert response.content_type.startswith("video/mp4")
        mock_container.video_processor.export_mp4.assert_called_once()

        _, kwargs = mock_container.video_processor.export_mp4.call_args
        subtitle_path = Path(kwargs["subtitle_path"])
        srt = subtitle_path.read_text(encoding="utf-8")
        assert "Hello" in srt
        assert "你好" in srt

    @pytest.mark.integration
    def test_download_with_auto_source_language_uses_detected_language(
        self,
        client,
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        content_dir = tmp_path / "content-c1"
        video_path = _write_bytes(content_dir / "video.mp4", b"fake-mp4")

        metadata = SimpleNamespace(
            video_file=str(video_path),
            source_file=None,
            original_filename="lesson.mp4",
            detected_source_language="ja",
        )
        mock_container.content_usecase.get_content.return_value = metadata
        mock_container.path_resolver.get_content_dir.return_value = str(content_dir)

        mock_container.subtitle_storage = MagicMock()
        source_segments = [SimpleNamespace(start=0.0, end=1.0, text="こんにちは")]

        def _load(_content_id: str, language: str):
            if language == "ja_enhanced":
                return source_segments
            return None

        mock_container.subtitle_storage.load.side_effect = _load
        mock_container.video_processor = MagicMock()

        def _fake_export(video_path_arg: str, output_path_arg: str, **_kwargs) -> None:
            _write_bytes(Path(output_path_arg), b"rendered-mp4")

        mock_container.video_processor.export_mp4.side_effect = _fake_export

        response = client.get(
            "/api/content/c1/video/download" "?burn_source_subtitle=1&burn_target_subtitle=0&source_language=auto"
        )

        assert response.status_code == 200
        calls = [call.args for call in mock_container.subtitle_storage.load.call_args_list]
        assert ("c1", "ja_enhanced") in calls
