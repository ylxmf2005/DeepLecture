"""
Flask server for CourseSubtitle application.

Phase 2 refactor: application factory is pure and side-effect free.
Workers start only when explicitly requested (CLI/env).
"""

from __future__ import annotations

import threading
from typing import Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

from deeplecture.api import register_routes
from deeplecture.app_context import AppContext, get_app_context
from deeplecture.config.config import get_settings
from deeplecture.infra.sse_manager import SSEManager
from deeplecture.services.content_service import get_default_content_service
from deeplecture.services.slide_lecture_service import SlideLectureService
from deeplecture.services.subtitle_service import SubtitleService
from deeplecture.workers import TaskManager

# Guard to avoid spawning duplicate workers in-process.
_worker_lock = threading.Lock()


def _should_start_worker(flag: Optional[bool]) -> bool:
    if flag is not None:
        return bool(flag)
    return get_settings().server.run_worker


def _start_worker_once(task_manager: TaskManager) -> threading.Thread:
    from deeplecture.workers.worker import start_worker  # Local import to avoid import-time side effects

    with _worker_lock:
        existing = getattr(task_manager, "_worker_thread", None)
        if existing and getattr(existing, "is_alive", lambda: False)():
            return existing  # type: ignore[return-value]
        thread = start_worker(task_manager)
        # Attach to task_manager so repeated create_app calls don't spawn more.
        setattr(task_manager, "_worker_thread", thread)
        return thread


def create_app(
    *,
    start_worker: Optional[bool] = None,
    app_context: Optional[AppContext] = None,
) -> Flask:
    """
    Application factory used by local scripts and WSGI servers.

    All heavy initialization (config, logging, factories) is explicit and
    idempotent. No work is performed at import time.
    """
    ctx = app_context or get_app_context()
    ctx.init_all()

    # Run pending migrations before starting services
    from scripts.migrations import run_migrations
    run_migrations()

    sse_manager = SSEManager()
    task_manager = TaskManager(sse_manager)
    content_service = get_default_content_service(task_manager=task_manager)
    slide_lecture_service = SlideLectureService(
        content_service=content_service,
        task_manager=task_manager,
    )
    subtitle_service = SubtitleService(
        content_service=content_service,
        task_manager=task_manager,
    )

    settings = get_settings()
    server_cfg = settings.server
    rate_limits_cfg = settings.rate_limits

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = server_cfg.max_upload_bytes

    CORS(
        app,
        resources={
        r"/api/*": {
            "origins": server_cfg.cors_allow_origins,
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization", "X-API-Key"],
            "supports_credentials": True,
        },
        },
    )

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[
            f"{rate_limits_cfg.default_per_day} per day",
            f"{rate_limits_cfg.default_per_hour} per hour",
        ],
        storage_uri=server_cfg.rate_limit_storage_uri,
    )
    limiter.init_app(app)
    app.extensions["limiter"] = limiter

    api_key = server_cfg.api_key

    @app.before_request
    def _require_api_key():
        if not api_key:
            return None

        path = request.path or ""
        if not path.startswith("/api/"):
            return None

        if request.endpoint in {"static"}:
            return None

        incoming_key = request.headers.get("X-API-Key")
        if incoming_key != api_key:
            return jsonify({"error": "Unauthorized"}), 401
        return None

    @app.after_request
    def _apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response

    @app.errorhandler(Exception)
    def _handle_exceptions(err):
        status_code = getattr(err, "code", 500)
        if isinstance(err, HTTPException):
            status_code = err.code or status_code

        if app.config.get("ENV") == "production":
            return jsonify({"error": "Internal server error"}), 500 if status_code < 400 else status_code

        return (
            jsonify({"error": str(err), "type": type(err).__name__}),
            status_code if status_code >= 400 else 500,
        )

    register_routes(
        app,
        task_manager=task_manager,
        sse_manager=sse_manager,
        content_service=content_service,
        slide_lecture_service=slide_lecture_service,
        subtitle_service=subtitle_service,
    )

    if _should_start_worker(start_worker):
        _start_worker_once(task_manager)

    # Expose references for testing/CLI utilities.
    app.config["task_manager"] = task_manager
    app.config["sse_manager"] = sse_manager
    app.config["app_context"] = ctx
    app.config["content_service"] = content_service
    app.config["slide_lecture_service"] = slide_lecture_service
    app.config["subtitle_service"] = subtitle_service

    return app


def main():
    """CLI entry point."""
    app = create_app(start_worker=_should_start_worker(None))
    app.run(debug=True, use_reloader=False, port=11393, threaded=True)


if __name__ == "__main__":
    main()
