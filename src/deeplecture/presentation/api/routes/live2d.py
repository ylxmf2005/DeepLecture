"""Live2D routes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, abort, send_file

from deeplecture.presentation.api.shared import handle_errors, success

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("live2d", __name__)

LIVE2D_MODELS_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "live2d_models"


def _get_mimetype(filepath: str) -> str:
    """Return appropriate MIME type for Live2D files."""
    ext = os.path.splitext(filepath)[1].lower()
    mimetypes = {
        ".json": "application/json",
        ".png": "image/png",
        ".moc3": "application/octet-stream",
        ".physics3.json": "application/json",
        ".motion3.json": "application/json",
    }
    return mimetypes.get(ext, "application/octet-stream")


@bp.route("/models", methods=["GET"])
@handle_errors
def get_live2d_models() -> Response:
    """Get available Live2D models."""
    models = []

    if not LIVE2D_MODELS_DIR.exists():
        return success({"models": models})

    for folder in sorted(LIVE2D_MODELS_DIR.iterdir()):
        if not folder.is_dir():
            continue

        model_files = list(folder.glob("*.model3.json"))
        if not model_files:
            continue

        model_file = model_files[0]
        model_name = model_file.stem.replace(".model3", "")

        models.append(
            {
                "name": model_name,
                "path": f"/api/live2d/models/{folder.name}/{model_file.name}",
            }
        )

    return success({"models": models})


@bp.route("/models/<path:filepath>", methods=["GET"])
def serve_live2d_file(filepath: str) -> Response:
    """Serve Live2D model files."""
    if not LIVE2D_MODELS_DIR.exists():
        abort(404)

    safe_path = Path(filepath)
    if ".." in safe_path.parts:
        abort(403)

    full_path = LIVE2D_MODELS_DIR / safe_path
    if not full_path.exists() or not full_path.is_file():
        abort(404)

    mimetype = _get_mimetype(filepath)
    response = send_file(full_path, mimetype=mimetype)
    # Enable CORS for WebGL texture loading
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    return response
