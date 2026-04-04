"""Video downloader implementation using yt-dlp.

Implements VideoDownloaderProtocol with SSRF hardening:
- Scheme allowlist (http/https)
- Domain allowlist
- Optional private-IP resolution blocking
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
import uuid
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class YtdlpDownloader:
    """Download videos from supported platforms via yt-dlp."""

    _COOKIE_UNAVAILABLE_MARKERS: ClassVar[tuple[str, ...]] = (
        "failed to load cookies",
        "could not find chrome cookies database",
        "could not find local state file",
        "failed to decrypt cookie",
        "failed to decrypt with dpapi",
        "cannot extract cookies from chrome",
    )

    _YOUTUBE_AUTH_REQUIRED_MARKERS: ClassVar[tuple[str, ...]] = (
        "sign in to confirm you're not a bot",
        "sign in to confirm you’re not a bot",
        "age-restricted",
        "confirm your age",
        "private video",
        "this video is private",
        "members-only",
        "channel members only",
        "authentication required",
        "login required",
    )

    _BILIBILI_AUTH_REQUIRED_MARKERS: ClassVar[tuple[str, ...]] = (
        "http error 412",
        "precondition failed",
        "unable to download webpage",
        "risk control",
        "request blocked",
    )

    DEFAULT_ALLOWED_DOMAINS: ClassVar[list[str]] = [
        "youtube.com",
        "youtu.be",
        "www.youtube.com",
        "m.youtube.com",
        "bilibili.com",
        "www.bilibili.com",
        "vimeo.com",
        "www.vimeo.com",
        "dailymotion.com",
        "www.dailymotion.com",
    ]

    DEFAULT_MAX_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5GB
    DEFAULT_TIMEOUT_SECONDS = 1800  # 30 minutes

    def __init__(
        self,
        output_folder: str,
        *,
        allowed_domains: list[str] | None = None,
        max_size_bytes: int | None = None,
        timeout_seconds: int | None = None,
        allow_private_ips: bool = False,
    ) -> None:
        self._output_folder = output_folder
        self._allowed_domains = allowed_domains or list(self.DEFAULT_ALLOWED_DOMAINS)
        self._max_size_bytes = max_size_bytes or self.DEFAULT_MAX_SIZE_BYTES
        self._timeout_seconds = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        self._allow_private_ips = allow_private_ips

    def validate_url(self, url: str) -> None:
        try:
            parsed = urlparse(url)
        except Exception as exc:
            raise ValueError(f"Invalid URL format: {exc}") from exc

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL scheme must be http or https, got: {parsed.scheme!r}")
        if not parsed.netloc:
            raise ValueError("URL must include a host")

        # Use parsed.hostname to correctly handle IPv6, userinfo, and port
        host = parsed.hostname
        if not host:
            raise ValueError("URL must include a valid host")
        host = host.lower()

        if not self._is_domain_allowed(host):
            raise ValueError(f"Domain '{host}' is not allowed. Allowed: {', '.join(self._allowed_domains)}")

        if not self._allow_private_ips:
            self._check_ssrf(host)

    def download_video(self, url: str, output_filename: str) -> dict[str, Any]:
        # Validate URL before touching yt-dlp.
        self.validate_url(url)

        os.makedirs(self._output_folder, exist_ok=True)

        # Sanitize filename: basename only, no path separators or control chars
        safe_base = self._sanitize_filename(output_filename)

        # Avoid collisions between concurrent downloads by suffixing a short random token.
        token = uuid.uuid4().hex[:8]
        outtmpl = os.path.join(self._output_folder, f"{safe_base}_{token}.%(ext)s")

        ydl_opts: dict[str, Any] = {
            "format": ("bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best"),
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": min(int(self._timeout_seconds), 300),
            "retries": 3,
            "max_filesize": self._max_size_bytes,
        }

        try:
            import yt_dlp  # type: ignore[import]
        except ImportError:
            return {
                "success": False,
                "error": "yt-dlp is required for URL video import. Install it with 'uv add yt-dlp'.",
            }

        source_type = self._detect_source_type(url)

        if self._should_try_browser_cookie(source_type):
            opts_with_chrome_cookie = {**ydl_opts, "cookiesfrombrowser": ("chrome",)}

            try:
                return self._download_once(yt_dlp, opts_with_chrome_cookie, url)
            except Exception as first_exc:
                if not self._is_cookie_unavailable_error(first_exc):
                    logger.error("yt-dlp download failed for %s with browser cookies: %s", url, first_exc)
                    return {
                        "success": False,
                        "error": self._format_download_error(first_exc, source_type=source_type),
                    }

                logger.warning(
                    "Chrome cookie loading failed for %s (%s), retrying without cookies: %s",
                    url,
                    source_type,
                    first_exc,
                )
                try:
                    return self._download_once(yt_dlp, ydl_opts, url)
                except Exception as second_exc:
                    logger.error("yt-dlp download failed for %s after cookie fallback: %s", url, second_exc)
                    return {
                        "success": False,
                        "error": self._format_download_error(
                            second_exc,
                            source_type=source_type,
                            cookie_unavailable_before_failure=True,
                        ),
                    }

        try:
            return self._download_once(yt_dlp, ydl_opts, url)
        except Exception as exc:
            logger.error("yt-dlp download failed for %s: %s", url, exc)
            return {
                "success": False,
                "error": self._format_download_error(exc, source_type=source_type),
            }

    def _download_once(self, yt_dlp_module: Any, ydl_opts: dict[str, Any], url: str) -> dict[str, Any]:
        with yt_dlp_module.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            filesize = info.get("filesize") or info.get("filesize_approx") or 0
            if isinstance(filesize, int | float) and filesize > self._max_size_bytes:
                return {
                    "success": False,
                    "error": (
                        f"Video size ({filesize / 1024 / 1024:.1f}MB) exceeds "
                        f"limit ({self._max_size_bytes / 1024 / 1024:.1f}MB)"
                    ),
                }

            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            return {
                "success": True,
                "filepath": filename,
                "title": info.get("title", "Unknown Title"),
                "duration": int(info.get("duration") or 0),
                "source_type": self._detect_source_type(url),
            }

    @classmethod
    def _is_cookie_unavailable_error(cls, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(marker in msg for marker in cls._COOKIE_UNAVAILABLE_MARKERS)

    @classmethod
    def _is_youtube_auth_required_error(cls, error_message: str) -> bool:
        msg = (error_message or "").lower()
        return any(marker in msg for marker in cls._YOUTUBE_AUTH_REQUIRED_MARKERS)

    @classmethod
    def _is_youtube_url(cls, url: str) -> bool:
        u = (url or "").lower()
        return "youtube.com" in u or "youtu.be" in u

    @classmethod
    def _is_bilibili_url(cls, url: str) -> bool:
        u = (url or "").lower()
        return "bilibili.com" in u

    @classmethod
    def _should_try_browser_cookie(cls, source_type: str) -> bool:
        return source_type in {"youtube", "bilibili"}

    @classmethod
    def _is_bilibili_auth_required_error(cls, error_message: str) -> bool:
        msg = (error_message or "").lower()
        return any(marker in msg for marker in cls._BILIBILI_AUTH_REQUIRED_MARKERS)

    def _format_download_error(
        self,
        exc: Exception,
        *,
        source_type: str,
        cookie_unavailable_before_failure: bool = False,
    ) -> str:
        raw_error = str(exc) or "unknown error"

        if source_type == "youtube" and (
            cookie_unavailable_before_failure or self._is_youtube_auth_required_error(raw_error)
        ):
            return self._build_youtube_troubleshooting_message(raw_error)
        if source_type == "bilibili" and (
            cookie_unavailable_before_failure or self._is_bilibili_auth_required_error(raw_error)
        ):
            return self._build_bilibili_troubleshooting_message(raw_error)

        return raw_error

    @staticmethod
    def _build_youtube_troubleshooting_message(raw_error: str) -> str:
        return (
            "YouTube download failed. Suggested fixes: "
            "1) Sign in to YouTube in Chrome and confirm the video can be played. "
            "2) Close all Chrome windows completely and retry (release cookie DB lock). "
            "3) Update yt-dlp to the latest version and retry. "
            "4) If it still fails, export cookies.txt and verify with '--cookies cookies.txt'. "
            f"Original error: {raw_error}"
        )

    @staticmethod
    def _build_bilibili_troubleshooting_message(raw_error: str) -> str:
        return (
            "Bilibili download failed. Suggested fixes: "
            "1) Sign in to Bilibili in Chrome and confirm the video plays in the browser. "
            "2) Retry the import so yt-dlp can reuse your Chrome cookies. "
            "3) If it still fails, update yt-dlp and retry in case Bilibili changed its anti-bot checks. "
            "4) If needed, export cookies.txt and verify with '--cookies cookies.txt'. "
            f"Original error: {raw_error}"
        )

    def _is_domain_allowed(self, host: str) -> bool:
        for allowed in self._allowed_domains:
            allowed_l = allowed.lower()
            if host == allowed_l or host.endswith("." + allowed_l):
                return True
        return False

    @staticmethod
    def _detect_source_type(url: str) -> str:
        u = (url or "").lower()
        if YtdlpDownloader._is_youtube_url(u):
            return "youtube"
        if "bilibili.com" in u:
            return "bilibili"
        return "web"

    # Surge/ClashX/Clash fake-IP range (used as proxy placeholder)
    _FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")

    def _check_ssrf(self, host: str) -> None:
        """Check all DNS records for private/internal IPs (SSRF protection)."""
        try:
            results = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            return

        for _, _, _, _, sockaddr in results:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue

            # Allow proxy fake-IP range (198.18.0.0/15)
            if ip in self._FAKE_IP_NETWORK:
                continue

            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError(f"URL resolves to private/internal IP ({ip_str}), not allowed")

    # Regex: only allow alphanumeric, dash, underscore, dot, space, CJK characters
    _SAFE_FILENAME_RE = re.compile(r"[^\w\s\-.\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+")
    _MAX_FILENAME_LEN = 200

    @classmethod
    def _sanitize_filename(cls, name: str) -> str:
        """Sanitize filename: basename only, no path separators or control chars."""
        if not name:
            return "video"
        # Extract basename to prevent path traversal
        safe = Path(name).name
        # Remove control characters and dangerous chars
        safe = cls._SAFE_FILENAME_RE.sub("_", safe)
        # Collapse multiple underscores/spaces
        safe = re.sub(r"[_\s]+", "_", safe).strip("_. ")
        # Truncate to reasonable length
        if len(safe) > cls._MAX_FILENAME_LEN:
            safe = safe[: cls._MAX_FILENAME_LEN]
        return safe or "video"
