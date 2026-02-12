"""Per-content configuration routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.domain.entities.config import ContentConfig
from deeplecture.presentation.api.shared import handle_errors, success
from deeplecture.presentation.api.shared.validation import validate_content_id

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("content_config", __name__)


@bp.route("/<content_id>/config", methods=["GET"])
@handle_errors
def get_content_config(content_id: str) -> Response:
    content_id = validate_content_id(content_id)
    container = get_container()
    config = container.content_config_storage.load(content_id)
    return success(config.to_sparse_dict() if config else {})


@bp.route("/<content_id>/config", methods=["PUT"])
@handle_errors
def put_content_config(content_id: str) -> Response:
    content_id = validate_content_id(content_id)
    payload = request.get_json(silent=True) or {}
    config = ContentConfig.from_dict(payload)
    container = get_container()
    container.content_config_storage.save(content_id, config)
    return success(config.to_sparse_dict())


@bp.route("/<content_id>/config", methods=["DELETE"])
@handle_errors
def delete_content_config(content_id: str) -> Response:
    content_id = validate_content_id(content_id)
    container = get_container()
    container.content_config_storage.delete(content_id)
    return success({"deleted": True})
