"""Flask Application Factory."""

from __future__ import annotations

import atexit

from flask import Flask
from flask_cors import CORS

from deeplecture.presentation.api.shared import init_rate_limiter, register_error_handlers


def create_app(*, start_workers: bool = True) -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)

    CORS(
        app,
        resources={
            r"/*": {
                "origins": "*",
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
            }
        },
    )

    register_error_handlers(app)
    init_rate_limiter(app)
    _register_blueprints(app)

    if start_workers:
        _start_worker_pool()

    return app


def _start_worker_pool() -> None:
    """Start background task worker pool and register shutdown hook."""
    from deeplecture.di import get_container

    container = get_container()
    worker_pool = container.worker_pool
    worker_pool.start()

    atexit.register(lambda: worker_pool.shutdown(wait=True, timeout=5.0))


def _register_blueprints(app: Flask) -> None:
    """Register all API blueprints under /api prefix."""
    from deeplecture.presentation.api.routes import (
        config_bp,
        content_bp,
        conversation_bp,
        explanation_bp,
        fact_verification_bp,
        generation_bp,
        live2d_bp,
        media_bp,
        note_bp,
        screenshot_bp,
        subtitle_bp,
        summaries_bp,
        task_bp,
        timeline_bp,
        upload_bp,
        voiceover_bp,
    )

    app.register_blueprint(config_bp, url_prefix="/api")
    app.register_blueprint(content_bp, url_prefix="/api/content")
    app.register_blueprint(conversation_bp, url_prefix="/api/conversations")
    app.register_blueprint(explanation_bp, url_prefix="/api/content")
    app.register_blueprint(fact_verification_bp, url_prefix="/api/fact-verification")
    app.register_blueprint(generation_bp, url_prefix="/api/content")
    app.register_blueprint(live2d_bp, url_prefix="/api/live2d")
    app.register_blueprint(media_bp, url_prefix="/api/content")
    app.register_blueprint(note_bp, url_prefix="/api/notes")
    app.register_blueprint(screenshot_bp, url_prefix="/api/content")
    app.register_blueprint(subtitle_bp, url_prefix="/api/subtitle")
    app.register_blueprint(summaries_bp, url_prefix="/api/summaries")
    app.register_blueprint(task_bp, url_prefix="/api/task")
    app.register_blueprint(timeline_bp, url_prefix="/api/timeline")
    app.register_blueprint(upload_bp, url_prefix="/api/content")
    app.register_blueprint(voiceover_bp, url_prefix="/api")
