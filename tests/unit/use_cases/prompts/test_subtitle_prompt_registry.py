"""Unit tests for subtitle prompt registry builders."""

from __future__ import annotations

import pytest

from deeplecture.use_cases.prompts.registry import SubtitleBackgroundBuilder


class TestSubtitleBackgroundBuilder:
    """Tests for subtitle background prompt builder compatibility."""

    @pytest.mark.unit
    def test_build_accepts_transcript_text_key(self) -> None:
        """Builder should support the canonical transcript_text argument."""
        builder = SubtitleBackgroundBuilder("default", "Default")

        spec = builder.build(transcript_text="hello world")

        assert "Transcript:\nhello world" in spec.user_prompt
        assert spec.system_prompt is not None

    @pytest.mark.unit
    def test_build_rejects_legacy_transcript_key(self) -> None:
        """Builder should reject legacy transcript key to enforce one API."""
        builder = SubtitleBackgroundBuilder("default", "Default")

        with pytest.raises(KeyError, match="transcript_text"):
            builder.build(transcript="legacy text")

    @pytest.mark.unit
    def test_build_raises_when_transcript_missing(self) -> None:
        """Builder should raise a clear key error when transcript is missing."""
        builder = SubtitleBackgroundBuilder("default", "Default")

        with pytest.raises(KeyError, match="transcript_text"):
            builder.build()
