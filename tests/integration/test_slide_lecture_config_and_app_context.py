from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from deeplecture.services.slide_lecture_service import SlideLectureService


def test_conf_default_yaml_has_lecture_settings() -> None:
    path = Path("config/conf.default.yaml")
    assert path.exists()

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)

    slides = data.get("slides") or {}
    lecture = slides.get("lecture") or {}
    assert lecture.get("neighbor_images") in {"none", "next", "prev_next", None}
    assert "cleanup_temp" in lecture
    assert "tts_language" in lecture
    # max_rpm is now global at llm.max_rpm and tts.max_rpm, not per-task


def test_get_effective_lecture_config_reads_settings(monkeypatch) -> None:
    import deeplecture.services.slide_lecture_service as lecture_module

    def fake_load_config() -> Dict[str, Any]:
        return {
            "llm": {
                "max_rpm": 90,
            },
            "subtitle": {
                "source_language": "en",
                "translation": {
                    "target_language": "ja",
                },
            },
            "slides": {
                "lecture": {
                    "neighbor_images": "next",
                    "tts_language": "target",
                    "page_break_silence_seconds": 2.5,
                    "cleanup_temp": True,
                }
            },
            "tts": {
                "max_rpm": 60,
            },
        }

    monkeypatch.setattr(lecture_module, "load_config", fake_load_config)

    # Create a mock TTS factory to avoid AppContext initialization
    class _MockTTSFactory:
        def get_tts_for_task(self, task_name: str):
            return object()

    svc = SlideLectureService(
        task_runner=None,
        tts=object(),
        tts_factory=_MockTTSFactory(),
        metadata_storage=None,
        content_service=None,
    )

    cfg = svc._get_effective_lecture_config(
        tts_language="source",
        page_break_silence_seconds=1.5,
    )

    assert cfg["source_language"] == "en"
    assert cfg["target_language"] == "ja"
    assert cfg["neighbor_images"] == "next"
    assert cfg["tts_max_concurrency"] > 0
    assert cfg["tts_language"] in {"source", "target"}
    assert isinstance(cfg["page_break_silence_seconds"], float)
    assert cfg["cleanup_temp"] == True
