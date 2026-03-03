"""Translation provider protocol."""

from __future__ import annotations

from typing import Protocol


class TranslationProviderProtocol(Protocol):
    """
    Contract for text translation services.

    Implementations: DeepLTranslator
    """

    def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> str:
        """
        Translate a single text string.

        Args:
            text: Text to translate
            target_lang: Target language code (ISO 639-1, e.g. "en", "zh")
            source_lang: Source language code (None = auto-detect)

        Returns:
            Translated text
        """
        ...

    def translate_batch(self, texts: list[str], target_lang: str, source_lang: str | None = None) -> list[str]:
        """
        Translate multiple texts in a single request.

        Args:
            texts: List of texts to translate
            target_lang: Target language code
            source_lang: Source language code (None = auto-detect)

        Returns:
            List of translated texts (same order as input)
        """
        ...

    def is_available(self) -> bool:
        """
        Check if the translation service is configured and available.

        Returns:
            True if service can be used, False otherwise
        """
        ...
