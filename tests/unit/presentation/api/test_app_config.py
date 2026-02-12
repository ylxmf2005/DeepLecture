"""Unit tests for Flask app configuration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from deeplecture.presentation.api.app import create_app


class TestAppConfig:
    """Tests for app-level Flask configuration."""

    @pytest.mark.unit
    def test_max_content_length_uses_largest_upload_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MAX_CONTENT_LENGTH should follow configured upload limits."""
        from deeplecture.presentation.api import app as app_module

        settings = SimpleNamespace(
            server=SimpleNamespace(
                max_upload_bytes=32 * 1024 * 1024,
                max_note_image_bytes=8 * 1024 * 1024,
            )
        )

        monkeypatch.setattr(app_module, "get_settings", lambda: settings)
        monkeypatch.setattr(app_module, "register_error_handlers", lambda _app: None)
        monkeypatch.setattr(app_module, "init_rate_limiter", lambda _app: None)
        monkeypatch.setattr(app_module, "_register_blueprints", lambda _app: None)

        app = create_app(start_workers=False)

        assert app.config["MAX_CONTENT_LENGTH"] == 32 * 1024 * 1024
