"""Unit tests for prompt template definition validation."""

import pytest

from deeplecture.use_cases.prompts.template_definitions import (
    PromptTemplateDefinition,
    validate_prompt_template_definition,
)


class TestPromptTemplateValidation:
    @pytest.mark.unit
    def test_valid_template_passes(self) -> None:
        template = PromptTemplateDefinition(
            func_id="ask_video",
            impl_id="concise_v1",
            name="Concise",
            description="Short answers",
            system_template="You are concise. {language}",
            user_template="Question: {question}",
        )

        errors = validate_prompt_template_definition(template)
        assert errors == []

    @pytest.mark.unit
    def test_unknown_placeholder_fails(self) -> None:
        template = PromptTemplateDefinition(
            func_id="ask_video",
            impl_id="concise_v1",
            name="Concise",
            description=None,
            system_template="You are concise. {unknown_token}",
            user_template="Question: {question}",
        )

        errors = validate_prompt_template_definition(template)
        assert any("Unknown placeholders" in err for err in errors)

    @pytest.mark.unit
    def test_missing_required_placeholder_fails(self) -> None:
        template = PromptTemplateDefinition(
            func_id="ask_video",
            impl_id="concise_v1",
            name="Concise",
            description=None,
            system_template="You are concise.",
            user_template="Only context: {context_block}",
        )

        errors = validate_prompt_template_definition(template)
        assert any("Missing required placeholders" in err for err in errors)
