"""Unit tests for YtdlpDownloader."""

from __future__ import annotations

import types
from typing import Any, ClassVar

import pytest

from deeplecture.infrastructure.gateways.ytdlp_downloader import YtdlpDownloader


class _FakeYDL:
    """Configurable fake YoutubeDL context manager."""

    options_seen: ClassVar[list[dict[str, Any]]] = []
    behavior: ClassVar[str] = "success"

    def __init__(self, opts: dict[str, Any]) -> None:
        self._opts = opts
        self.__class__.options_seen.append(dict(opts))

    def __enter__(self) -> _FakeYDL:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False

    def extract_info(self, url: str, download: bool = False) -> dict[str, Any]:
        del url

        has_cookie = "cookiesfrombrowser" in self._opts
        behavior = self.__class__.behavior

        if behavior == "cookie_unavailable_then_success":
            if has_cookie:
                raise Exception("failed to load cookies")
        elif behavior == "bilibili_auth_then_cookie_success":
            if not has_cookie:
                raise Exception("HTTP Error 412: Precondition Failed")
        elif behavior == "cookie_unavailable_then_auth_fail":
            if has_cookie:
                raise Exception("failed to load cookies")
            raise Exception("Sign in to confirm you\N{RIGHT SINGLE QUOTATION MARK}re not a bot")
        elif behavior == "auth_required":
            raise Exception("This is an age-restricted video")

        if not download:
            return {"filesize": 1024}

        return {
            "title": "Test Video",
            "duration": 12,
            "ext": "mp4",
        }

    def prepare_filename(self, info: dict[str, Any]) -> str:
        del info
        return "/tmp/source.mp4"


@pytest.fixture
def downloader(tmp_path) -> YtdlpDownloader:  # type: ignore[no-untyped-def]
    return YtdlpDownloader(
        output_folder=str(tmp_path),
        allow_private_ips=True,
    )


@pytest.fixture(autouse=True)
def reset_fake() -> None:
    _FakeYDL.options_seen = []
    _FakeYDL.behavior = "success"


class TestYtdlpDownloaderCookieBehavior:
    """Tests for platform cookie fallback behavior."""

    @staticmethod
    def _install_fake_yt_dlp(monkeypatch: pytest.MonkeyPatch) -> None:
        fake_module = types.SimpleNamespace(YoutubeDL=_FakeYDL)
        monkeypatch.setitem(__import__("sys").modules, "yt_dlp", fake_module)

    @pytest.mark.unit
    def test_youtube_uses_chrome_cookie_first(
        self, downloader: YtdlpDownloader, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._install_fake_yt_dlp(monkeypatch)

        result = downloader.download_video("https://www.youtube.com/watch?v=abc", "source")

        assert result["success"] is True
        assert len(_FakeYDL.options_seen) == 1
        assert _FakeYDL.options_seen[0]["cookiesfrombrowser"] == ("chrome",)

    @pytest.mark.unit
    def test_youtube_retries_without_cookie_when_unavailable(
        self,
        downloader: YtdlpDownloader,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _FakeYDL.behavior = "cookie_unavailable_then_success"
        self._install_fake_yt_dlp(monkeypatch)

        result = downloader.download_video("https://youtu.be/abc", "source")

        assert result["success"] is True
        assert len(_FakeYDL.options_seen) == 2
        assert _FakeYDL.options_seen[0]["cookiesfrombrowser"] == ("chrome",)
        assert "cookiesfrombrowser" not in _FakeYDL.options_seen[1]

    @pytest.mark.unit
    def test_youtube_cookie_fallback_failure_contains_suggestions(
        self,
        downloader: YtdlpDownloader,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _FakeYDL.behavior = "cookie_unavailable_then_auth_fail"
        self._install_fake_yt_dlp(monkeypatch)

        result = downloader.download_video("https://www.youtube.com/watch?v=abc", "source")

        assert result["success"] is False
        error = result["error"]
        assert "Suggested fixes" in error
        assert "Close all Chrome windows" in error
        assert "Original error" in error

    @pytest.mark.unit
    def test_non_youtube_does_not_use_cookie(
        self, downloader: YtdlpDownloader, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._install_fake_yt_dlp(monkeypatch)

        result = downloader.download_video("https://vimeo.com/123456", "source")

        assert result["success"] is True
        assert len(_FakeYDL.options_seen) == 1
        assert "cookiesfrombrowser" not in _FakeYDL.options_seen[0]

    @pytest.mark.unit
    def test_bilibili_uses_chrome_cookie_first(
        self, downloader: YtdlpDownloader, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._install_fake_yt_dlp(monkeypatch)

        result = downloader.download_video("https://www.bilibili.com/video/BV1t9wfzME2A", "source")

        assert result["success"] is True
        assert len(_FakeYDL.options_seen) == 1
        assert _FakeYDL.options_seen[0]["cookiesfrombrowser"] == ("chrome",)

    @pytest.mark.unit
    def test_bilibili_uses_browser_cookie_to_avoid_412(
        self,
        downloader: YtdlpDownloader,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _FakeYDL.behavior = "bilibili_auth_then_cookie_success"
        self._install_fake_yt_dlp(monkeypatch)

        result = downloader.download_video("https://www.bilibili.com/video/BV1t9wfzME2A", "source")

        assert result["success"] is True
        assert len(_FakeYDL.options_seen) == 1
        assert _FakeYDL.options_seen[0]["cookiesfrombrowser"] == ("chrome",)

    @pytest.mark.unit
    def test_bilibili_cookie_fallback_failure_contains_suggestions(
        self,
        downloader: YtdlpDownloader,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _FakeYDL.behavior = "cookie_unavailable_then_auth_fail"
        self._install_fake_yt_dlp(monkeypatch)

        result = downloader.download_video("https://www.bilibili.com/video/BV1t9wfzME2A", "source")

        assert result["success"] is False
        error = result["error"]
        assert "Bilibili download failed" in error
        assert "Chrome" in error
        assert "Original error" in error

    @pytest.mark.unit
    def test_url_allowlist_unchanged(self, downloader: YtdlpDownloader) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            downloader.validate_url("https://evil.example.com/video.mp4")
