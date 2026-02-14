"""Global prompt template management routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import bad_request, created, handle_errors, success
from deeplecture.use_cases.prompts.template_definitions import (
    PromptTemplateDefinition,
    list_template_func_ids,
    now_iso_utc,
    validate_prompt_template_definition,
)

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("prompt_templates", __name__)


@bp.route("/prompt-templates", methods=["GET"])
@handle_errors
def list_prompt_templates() -> Response:
    """List active global custom prompt templates."""
    container = get_container()
    templates = container.prompt_template_storage.list_templates()
    return success(
        {
            "templates": [t.to_dict() for t in templates],
            "func_ids": list_template_func_ids(),
        }
    )


@bp.route("/prompt-templates", methods=["POST"])
@handle_errors
def create_prompt_template() -> Response:
    """Create a global custom prompt template."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return bad_request("Request body must be a JSON object")

    func_id = str(data.get("func_id") or "").strip()
    impl_id = str(data.get("impl_id") or "").strip()
    name = str(data.get("name") or "").strip()
    description = str(data.get("description") or "").strip() or None
    system_template = str(data.get("system_template") or "")
    user_template = str(data.get("user_template") or "")

    template = PromptTemplateDefinition(
        func_id=func_id,
        impl_id=impl_id,
        name=name,
        description=description,
        system_template=system_template,
        user_template=user_template,
        source="custom",
        created_at=now_iso_utc(),
        updated_at=now_iso_utc(),
        active=True,
    )

    errors = validate_prompt_template_definition(template)
    if errors:
        return bad_request("; ".join(errors))

    container = get_container()
    if func_id not in container.prompt_registry.list_func_ids():
        return bad_request(f"Unknown func_id: {func_id}")

    if container.prompt_template_storage.get_template(func_id, impl_id):
        return bad_request(f"Template already exists: {func_id}/{impl_id}")

    saved = container.prompt_template_storage.upsert_template(template)
    container.refresh_prompt_registry()
    return created(saved.to_dict())
