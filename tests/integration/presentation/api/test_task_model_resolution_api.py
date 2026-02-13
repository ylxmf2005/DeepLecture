"""Integration tests for task-level model resolution across API routes."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from deeplecture.domain.entities.config import ContentConfig
from deeplecture.use_cases.interfaces.llm_provider import LLMModelInfo
from deeplecture.use_cases.interfaces.tts_provider import TTSModelInfo
from deeplecture.use_cases.task_modeling import TaskModelResolver


@dataclass
class _VoiceoverResult:
    audio_path: str
    timeline_path: str
    audio_duration: float
    video_duration: float


def _configure_model_resolution_baseline(mock_container: MagicMock) -> None:
    """Set minimal container dependencies required by model resolution helper."""
    mock_container.global_config_storage = MagicMock()
    mock_container.content_config_storage = MagicMock()
    mock_container.task_model_resolver = TaskModelResolver(
        yaml_llm_task_models={},
        yaml_tts_task_models={},
    )
    mock_container.llm_provider = MagicMock()
    mock_container.tts_provider = MagicMock()


class TestTaskModelResolutionAPI:
    @pytest.mark.integration
    def test_cheatsheet_uses_content_task_llm_model(self, client, mock_container: MagicMock) -> None:
        _configure_model_resolution_baseline(mock_container)
        mock_container.global_config_storage.load.return_value = ContentConfig(
            llm_task_models={"cheatsheet_generation": "global-llm"}
        )
        mock_container.content_config_storage.load.return_value = ContentConfig(
            llm_task_models={"cheatsheet_generation": "content-llm"}
        )
        mock_container.llm_provider.get.return_value = MagicMock()

        cheatsheet_result = MagicMock()
        cheatsheet_result.to_dict.return_value = {"content_id": "c1", "content": "ok", "updated_at": None}
        mock_container.cheatsheet_usecase.generate.return_value = cheatsheet_result

        def _submit(*, task, **kwargs):
            _ = kwargs
            task(None)
            return "task-cheatsheet-1"

        mock_container.task_manager.submit.side_effect = _submit

        response = client.post(
            "/api/cheatsheet/generate",
            json={
                "content_id": "c1",
                "language": "en",
            },
        )

        assert response.status_code == 202
        assert response.json["success"] is True
        assert response.json["data"]["task_id"] == "task-cheatsheet-1"

        mock_container.llm_provider.get.assert_called_with("content-llm")
        call_args = mock_container.cheatsheet_usecase.generate.call_args
        req = call_args.args[0]
        assert req.llm_model == "content-llm"

    @pytest.mark.integration
    def test_cheatsheet_request_llm_model_overrides_task_defaults(self, client, mock_container: MagicMock) -> None:
        _configure_model_resolution_baseline(mock_container)
        mock_container.global_config_storage.load.return_value = ContentConfig(
            llm_task_models={"cheatsheet_generation": "global-llm"}
        )
        mock_container.content_config_storage.load.return_value = ContentConfig(
            llm_task_models={"cheatsheet_generation": "content-llm"}
        )
        mock_container.llm_provider.get.return_value = MagicMock()

        cheatsheet_result = MagicMock()
        cheatsheet_result.to_dict.return_value = {"content_id": "c1", "content": "ok", "updated_at": None}
        mock_container.cheatsheet_usecase.generate.return_value = cheatsheet_result

        def _submit(*, task, **kwargs):
            _ = kwargs
            task(None)
            return "task-cheatsheet-2"

        mock_container.task_manager.submit.side_effect = _submit

        response = client.post(
            "/api/cheatsheet/generate",
            json={
                "content_id": "c1",
                "language": "en",
                "llm_model": "request-llm",
            },
        )

        assert response.status_code == 202
        assert response.json["success"] is True
        mock_container.llm_provider.get.assert_called_with("request-llm")

        req = mock_container.cheatsheet_usecase.generate.call_args.args[0]
        assert req.llm_model == "request-llm"

    @pytest.mark.integration
    def test_voiceover_uses_content_task_tts_model(self, client, mock_container: MagicMock) -> None:
        _configure_model_resolution_baseline(mock_container)
        mock_container.global_config_storage.load.return_value = ContentConfig(
            tts_task_models={"voiceover_generation": "global-tts"}
        )
        mock_container.content_config_storage.load.return_value = ContentConfig(
            tts_task_models={"voiceover_generation": "content-tts"}
        )
        mock_container.tts_provider.get.return_value = MagicMock()

        mock_container.artifact_storage = MagicMock()
        mock_container.artifact_storage.get_path.return_value = "/tmp/video.mp4"
        mock_container.path_resolver = MagicMock()
        mock_container.path_resolver.get_content_dir.return_value = "/tmp/content-c1"
        mock_container.voiceover_storage = MagicMock()
        mock_container.voiceover_usecase.generate.return_value = _VoiceoverResult(
            audio_path="/tmp/content-c1/voiceovers/a.m4a",
            timeline_path="/tmp/content-c1/voiceovers/a_sync_timeline.json",
            audio_duration=12.3,
            video_duration=15.0,
        )

        def _submit(*, task, **kwargs):
            _ = kwargs
            task(None)
            return "task-voiceover-1"

        mock_container.task_manager.submit.side_effect = _submit

        response = client.post(
            "/api/content/c1/voiceovers",
            json={
                "voiceover_name": "voice-1",
                "language": "en",
            },
        )

        assert response.status_code == 202
        assert response.json["success"] is True
        assert response.json["data"]["task_id"] == "task-voiceover-1"
        mock_container.tts_provider.get.assert_called_with("content-tts")

        req = mock_container.voiceover_usecase.generate.call_args.args[0]
        assert req.tts_model == "content-tts"

    @pytest.mark.integration
    def test_config_endpoint_exposes_separate_llm_and_tts_task_keys(self, client, mock_container: MagicMock) -> None:
        _configure_model_resolution_baseline(mock_container)
        mock_container.llm_provider.list_models.return_value = [
            LLMModelInfo(name="cch", provider="openai", model="kimi-k2.5")
        ]
        mock_container.llm_provider.get_default_model_name.return_value = "cch"
        mock_container.tts_provider.list_models.return_value = [TTSModelInfo(name="edge-default", provider="edge_tts")]
        mock_container.tts_provider.get_default_model_name.return_value = "edge-default"
        mock_container.prompt_registry = MagicMock()
        mock_container.prompt_registry.list_func_ids.return_value = []
        mock_container.global_config_storage.load.return_value = ContentConfig(
            llm_task_models={"slide_lecture": "cch"},
            tts_task_models={"voiceover": "edge-default"},
        )

        fake_settings = SimpleNamespace(
            llm=SimpleNamespace(task_models={"ask_video": "cch"}),
            tts=SimpleNamespace(task_models={"default": "edge-default"}),
        )

        with patch("deeplecture.presentation.api.routes.config.get_settings", return_value=fake_settings):
            response = client.get("/api/config")

        assert response.status_code == 200
        assert response.json["success"] is True

        data = response.json["data"]
        assert "llmTaskKeys" in data
        assert "ttsTaskKeys" in data
        assert "voiceover_generation" not in data["llmTaskKeys"]
        assert data["ttsTaskKeys"] == ["video_generation", "voiceover_generation"]

        # Alias normalization from global overrides should map to canonical keys.
        assert data["llm"]["taskModelDefaults"]["video_generation"] == "cch"
        assert data["tts"]["taskModelDefaults"]["voiceover_generation"] == "edge-default"
