"""Unit tests for global config sparse merge helper."""

import pytest

from deeplecture.presentation.api.routes.global_config import _merge_sparse


class TestGlobalConfigMerge:
    @pytest.mark.unit
    def test_partial_patch_keeps_unrelated_fields(self) -> None:
        existing = {
            "language": {"original": "en", "translated": "zh"},
            "ai": {"llm_model": "cch"},
        }
        incoming = {"language": {"translated": "ja"}}

        merged = _merge_sparse(existing, incoming)

        assert merged["language"]["original"] == "en"
        assert merged["language"]["translated"] == "ja"
        assert merged["ai"]["llm_model"] == "cch"

    @pytest.mark.unit
    def test_null_value_clears_field(self) -> None:
        existing = {
            "ai": {
                "llm_model": "cch",
                "tts_model": "voice",
            }
        }
        incoming = {"ai": {"llm_model": None}}

        merged = _merge_sparse(existing, incoming)

        assert "llm_model" not in merged["ai"]
        assert merged["ai"]["tts_model"] == "voice"

    @pytest.mark.unit
    def test_replace_dict_paths_for_task_models_and_prompts(self) -> None:
        existing = {
            "ai": {
                "prompts": {"ask_video": "default", "quiz_generation": "default"},
                "llm": {"task_models": {"ask_video": "cch", "note_generation": "cch"}},
                "tts": {"task_models": {"voiceover_generation": "voice-a", "video_generation": "voice-a"}},
            }
        }
        incoming = {
            "ai": {
                "prompts": {"ask_video": "concise"},
                "llm": {"task_models": {"ask_video": "gemini"}},
                "tts": {"task_models": {"voiceover_generation": "voice-b"}},
            }
        }

        merged = _merge_sparse(existing, incoming)

        assert merged["ai"]["prompts"] == {"ask_video": "concise"}
        assert merged["ai"]["llm"]["task_models"] == {"ask_video": "gemini"}
        assert merged["ai"]["tts"]["task_models"] == {"voiceover_generation": "voice-b"}

    @pytest.mark.unit
    def test_replace_dict_paths_supports_camel_case_task_models(self) -> None:
        existing = {
            "ai": {
                "llm": {"taskModels": {"ask_video": "cch", "note_generation": "cch"}},
                "tts": {"taskModels": {"voiceover_generation": "voice-a", "video_generation": "voice-a"}},
            }
        }
        incoming = {
            "ai": {
                "llm": {"taskModels": {"ask_video": "gemini"}},
                "tts": {"taskModels": {"voiceover_generation": "voice-b"}},
            }
        }

        merged = _merge_sparse(existing, incoming)

        assert merged["ai"]["llm"]["taskModels"] == {"ask_video": "gemini"}
        assert merged["ai"]["tts"]["taskModels"] == {"voiceover_generation": "voice-b"}
