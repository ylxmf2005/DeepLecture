"""Integration tests for auto source-language resolution across routes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from deeplecture.domain import ContentType

if TYPE_CHECKING:
    from pathlib import Path


class TestSourceLanguageResolutionAPI:
    @pytest.mark.integration
    def test_timeline_generate_resolves_auto_subtitle_language(
        self,
        client,
        mock_container: MagicMock,
    ) -> None:
        mock_container.content_usecase.get_content.return_value = SimpleNamespace(detected_source_language="ja")
        mock_container.timeline_usecase.generate.return_value = SimpleNamespace(
            content_id="c1",
            language="en",
            entries=[],
            status="ready",
        )

        def _submit(*, task, **kwargs):
            _ = kwargs
            task(None)
            return "task-timeline-1"

        mock_container.task_manager.submit.side_effect = _submit

        with patch("deeplecture.presentation.api.routes.timeline.resolve_models_for_task", return_value=(None, None)):
            response = client.post(
                "/api/timeline/c1/generate",
                json={"subtitle_language": "auto", "output_language": "en"},
            )

        assert response.status_code == 202
        req = mock_container.timeline_usecase.generate.call_args.args[0]
        assert req.subtitle_language == "ja"

    @pytest.mark.integration
    def test_explanation_generate_resolves_auto_subtitle_language(
        self,
        client,
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        content_dir = tmp_path / "content-c1"
        screenshot = content_dir / "screenshots" / "frame.png"
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        screenshot.write_bytes(b"png")

        mock_container.content_usecase.get_content.return_value = SimpleNamespace(detected_source_language="ja")
        mock_container.path_resolver.get_content_dir.return_value = str(content_dir)
        mock_container.explanation_storage = MagicMock()
        mock_container.explanation_usecase.generate.return_value = SimpleNamespace(
            to_dict=lambda: {"content_id": "c1", "status": "ready"}
        )

        def _submit(*, task, **kwargs):
            _ = kwargs
            task(None)
            return "task-expl-1"

        mock_container.task_manager.submit.side_effect = _submit

        with patch(
            "deeplecture.presentation.api.routes.explanation.resolve_models_for_task", return_value=(None, None)
        ):
            response = client.post(
                "/api/content/c1/explanations",
                json={
                    "image_url": "/api/content/c1/screenshots/frame.png",
                    "timestamp": 12.5,
                    "subtitle_language": "auto",
                    "output_language": "en",
                },
            )

        assert response.status_code == 202
        req = mock_container.explanation_usecase.generate.call_args.args[0]
        assert req.subtitle_language == "ja"

    @pytest.mark.integration
    def test_slide_generation_rejects_unresolved_auto_source_language(
        self,
        client,
        mock_container: MagicMock,
    ) -> None:
        mock_container.content_usecase.get_content.return_value = SimpleNamespace(
            type=ContentType.SLIDE,
            detected_source_language=None,
            video_status="none",
        )

        with patch("deeplecture.presentation.api.routes.generation.resolve_models_for_task", return_value=(None, None)):
            response = client.post(
                "/api/content/c1/generate-video",
                json={"source_language": "auto", "target_language": "en"},
            )

        assert response.status_code == 400
        assert "concrete source language" in response.json.get("error", "").lower()
