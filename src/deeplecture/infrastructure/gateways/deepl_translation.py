"""
DeepL translation gateway.

Implements TranslationProviderProtocol using the DeepL Free/Pro API.
Requires a DeepL API key configured via ``ReadAloudConfig.deepl.auth_key``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.config.settings import DeepLConfig

logger = logging.getLogger(__name__)

# ISO 639-1 → DeepL target language codes
_LANG_MAP: dict[str, str] = {
    "en": "EN-US",
    "zh": "ZH-HANS",
    "ja": "JA",
    "ko": "KO",
    "de": "DE",
    "fr": "FR",
    "es": "ES",
    "pt": "PT-BR",
    "ru": "RU",
    "it": "IT",
    "nl": "NL",
    "pl": "PL",
    "tr": "TR",
    "ar": "AR",
}


def _to_deepl_lang(lang: str) -> str:
    """Convert ISO 639-1 language code to DeepL format."""
    return _LANG_MAP.get(lang.lower(), lang.upper())


class DeepLTranslator:
    """DeepL Free/Pro API translation gateway."""

    def __init__(self, config: DeepLConfig) -> None:
        self._translator = None
        if config.auth_key:
            try:
                import deepl

                self._translator = deepl.Translator(config.auth_key)
                logger.info("DeepL translator initialized")
            except ImportError:
                logger.warning("deepl package not installed. Install with: pip install deepl")
            except Exception:
                logger.exception("Failed to initialize DeepL translator")

    def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> str:
        """Translate a single text string."""
        if not self._translator or not text.strip():
            return text

        try:
            result = self._translator.translate_text(
                text,
                target_lang=_to_deepl_lang(target_lang),
                source_lang=_to_deepl_lang(source_lang) if source_lang else None,
            )
            return str(result)
        except Exception:
            logger.exception("DeepL translation failed for text (len=%d)", len(text))
            return text  # Graceful degradation: return original

    def translate_batch(self, texts: list[str], target_lang: str, source_lang: str | None = None) -> list[str]:
        """Translate multiple texts in a single request."""
        if not self._translator or not texts:
            return list(texts)

        try:
            results = self._translator.translate_text(
                texts,
                target_lang=_to_deepl_lang(target_lang),
                source_lang=_to_deepl_lang(source_lang) if source_lang else None,
            )
            return [str(r) for r in results]
        except Exception:
            logger.exception("DeepL batch translation failed for %d texts", len(texts))
            return list(texts)  # Graceful degradation

    def is_available(self) -> bool:
        """Check if DeepL is configured and ready."""
        return self._translator is not None
