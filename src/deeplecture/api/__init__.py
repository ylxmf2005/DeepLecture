"""
Per-domain route registration for the Flask app.

Each module exposes a `register_<domain>_routes(app)` function that
attaches its endpoints to the provided Flask application instance.
"""

from flask import Flask

from .ask_routes import register_ask_routes
from .cheatsheet_routes import register_cheatsheet_routes
from .config_routes import register_config_routes
from .content_routes import register_content_routes
from .live2d_routes import register_live2d_routes
from .note_routes import register_note_routes
from .slide_routes import register_slide_routes
from .task_routes import register_task_routes
from .timeline_routes import register_timeline_routes
from .voiceover_routes import register_voiceover_routes


def register_routes(
    app: Flask,
    *,
    task_manager=None,
    sse_manager=None,
    content_service=None,
    slide_lecture_service=None,
    subtitle_service=None,
) -> None:
    """Register all API endpoint groups on the given Flask app."""
    if content_service is None:
        raise ValueError("content_service is required for route registration")

    register_content_routes(
        app,
        content_service=content_service,  # Unified content API (videos + slides)
        slide_service=slide_lecture_service,
        subtitle_service=subtitle_service,
        task_manager=task_manager,
    )
    register_voiceover_routes(app, content_service=content_service, task_manager=task_manager)
    register_timeline_routes(app, task_manager=task_manager, content_service=content_service)
    register_slide_routes(
        app,
        content_service=content_service,
        slide_lecture_service=slide_lecture_service,
        task_manager=task_manager,
    )
    register_ask_routes(app, content_service=content_service)
    register_note_routes(app, task_manager=task_manager, content_service=content_service)
    register_cheatsheet_routes(app, task_manager=task_manager, content_service=content_service)
    register_config_routes(app)
    register_live2d_routes(app)
    register_task_routes(app, task_manager=task_manager, sse_manager=sse_manager)
