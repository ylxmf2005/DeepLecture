"""Project CRUD routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import bad_request, handle_errors, not_found, success
from deeplecture.presentation.api.shared.validation import validate_title, validate_uuid
from deeplecture.use_cases.project import ProjectNotFoundError

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("project", __name__)

MAX_PROJECT_NAME_LENGTH = 100
MAX_PROJECT_DESCRIPTION_LENGTH = 500


def _validate_project_name(name: str | None) -> str:
    """Validate project name: required, 1-100 chars, trimmed."""
    from deeplecture.presentation.api.shared.validation import ValidationError

    if not name:
        raise ValidationError("name is required")
    name = name.strip()
    if not name:
        raise ValidationError("name is required")
    if len(name) > MAX_PROJECT_NAME_LENGTH:
        raise ValidationError(f"name exceeds maximum length ({MAX_PROJECT_NAME_LENGTH})")
    return name


@bp.route("", methods=["GET"])
@handle_errors
def list_projects() -> Response:
    """List all projects."""
    container = get_container()
    projects = container.project_usecase.list_projects()
    return success({"projects": projects, "count": len(projects)})


@bp.route("", methods=["POST"])
@handle_errors
def create_project() -> Response:
    """Create a new project."""
    data = request.get_json() or {}
    name = _validate_project_name(data.get("name"))
    description = validate_title(data.get("description"), field_name="description", default="")
    if len(description) > MAX_PROJECT_DESCRIPTION_LENGTH:
        return bad_request(f"description exceeds maximum length ({MAX_PROJECT_DESCRIPTION_LENGTH})")
    color = (data.get("color") or "").strip()
    icon = (data.get("icon") or "").strip()

    container = get_container()
    project = container.project_usecase.create_project(
        name=name,
        description=description,
        color=color,
        icon=icon,
    )
    return success(_serialize_project(project))


@bp.route("/<project_id>", methods=["PUT"])
@handle_errors
def update_project(project_id: str) -> Response:
    """Update an existing project."""
    project_id = validate_uuid(project_id, field_name="project_id")
    data = request.get_json() or {}

    fields: dict[str, str] = {}
    if "name" in data:
        fields["name"] = _validate_project_name(data["name"])
    if "description" in data:
        desc = validate_title(data.get("description"), field_name="description", default="")
        if len(desc) > MAX_PROJECT_DESCRIPTION_LENGTH:
            return bad_request(f"description exceeds maximum length ({MAX_PROJECT_DESCRIPTION_LENGTH})")
        fields["description"] = desc
    if "color" in data:
        fields["color"] = (data["color"] or "").strip()
    if "icon" in data:
        fields["icon"] = (data["icon"] or "").strip()

    if not fields:
        return bad_request("No fields to update")

    container = get_container()
    try:
        project = container.project_usecase.update_project(project_id, **fields)
    except ProjectNotFoundError:
        return not_found(f"Project not found: {project_id}")
    return success(_serialize_project(project))


@bp.route("/<project_id>", methods=["DELETE"])
@handle_errors
def delete_project(project_id: str) -> Response:
    """Delete a project (content becomes ungrouped)."""
    project_id = validate_uuid(project_id, field_name="project_id")
    container = get_container()
    deleted = container.project_usecase.delete_project(project_id)
    if not deleted:
        return not_found(f"Project not found: {project_id}")
    return success({"deleted": True})


def _serialize_project(project: object) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "color": project.color,
        "icon": project.icon,
        "created_at": project.created_at.isoformat() if hasattr(project, "created_at") else None,
        "updated_at": project.updated_at.isoformat() if hasattr(project, "updated_at") else None,
    }
