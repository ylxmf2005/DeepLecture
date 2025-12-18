"""
Route smoke tests for all API blueprints.

These tests verify that routes are correctly wired and don't crash
on basic requests. They catch interface mismatches early.

Note: Due to Flask blueprint registration, all routes share /api prefix.
Blueprint-internal url_prefix is overwritten by register_blueprint().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from flask.testing import FlaskClient


class TestContentRoutes:
    """Smoke tests for content API routes."""

    @pytest.mark.integration
    def test_list_contents_returns_200(self, client: FlaskClient, mock_container: MagicMock) -> None:
        """GET /api/list should return 200."""
        mock_container.content_usecase.list_contents.return_value = []

        response = client.get("/api/list")

        assert response.status_code == 200
        assert response.json["success"] is True


class TestSubtitleRoutes:
    """Smoke tests for subtitle API routes."""

    @pytest.mark.integration
    def test_get_subtitle_vtt_not_found(self, client: FlaskClient, mock_container: MagicMock) -> None:
        """GET /api/<id>/vtt should return 404 when not found."""
        mock_container.subtitle_usecase.get_subtitles.return_value = None

        response = client.get("/api/test-content-id/vtt?language=en")

        assert response.status_code == 404

    @pytest.mark.integration
    def test_generate_subtitle_requires_language(self, client: FlaskClient, mock_container: MagicMock) -> None:
        """POST /api/<id>/generate without language returns 400."""
        response = client.post(
            "/api/test-content-id/generate",
            json={},
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "language" in response.json.get("error", "").lower()


class TestTaskRoutes:
    """Smoke tests for task API routes."""

    @pytest.mark.integration
    def test_get_tasks_by_content(self, client: FlaskClient, mock_container: MagicMock) -> None:
        """GET /api/content/<id> should return 200 with empty list."""
        mock_container.task_manager.list_tasks_by_content.return_value = []

        response = client.get("/api/content/test-content-id")

        assert response.status_code == 200

    @pytest.mark.integration
    def test_stream_tasks_endpoint_exists(self, client: FlaskClient, mock_container: MagicMock) -> None:
        """GET /api/stream/<id> should be accessible."""
        # SSE endpoint returns streaming response
        response = client.get("/api/stream/test-content-id")

        # Should not be 404 - endpoint exists
        assert response.status_code != 404


class TestConfigRoutes:
    """Smoke tests for config API routes."""

    @pytest.mark.integration
    def test_get_languages_returns_200(self, client: FlaskClient) -> None:
        """GET /api/languages should return 200."""
        response = client.get("/api/languages")

        assert response.status_code == 200
        assert response.json["success"] is True

    @pytest.mark.integration
    def test_get_llm_models_returns_200(self, client: FlaskClient) -> None:
        """GET /api/llm-models should return 200."""
        response = client.get("/api/llm-models")

        assert response.status_code == 200

    @pytest.mark.integration
    def test_get_tts_models_returns_200(self, client: FlaskClient) -> None:
        """GET /api/tts-models should return 200."""
        response = client.get("/api/tts-models")

        assert response.status_code == 200


class TestNoteRoutes:
    """Smoke tests for note API routes."""

    @pytest.mark.integration
    def test_generate_note_requires_content_id(self, client: FlaskClient) -> None:
        """POST /api/generate (notes) without content_id returns 400."""
        response = client.post(
            "/api/generate",
            json={},
            content_type="application/json",
        )

        assert response.status_code == 400


class TestLive2DRoutes:
    """Smoke tests for Live2D API routes."""

    @pytest.mark.integration
    def test_list_models_returns_200(self, client: FlaskClient) -> None:
        """GET /api/models should return 200."""
        response = client.get("/api/models")

        # Should return list of models
        assert response.status_code == 200


class TestUploadRoutes:
    """Smoke tests for upload API routes."""

    @pytest.mark.integration
    def test_upload_requires_file(self, client: FlaskClient) -> None:
        """POST /api/upload without file returns 400."""
        response = client.post(
            "/api/upload",
            content_type="multipart/form-data",
        )

        assert response.status_code == 400

    @pytest.mark.integration
    def test_import_url_requires_url(self, client: FlaskClient) -> None:
        """POST /api/import-url without url returns 400."""
        response = client.post(
            "/api/import-url",
            json={},
            content_type="application/json",
        )

        assert response.status_code == 400
