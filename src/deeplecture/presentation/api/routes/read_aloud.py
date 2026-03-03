"""Read-aloud API routes.

Provides:
- GET /stream/<content_id> — SSE stream of read-aloud signals
- GET /audio/<content_id>/<sentence_key> — REST endpoint for individual MP3 audio
"""

from __future__ import annotations

import logging
import threading

from flask import Blueprint, request, stream_with_context
from flask import Response as FlaskResponse

from deeplecture.di import get_container
from deeplecture.presentation.api.shared.validation import validate_content_id
from deeplecture.use_cases.dto.read_aloud import ReadAloudRequest

bp = Blueprint("read_aloud", __name__)
log = logging.getLogger(__name__)


@bp.route("/stream/<content_id>", methods=["GET"])
def stream_read_aloud(content_id: str) -> FlaskResponse:
    """SSE stream: pushes sentence-ready signals for the read-aloud pipeline."""
    content_id = validate_content_id(content_id)

    target_language = request.args.get("target_language", "en")
    source_language = request.args.get("source_language")
    tts_model = request.args.get("tts_model")
    start_paragraph = int(request.args.get("start_paragraph", "0"))

    container = get_container()

    req = ReadAloudRequest(
        content_id=content_id,
        target_language=target_language,
        source_language=source_language or None,
        tts_model=tts_model or None,
        start_paragraph=start_paragraph,
    )

    # Launch generation in a background daemon thread
    thread = threading.Thread(
        target=container.read_aloud_usecase.generate_stream,
        args=(req,),
        daemon=True,
        name=f"read-aloud-{content_id}",
    )
    thread.start()

    # Stream SSE events from the read-aloud channel
    channel = f"read_aloud:{content_id}"

    return FlaskResponse(
        stream_with_context(
            container.event_publisher.stream(
                channel,
                timeout=30.0,
                send_initial=True,
                retry_ms=3000,
            )
        ),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/audio/<content_id>/<sentence_key>", methods=["GET"])
def get_sentence_audio(content_id: str, sentence_key: str) -> FlaskResponse:
    """REST endpoint: retrieve a single sentence's MP3 audio from cache."""
    content_id = validate_content_id(content_id)

    container = get_container()
    audio_data = container.read_aloud_cache.load_audio(content_id, sentence_key)

    if not audio_data:
        return FlaskResponse("Audio not found", status=404)

    return FlaskResponse(
        audio_data,
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Length": str(len(audio_data)),
        },
    )
