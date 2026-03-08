"""Unit tests for markdown sentence segmentation."""

from __future__ import annotations

import pytest

from deeplecture.infrastructure.shared.markdown_text_filter import MarkdownTextFilter


class TestMarkdownTextFilter:
    @pytest.mark.unit
    def test_splits_cjk_sentences_without_whitespace(self) -> None:
        text_filter = MarkdownTextFilter(min_sentence_length=1)

        paragraphs = text_filter.filter_to_sentences("句一。句二。句三！")

        assert len(paragraphs) == 1
        assert paragraphs[0].sentences == ["句一。", "句二。", "句三！"]

    @pytest.mark.unit
    def test_splits_latin_sentences_with_whitespace(self) -> None:
        text_filter = MarkdownTextFilter(min_sentence_length=1)

        paragraphs = text_filter.filter_to_sentences("Sentence one. Sentence two? Sentence three!")

        assert len(paragraphs) == 1
        assert paragraphs[0].sentences == ["Sentence one.", "Sentence two?", "Sentence three!"]
