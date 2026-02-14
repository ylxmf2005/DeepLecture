"""Integration tests for prompt template routes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deeplecture.use_cases.prompts.template_definitions import PromptTemplateDefinition


class TestPromptTemplatesAPI:
    @pytest.mark.integration
    def test_list_prompt_templates(self, client, mock_container: MagicMock) -> None:
        mock_container.prompt_template_storage = MagicMock()
        mock_container.prompt_template_storage.list_templates.return_value = [
            PromptTemplateDefinition(
                func_id="ask_video",
                impl_id="concise_v1",
                name="Concise",
                description=None,
                system_template="",
                user_template="Question: {question}",
            )
        ]

        response = client.get("/api/prompt-templates")

        assert response.status_code == 200
        assert response.json["success"] is True
        assert response.json["data"]["templates"][0]["func_id"] == "ask_video"

    @pytest.mark.integration
    def test_create_prompt_template_success(self, client, mock_container: MagicMock) -> None:
        mock_container.prompt_template_storage = MagicMock()
        mock_container.prompt_template_storage.get_template.return_value = None
        mock_container.prompt_template_storage.upsert_template.side_effect = lambda template: template
        mock_container.prompt_registry = MagicMock()
        mock_container.prompt_registry.list_func_ids.return_value = ["ask_video"]
        mock_container.refresh_prompt_registry = MagicMock()

        response = client.post(
            "/api/prompt-templates",
            json={
                "func_id": "ask_video",
                "impl_id": "concise_v1",
                "name": "Concise",
                "user_template": "Question: {question}",
            },
        )

        assert response.status_code == 201
        assert response.json["success"] is True
        assert response.json["data"]["impl_id"] == "concise_v1"
        mock_container.refresh_prompt_registry.assert_called_once()

    @pytest.mark.integration
    def test_create_prompt_template_rejects_unknown_placeholder(self, client, mock_container: MagicMock) -> None:
        mock_container.prompt_template_storage = MagicMock()
        mock_container.prompt_registry = MagicMock()
        mock_container.prompt_registry.list_func_ids.return_value = ["ask_video"]

        response = client.post(
            "/api/prompt-templates",
            json={
                "func_id": "ask_video",
                "impl_id": "concise_v1",
                "name": "Concise",
                "user_template": "Question: {bad_token}",
            },
        )

        assert response.status_code == 400
        assert response.json["success"] is False
        assert "Unknown placeholders" in response.json["error"]
