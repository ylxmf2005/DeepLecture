"""
Subtitle-related domain logic.

Public facade for commonly used subtitle components.

Currently exposes:
- SubtitleEnhanceTranslator: high-level service for enhancing & translating SRT
  subtitles with an LLM.
- WhisperEngine: default Whisper-based subtitle generator.
"""

from .enhance_translator import SubtitleEnhanceTranslator
from .whisper_engine import (
    MockSubtitleEngine,
    SubtitleEngine,
    WhisperEngine,
    get_default_subtitle_engine,
)

__all__ = [
    "SubtitleEnhanceTranslator",
    "SubtitleEngine",
    "WhisperEngine",
    "MockSubtitleEngine",
    "get_default_subtitle_engine",
]
