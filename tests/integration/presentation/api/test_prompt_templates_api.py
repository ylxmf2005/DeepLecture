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

    @pytest.mark.integration
    def test_update_prompt_template_clears_optional_fields(self, client, mock_container: MagicMock) -> None:
        existing = PromptTemplateDefinition(
            func_id="ask_video",
            impl_id="concise_v1",
            name="Concise",
            description="Short answers",
            system_template="You are concise.",
            user_template="Question: {question}",
            source="custom",
        )

        mock_container.prompt_template_storage = MagicMock()
        mock_container.prompt_template_storage.get_template.return_value = existing
        mock_container.prompt_template_storage.upsert_template.side_effect = lambda template: template
        mock_container.refresh_prompt_registry = MagicMock()

        response = client.put(
            "/api/prompt-templates/ask_video/concise_v1",
            json={
                "name": "Concise",
                "description": "",
                "system_template": "You are concise.",
                "user_template": None,
            },
        )

        assert response.status_code == 200
        assert response.json["success"] is True
        assert response.json["data"]["description"] is None
        assert response.json["data"]["system_template"] == "You are concise."
        assert response.json["data"]["user_template"] == ""
        mock_container.refresh_prompt_registry.assert_called_once()

    @pytest.mark.integration
    def test_delete_prompt_template_returns_conflict_when_selected(self, client, mock_container: MagicMock) -> None:
        mock_container.global_config_storage = MagicMock()
        mock_container.global_config_storage.load.return_value = MagicMock(prompts={"ask_video": "concise_v1"})
        mock_container.prompt_template_storage = MagicMock()

        response = client.delete("/api/prompt-templates/ask_video/concise_v1")

        assert response.status_code == 409
        assert response.json["success"] is False
        assert response.json["code"] == "CONFLICT"
        mock_container.prompt_template_storage.delete_template.assert_not_called()

    @pytest.mark.integration
    def test_get_prompt_template_text_success(self, client, mock_container: MagicMock) -> None:
        mock_container.prompt_registry = MagicMock()
        mock_container.prompt_registry.list_func_ids.return_value = ["ask_video"]
        mock_container.prompt_registry.list_implementations.return_value = [
            MagicMock(impl_id="default"),
            MagicMock(impl_id="concise_v1"),
        ]
        mock_container.prompt_registry.get_template_texts.return_value = {
            "system_template": "You are concise.",
            "user_template": "Question: {question}",
        }

        response = client.get("/api/prompt-templates/ask_video/concise_v1/text")

        assert response.status_code == 200
        assert response.json["success"] is True
        assert response.json["data"]["system_template"] == "You are concise."
        assert response.json["data"]["user_template"] == "Question: {question}"

    @pytest.mark.integration
    def test_get_prompt_template_text_unknown_impl_returns_not_found(self, client, mock_container: MagicMock) -> None:
        mock_container.prompt_registry = MagicMock()
        mock_container.prompt_registry.list_func_ids.return_value = ["ask_video"]
        mock_container.prompt_registry.list_implementations.return_value = [
            MagicMock(impl_id="default"),
        ]

        response = client.get("/api/prompt-templates/ask_video/missing_impl/text")

        assert response.status_code == 404
        assert response.json["success"] is False
        assert "Template not found" in response.json["error"]
        mock_container.prompt_registry.get_template_texts.assert_not_called()
