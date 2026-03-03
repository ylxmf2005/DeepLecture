"""Global prompt template management routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import bad_request, conflict, created, handle_errors, not_found, success
from deeplecture.use_cases.prompts.template_definitions import (
    PromptTemplateDefinition,
    get_placeholder_metadata,
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
            "metadata": get_placeholder_metadata(),
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


@bp.route("/prompt-templates/<func_id>/<impl_id>", methods=["PUT"])
@handle_errors
def update_prompt_template(func_id: str, impl_id: str) -> Response:
    """Update an existing custom prompt template."""
    if impl_id == "default":
        return bad_request("Cannot edit built-in default templates")

    container = get_container()
    existing = container.prompt_template_storage.get_template(func_id, impl_id)
    if not existing:
        return not_found(f"Template not found: {func_id}/{impl_id}")

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return bad_request("Request body must be a JSON object")

    updated = PromptTemplateDefinition(
        func_id=func_id,
        impl_id=impl_id,
        name=str(data.get("name") or existing.name).strip(),
        description=str(data.get("description") or "").strip() or existing.description,
        system_template=str(data.get("system_template")) if "system_template" in data else existing.system_template,
        user_template=str(data.get("user_template")) if "user_template" in data else existing.user_template,
        source=existing.source,
        created_at=existing.created_at,
        updated_at=now_iso_utc(),
        active=True,
    )

    errors = validate_prompt_template_definition(updated)
    if errors:
        return bad_request("; ".join(errors))

    saved = container.prompt_template_storage.upsert_template(updated)
    container.refresh_prompt_registry()
    return success(saved.to_dict())


@bp.route("/prompt-templates/<func_id>/<impl_id>", methods=["DELETE"])
@handle_errors
def delete_prompt_template(func_id: str, impl_id: str) -> Response:
    """Delete a custom prompt template."""
    if impl_id == "default":
        return bad_request("Cannot delete built-in default templates")

    container = get_container()

    # Check if template is selected in global config
    global_config = container.global_config_storage.load()
    if global_config and global_config.prompts:
        selected_impl = global_config.prompts.get(func_id)
        if selected_impl == impl_id:
            return conflict(
                f"Template {func_id}/{impl_id} is currently selected. " "Switch to a different template first."
            )

    deleted = container.prompt_template_storage.delete_template(func_id, impl_id)
    if not deleted:
        return not_found(f"Template not found: {func_id}/{impl_id}")

    container.refresh_prompt_registry()
    return success(None, status=204)


@bp.route("/prompt-templates/<func_id>/<impl_id>/text", methods=["GET"])
@handle_errors
def get_prompt_template_text(func_id: str, impl_id: str) -> Response:
    """Get raw system/user template text for editor pre-filling."""
    container = get_container()
    if func_id not in container.prompt_registry.list_func_ids():
        return not_found(f"Unknown func_id: {func_id}")

    try:
        texts = container.prompt_registry.get_template_texts(func_id, impl_id)
    except ValueError as exc:
        return not_found(str(exc))

    return success(texts)
