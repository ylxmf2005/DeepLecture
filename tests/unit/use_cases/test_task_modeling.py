"""Unit tests for task model resolution utilities."""

import pytest

from deeplecture.domain.entities.config import ContentConfig
from deeplecture.use_cases.task_modeling import TaskModelResolver


class TestTaskModelResolver:
    @pytest.mark.unit
    def test_resolve_prefers_request_overrides(self) -> None:
        resolver = TaskModelResolver(
            yaml_llm_task_models={"default": "yaml-llm"},
            yaml_tts_task_models={"default": "yaml-tts"},
        )
        content_cfg = ContentConfig(llm_model="content-llm", tts_model="content-tts")
        global_cfg = ContentConfig(llm_model="global-llm", tts_model="global-tts")

        resolved = resolver.resolve(
            task_key="ask_video",
            requested_llm_model="request-llm",
            requested_tts_model="request-tts",
            content_config=content_cfg,
            global_config=global_cfg,
        )

        assert resolved.llm_model == "request-llm"
        assert resolved.tts_model == "request-tts"

    @pytest.mark.unit
    def test_resolve_accepts_legacy_alias_keys_in_stored_task_map(self) -> None:
        resolver = TaskModelResolver(
            yaml_llm_task_models={"default": "yaml-llm"},
            yaml_tts_task_models={"default": "yaml-tts"},
        )
        content_cfg = ContentConfig(
            llm_task_models={"slide_lecture": "content-video-llm"},
            tts_task_models={"voiceover": "content-voice-tts"},
        )

        resolved = resolver.resolve(
            task_key="video_generation",
            requested_llm_model=None,
            requested_tts_model=None,
            content_config=content_cfg,
            global_config=None,
        )
        assert resolved.llm_model == "content-video-llm"
        assert resolved.tts_model == "yaml-tts"

        resolved_voice = resolver.resolve(
            task_key="voiceover_generation",
            requested_llm_model=None,
            requested_tts_model=None,
            content_config=content_cfg,
            global_config=None,
        )
        assert resolved_voice.tts_model == "content-voice-tts"

    @pytest.mark.unit
    def test_resolve_falls_back_through_content_global_yaml(self) -> None:
        resolver = TaskModelResolver(
            yaml_llm_task_models={"default": "yaml-default", "ask_video": "yaml-ask"},
            yaml_tts_task_models={"default": "yaml-tts"},
        )
        global_cfg = ContentConfig(llm_task_models={"ask_video": "global-ask"})

        resolved = resolver.resolve(
            task_key="ask_video",
            requested_llm_model=None,
            requested_tts_model=None,
            content_config=None,
            global_config=global_cfg,
        )
        assert resolved.llm_model == "global-ask"
        assert resolved.tts_model == "yaml-tts"

        resolved_yaml = resolver.resolve(
            task_key="subtitle_translation",
            requested_llm_model=None,
            requested_tts_model=None,
            content_config=None,
            global_config=None,
        )
        assert resolved_yaml.llm_model == "yaml-default"
