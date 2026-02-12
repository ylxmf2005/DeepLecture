"""Unit tests for shared subtitle language selection helpers."""

from __future__ import annotations

import pytest

from deeplecture.use_cases.shared.subtitle import build_subtitle_language_candidates


class TestBuildSubtitleLanguageCandidates:
    """Tests for subtitle language candidate ordering."""

    @pytest.mark.unit
    def test_prefers_requested_base_language_with_enhanced_first(self) -> None:
        available = ["en_enhanced", "en", "zh_enhanced", "zh"]

        result = build_subtitle_language_candidates(available, preferred_base_language="zh")

        assert result[:2] == ["zh_enhanced", "zh"]

    @pytest.mark.unit
    def test_falls_back_to_priority_order_when_preferred_missing(self) -> None:
        available = ["en", "en_enhanced", "ja"]

        result = build_subtitle_language_candidates(available, preferred_base_language="zh")

        assert result == ["en_enhanced", "en", "ja"]

    @pytest.mark.unit
    def test_uses_priority_order_when_no_preference(self) -> None:
        available = ["zh", "en", "zh_enhanced", "en_enhanced"]

        result = build_subtitle_language_candidates(available, preferred_base_language=None)

        assert result == ["en_enhanced", "en", "zh_enhanced", "zh"]
