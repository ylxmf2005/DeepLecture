"""
Text-to-Speech (TTS) domain package.

Currently exposes:
- TTS: abstract base interface for TTS providers.
- TTSFactory: factory that creates TTS implementations based on config.
"""

from .tts_factory import TTS, TTSFactory, TTSRegistry

__all__ = ["TTS", "TTSFactory", "TTSRegistry"]
