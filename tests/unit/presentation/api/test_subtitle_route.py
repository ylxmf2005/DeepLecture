"""Unit tests for subtitle route validation and request handling."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from deeplecture.presentation.api.routes.subtitle import bp as subtitle_bp


@pytest.fixture
def minimal_app() -> Flask:
    """Create a minimal Flask app with only the subtitle blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(subtitle_bp, url_prefix="/api/subtitle")
    return app


@pytest.fixture
def mock_container() -> MagicMock:
    """Build the minimum container surface used by the subtitle route."""
    container = MagicMock()
    container.content_usecase.get_content.return_value = SimpleNamespace(subtitle_status="none")
    container.task_manager.submit.return_value = "task-123"
    return container


@pytest.fixture
def client(minimal_app: Flask, mock_container: MagicMock):
    """Create a test client with the DI container patched."""
    with (
        patch("deeplecture.presentation.api.routes.subtitle.get_container", return_value=mock_container),
        patch("deeplecture.presentation.api.routes.subtitle.resolve_models_for_task", return_value=(None, None)),
        minimal_app.test_client() as client,
    ):
        yield client


class TestGenerateSubtitleRoute:
    """Focused tests for subtitle generation route behavior."""

    @pytest.mark.unit
    def test_generate_subtitle_accepts_auto_language(self, client, mock_container: MagicMock) -> None:
        """The route should accept auto as a valid source language."""
        response = client.post(
            "/api/subtitle/test-content-id/generate",
            json={"language": "auto"},
            content_type="application/json",
        )

        assert response.status_code == 202
        mock_container.task_manager.submit.assert_called_once()
        submitted_metadata = mock_container.task_manager.submit.call_args.kwargs["metadata"]
        assert submitted_metadata["language"] == "auto"

    @pytest.mark.unit
    def test_generate_subtitle_requires_language_when_missing(self, client) -> None:
        """Missing language should still be rejected."""
        response = client.post(
            "/api/subtitle/test-content-id/generate",
            json={},
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "language" in response.json.get("error", "").lower()


class TestEnhanceTranslateRoute:
    """Focused tests for downstream source-language resolution."""

    @pytest.mark.unit
    def test_enhance_translate_resolves_auto_source_language(
        self,
        client,
        mock_container: MagicMock,
    ) -> None:
        mock_container.content_usecase.get_content.return_value = SimpleNamespace(
            subtitle_status="ready",
            enhance_translate_status="none",
            detected_source_language="ja",
        )

        def _submit(**kwargs):
            kwargs["task"](None)
            return "task-123"

        mock_container.task_manager.submit.side_effect = _submit

        response = client.post(
            "/api/subtitle/test-content-id/enhance-translate",
            json={"source_language": "auto", "target_language": "en"},
            content_type="application/json",
        )

        assert response.status_code == 202
        req = mock_container.subtitle_usecase.enhance_and_translate.call_args.args[0]
        assert req.source_language == "ja"
        submitted_metadata = mock_container.task_manager.submit.call_args.kwargs["metadata"]
        assert submitted_metadata["source_language"] == "auto"
        assert submitted_metadata["resolved_source_language"] == "ja"

    @pytest.mark.unit
    def test_enhance_translate_rejects_unresolved_auto_source_language(
        self,
        client,
        mock_container: MagicMock,
    ) -> None:
        mock_container.content_usecase.get_content.return_value = SimpleNamespace(
            subtitle_status="ready",
            enhance_translate_status="none",
            detected_source_language=None,
        )

        response = client.post(
            "/api/subtitle/test-content-id/enhance-translate",
            json={"source_language": "auto", "target_language": "en"},
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "generate subtitles first" in response.json.get("error", "").lower()
