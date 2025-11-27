from __future__ import annotations

import os
from pathlib import Path
from typing import List, TypedDict

import logging
from flask import Flask, jsonify, send_from_directory, abort

from deeplecture.api.error_utils import api_success

logger = logging.getLogger(__name__)

LIVE2D_MODELS_DIR = Path(__file__).parent.parent / "live2d_models"


class Live2DModel(TypedDict):
    name: str
    path: str


def _discover_models() -> List[Live2DModel]:
    """
    Scan live2d_models directory for available models.
    Each model folder should contain a .model3.json file.
    """
    models: List[Live2DModel] = []

    if not LIVE2D_MODELS_DIR.exists():
        logger.warning("Live2D models directory not found: %s", LIVE2D_MODELS_DIR)
        return models

    for folder in sorted(LIVE2D_MODELS_DIR.iterdir()):
        if not folder.is_dir():
            continue

        model_files = list(folder.glob("*.model3.json"))
        if not model_files:
            continue

        model_file = model_files[0]
        model_name = model_file.stem.replace(".model3", "")

        models.append({
            "name": model_name,
            "path": f"/api/live2d/models/{folder.name}/{model_file.name}",
        })

    return models


def register_live2d_routes(app: Flask) -> None:
    """Register Live2D-related routes."""

    @app.route("/api/live2d/models", methods=["GET"])
    def list_live2d_models():
        """Return a list of available Live2D models."""
        models = _discover_models()
        return api_success(models)

    @app.route("/api/live2d/models/<path:filepath>", methods=["GET"])
    def serve_live2d_file(filepath: str):
        """Serve Live2D model files from live2d_models directory."""
        if not LIVE2D_MODELS_DIR.exists():
            abort(404)

        full_path = LIVE2D_MODELS_DIR / filepath
        if not full_path.exists():
            abort(404)

        if not full_path.resolve().is_relative_to(LIVE2D_MODELS_DIR.resolve()):
            abort(403)

        return send_from_directory(
            LIVE2D_MODELS_DIR,
            filepath,
            mimetype=_get_mimetype(filepath),
        )


def _get_mimetype(filepath: str) -> str:
    """Return appropriate MIME type for Live2D files."""
    ext = os.path.splitext(filepath)[1].lower()
    mimetypes = {
        ".json": "application/json",
        ".moc3": "application/octet-stream",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    return mimetypes.get(ext, "application/octet-stream")
