"""Unit tests for shared source-language resolution helpers."""

from __future__ import annotations

import pytest

from deeplecture.use_cases.shared.source_language import (
    SourceLanguageResolutionError,
    is_auto_language,
    resolve_source_language,
)


class TestResolveSourceLanguage:
    @pytest.mark.unit
    def test_returns_explicit_language_unchanged(self) -> None:
        assert resolve_source_language("ja", metadata=None) == "ja"

    @pytest.mark.unit
    def test_resolves_auto_from_detected_metadata(self) -> None:
        metadata = type("Metadata", (), {"detected_source_language": "ja"})()

        assert resolve_source_language("auto", metadata=metadata) == "ja"

    @pytest.mark.unit
    def test_raises_when_auto_has_no_detected_language(self) -> None:
        metadata = type("Metadata", (), {"detected_source_language": None})()

        with pytest.raises(SourceLanguageResolutionError, match="Generate subtitles first"):
            resolve_source_language("auto", metadata=metadata)

    @pytest.mark.unit
    def test_identifies_auto_language(self) -> None:
        assert is_auto_language("auto") is True
        assert is_auto_language("ja") is False
