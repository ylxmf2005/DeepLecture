"""Bookmark routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import bad_request, created, handle_errors, not_found, success
from deeplecture.presentation.api.shared.validation import (
    validate_content_id,
    validate_title,
    validate_uuid,
)
from deeplecture.use_cases.bookmark import BookmarkNotFoundError
from deeplecture.use_cases.dto.bookmark import CreateBookmarkRequest, UpdateBookmarkRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("bookmarks", __name__)

MAX_NOTE_LENGTH = 50_000


@bp.route("", methods=["GET"])
@handle_errors
def list_bookmarks() -> Response:
    """List all bookmarks for a content item."""
    content_id = validate_content_id(request.args.get("content_id"), field_name="content_id")

    container = get_container()
    result = container.bookmark_usecase.list_bookmarks(content_id)

    return success(result.to_dict())


@bp.route("", methods=["POST"])
@handle_errors
def create_bookmark() -> Response:
    """Create a new bookmark."""
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")

    # Validate timestamp
    raw_timestamp = data.get("timestamp")
    if raw_timestamp is None:
        return bad_request("timestamp is required")
    try:
        timestamp = float(raw_timestamp)
    except (TypeError, ValueError):
        return bad_request("timestamp must be a number")
    if timestamp < 0:
        return bad_request("timestamp must be non-negative")

    title = validate_title(data.get("title"), field_name="title", default="")
    note = data.get("note", "")
    if len(note) > MAX_NOTE_LENGTH:
        return bad_request(f"note exceeds maximum length ({MAX_NOTE_LENGTH})")

    container = get_container()
    req = CreateBookmarkRequest(
        content_id=content_id,
        timestamp=timestamp,
        title=title,
        note=note,
    )
    item = container.bookmark_usecase.create_bookmark(req)

    return created(item.to_dict())


@bp.route("/<bookmark_id>", methods=["PUT"])
@handle_errors
def update_bookmark(bookmark_id: str) -> Response:
    """Update an existing bookmark."""
    bookmark_id = validate_uuid(bookmark_id, field_name="bookmark_id")
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")

    # Build update request — only set fields that are present
    title = None
    if "title" in data:
        title = validate_title(data["title"], field_name="title", default="")

    note = None
    if "note" in data:
        note = data["note"] or ""
        if len(note) > MAX_NOTE_LENGTH:
            return bad_request(f"note exceeds maximum length ({MAX_NOTE_LENGTH})")

    timestamp = None
    if "timestamp" in data:
        try:
            timestamp = float(data["timestamp"])
        except (TypeError, ValueError):
            return bad_request("timestamp must be a number")
        if timestamp < 0:
            return bad_request("timestamp must be non-negative")

    container = get_container()
    req = UpdateBookmarkRequest(
        content_id=content_id,
        bookmark_id=bookmark_id,
        title=title,
        note=note,
        timestamp=timestamp,
    )

    try:
        item = container.bookmark_usecase.update_bookmark(req)
    except BookmarkNotFoundError:
        return not_found(f"Bookmark {bookmark_id} not found")

    return success(item.to_dict())


@bp.route("/<bookmark_id>", methods=["DELETE"])
@handle_errors
def delete_bookmark(bookmark_id: str) -> Response:
    """Delete a bookmark."""
    bookmark_id = validate_uuid(bookmark_id, field_name="bookmark_id")
    content_id = validate_content_id(request.args.get("content_id"), field_name="content_id")

    container = get_container()

    try:
        container.bookmark_usecase.delete_bookmark(content_id, bookmark_id)
    except BookmarkNotFoundError:
        return not_found(f"Bookmark {bookmark_id} not found")

    return success({"deleted": True})
