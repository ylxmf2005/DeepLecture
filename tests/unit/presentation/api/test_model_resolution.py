"""Unit tests for model resolution helper fallback behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from deeplecture.domain.entities.config import ContentConfig
from deeplecture.presentation.api.shared.model_resolution import resolve_models_for_task
from deeplecture.use_cases.task_modeling import TaskModelResolver


def _make_container(*, global_cfg: ContentConfig | None = None) -> SimpleNamespace:
    container = SimpleNamespace()
    container.global_config_storage = MagicMock()
    container.global_config_storage.load.return_value = global_cfg
    container.content_config_storage = MagicMock()
    container.content_config_storage.load.return_value = None
    container.task_model_resolver = TaskModelResolver(
        yaml_llm_task_models={},
        yaml_tts_task_models={},
    )
    container.llm_provider = MagicMock()
    container.tts_provider = MagicMock()
    return container


class TestResolveModelsForTaskFallback:
    @pytest.mark.unit
    def test_stale_global_llm_model_falls_back_to_default(self) -> None:
        container = _make_container(
            global_cfg=ContentConfig(llm_task_models={"video_generation": "cch"}),
        )

        def _llm_get(model_id: str | None = None) -> object:
            if model_id == "cch":
                raise ValueError("Unknown LLM model: 'cch'. Available: gemini")
            return object()

        container.llm_provider.get.side_effect = _llm_get

        llm_model, tts_model = resolve_models_for_task(
            container=container,
            content_id="c1",
            task_key="video_generation",
            llm_model=None,
            tts_model=None,
        )

        assert llm_model is None
        assert tts_model is None
        assert container.llm_provider.get.call_args_list == [call("cch"), call()]

    @pytest.mark.unit
    def test_explicit_invalid_llm_model_raises_value_error(self) -> None:
        container = _make_container()
        container.llm_provider.get.side_effect = ValueError("Unknown LLM model: 'cch'. Available: gemini")

        with pytest.raises(ValueError, match="Unknown LLM model"):
            resolve_models_for_task(
                container=container,
                content_id="c1",
                task_key="video_generation",
                llm_model="cch",
                tts_model=None,
            )

        assert container.llm_provider.get.call_args_list == [call("cch")]

    @pytest.mark.unit
    def test_stale_global_tts_model_falls_back_to_default(self) -> None:
        container = _make_container(
            global_cfg=ContentConfig(tts_task_models={"video_generation": "old-tts"}),
        )

        def _tts_get(model_id: str | None = None) -> object:
            if model_id == "old-tts":
                raise ValueError("Unknown TTS model: 'old-tts'. Available: edge-default")
            return object()

        container.tts_provider.get.side_effect = _tts_get

        llm_model, tts_model = resolve_models_for_task(
            container=container,
            content_id="c1",
            task_key="video_generation",
            llm_model=None,
            tts_model=None,
        )

        assert llm_model is None
        assert tts_model is None
        assert container.tts_provider.get.call_args_list == [call("old-tts"), call()]
