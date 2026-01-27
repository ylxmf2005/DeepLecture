"""Unit tests for LLM Markdown normalization."""

import pytest


class TestNormalizeLlmMarkdown:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (
                "解释**栈溢出 (Stack Overflow) 攻击的核心原理，特别是如何通过覆盖返回地址 (Return Address) **来劫持程序的执行流程。",
                "解释**栈溢出 (Stack Overflow) 攻击的核心原理，特别是如何通过覆盖返回地址 (Return Address)**来劫持程序的执行流程。",
            ),
            ("A ** B ** C", "A **B** C"),
            ("A **B** C", "A **B** C"),
            (r"\*\*Bold\*\*", "**Bold**"),
            ("Unmatched **bold", "Unmatched **bold"),
            ("**foo \nbar**", "**foo \nbar**"),
        ],
    )
    def test_trims_whitespace_inside_bold_markers(self, text: str, expected: str) -> None:
        from deeplecture.use_cases.shared.prompt_safety import normalize_llm_markdown

        assert normalize_llm_markdown(text) == expected
