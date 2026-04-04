"""Content metadata CRUD routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import bad_request, handle_errors, not_found, success
from deeplecture.presentation.api.shared.validation import validate_content_id, validate_title

if TYPE_CHECKING:
    from datetime import datetime

    from flask import Response

bp = Blueprint("content", __name__)


@bp.route("/list", methods=["GET"])
@handle_errors
def list_content() -> Response:
    """List all content items, optionally filtered by project."""
    project_id = request.args.get("project_id") or None
    container = get_container()
    items = container.content_usecase.list_content(project_id=project_id)
    for item in items:
        _reconcile_stale_processing(item, container)
    content_list = [_serialize_content_item(item) for item in items]
    return success({"content": content_list, "count": len(content_list)})


@bp.route("/<content_id>", methods=["GET"])
@handle_errors
def get_content(content_id: str) -> Response:
    """Get content metadata by ID."""
    content_id = validate_content_id(content_id)
    container = get_container()
    metadata = container.content_usecase.get_content(content_id)
    _reconcile_stale_processing(metadata, container)
    return success(_serialize_content_item(metadata))


@bp.route("/<content_id>/rename", methods=["POST"])
@handle_errors
def rename_content(content_id: str) -> Response:
    """Rename content."""
    content_id = validate_content_id(content_id)
    data = request.get_json() or {}
    new_name = validate_title(data.get("new_name"), field_name="new_name", required=True)

    container = get_container()
    metadata = container.content_usecase.rename_content(content_id, new_name)

    return success(
        {
            "id": metadata.id,
            "filename": metadata.original_filename,
            "message": "Content renamed successfully",
        }
    )


@bp.route("/<content_id>/project", methods=["PATCH"])
@handle_errors
def update_content_project(content_id: str) -> Response:
    """Assign or remove project for a content item."""
    content_id = validate_content_id(content_id)
    data = request.get_json() or {}
    if "project_id" not in data:
        return bad_request("project_id field is required (use null to remove)")

    project_id = data["project_id"]
    if project_id is not None and not isinstance(project_id, str):
        return bad_request("project_id must be a string or null")

    container = get_container()
    from deeplecture.use_cases.project import ProjectNotFoundError

    try:
        updated = container.project_usecase.assign_content(content_id, project_id)
    except ProjectNotFoundError:
        return not_found(f"Project not found: {project_id}")
    if not updated:
        return not_found(f"Content not found: {content_id}")
    return success({"id": content_id, "project_id": project_id})


@bp.route("/<content_id>", methods=["DELETE"])
@handle_errors
def delete_content(content_id: str) -> Response:
    """Delete content and all artifacts."""
    content_id = validate_content_id(content_id)
    container = get_container()
    deleted = container.content_usecase.delete_content(content_id)
    if not deleted:
        return not_found(f"Content not found: {content_id}")
    return success({"deleted": True})


def _reconcile_stale_processing(metadata: object, container) -> None:
    """If status is 'processing' but task doesn't exist, update to 'error'.

    Covers all features that track job_id in ContentMetadata.
    Other features (note, voiceover, quiz, cheatsheet, explanation) don't
    have job_id fields in the entity and are handled by their own mechanisms.
    """
    features = [
        ("video", "video_status", "video_job_id"),
        ("subtitle", "subtitle_status", "subtitle_job_id"),
        ("enhance_translate", "enhance_translate_status", "enhance_translate_job_id"),
        ("timeline", "timeline_status", "timeline_job_id"),
    ]
    for feature, status_field, job_field in features:
        status = getattr(metadata, status_field, None)
        job_id = getattr(metadata, job_field, None)
        if status == "processing" and (not job_id or container.task_manager.get_task(job_id) is None):
            container.content_usecase.update_feature_status(metadata.id, feature, "error")
            setattr(metadata, status_field, "error")


def _serialize_content_item(metadata: object) -> dict:
    """Serialize ContentMetadata to API response format."""
    return {
        "id": metadata.id,
        "type": metadata.type,
        "filename": metadata.original_filename,
        "created_at": _format_datetime(metadata.created_at),
        "updated_at": _format_datetime(metadata.updated_at),
        "video_status": _normalize_status(getattr(metadata, "video_status", None)),
        "subtitle_status": _normalize_status(getattr(metadata, "subtitle_status", None)),
        "enhanced_status": _normalize_status(getattr(metadata, "enhance_translate_status", None)),
        "timeline_status": _normalize_status(getattr(metadata, "timeline_status", None)),
        "notes_status": _normalize_status(getattr(metadata, "notes_status", None)),
        "page_count": getattr(metadata, "pdf_page_count", None),
        "source_type": getattr(metadata, "source_type", None),
        "project_id": getattr(metadata, "project_id", None),
        "detected_source_language": getattr(metadata, "detected_source_language", None),
    }


def _normalize_status(status: str | None) -> str:
    """Normalize feature status to standard values."""
    if status is None:
        return "none"
    status_lower = status.lower()
    return status_lower if status_lower in ("none", "processing", "ready", "error") else "none"


def _format_datetime(dt: datetime | None) -> str | None:
    """Format datetime to ISO8601 string."""
    return dt.isoformat() if dt else None
