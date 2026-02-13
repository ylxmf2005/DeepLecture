"""Compatibility tests for ContentConfig AI task model parsing."""

import pytest

from deeplecture.domain.entities.config import ContentConfig


class TestContentConfigTaskModelCompat:
    @pytest.mark.unit
    def test_from_dict_reads_snake_case_nested_ai_models(self) -> None:
        cfg = ContentConfig.from_dict(
            {
                "ai": {
                    "llm_model": "cch",
                    "tts_model": "fishaudio-elaina",
                    "llm": {"task_models": {"ask_video": "gemini"}},
                    "tts": {"task_models": {"voiceover_generation": "edge-default"}},
                }
            }
        )

        assert cfg.llm_model == "cch"
        assert cfg.tts_model == "fishaudio-elaina"
        assert cfg.llm_task_models == {"ask_video": "gemini"}
        assert cfg.tts_task_models == {"voiceover_generation": "edge-default"}

    @pytest.mark.unit
    def test_from_dict_reads_camel_case_nested_ai_models(self) -> None:
        cfg = ContentConfig.from_dict(
            {
                "ai": {
                    "llmModel": "cch",
                    "ttsModel": "fishaudio-elaina",
                    "llm": {"taskModels": {"ask_video": "gemini"}},
                    "tts": {"taskModels": {"voiceover_generation": "edge-default"}},
                }
            }
        )

        assert cfg.llm_model == "cch"
        assert cfg.tts_model == "fishaudio-elaina"
        assert cfg.llm_task_models == {"ask_video": "gemini"}
        assert cfg.tts_task_models == {"voiceover_generation": "edge-default"}
