"""Read-aloud API routes.

Provides:
- GET /stream/<content_id> — SSE stream of read-aloud signals
- GET /audio/<content_id>/<sentence_key>?variant_key=... — REST endpoint for individual MP3 audio
- POST /cancel/<content_id>?session_id=... — cancel active read-aloud generation session
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from uuid import uuid4

from flask import Blueprint, request, stream_with_context
from flask import Response as FlaskResponse

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import bad_request, handle_errors, rate_limit, success
from deeplecture.presentation.api.shared.model_resolution import resolve_models_for_task
from deeplecture.presentation.api.shared.validation import (
    validate_content_id,
    validate_positive_int,
    validate_task_id,
)
from deeplecture.use_cases.dto.read_aloud import ReadAloudRequest

bp = Blueprint("read_aloud", __name__)
log = logging.getLogger(__name__)
_VARIANT_RE = re.compile(r"^[a-z0-9]{8,64}$")


@dataclass(slots=True)
class _ActiveRun:
    session_id: str
    cancel_event: threading.Event


_ACTIVE_RUNS: dict[str, _ActiveRun] = {}
_ACTIVE_RUNS_LOCK = threading.RLock()


def _stream_channel(content_id: str, session_id: str) -> str:
    return f"read_aloud:{content_id}:{session_id}"


def _parse_variant_key(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if not value:
        raise ValueError("variant_key is required")
    if not _VARIANT_RE.fullmatch(value):
        raise ValueError("variant_key must match ^[a-z0-9]{8,64}$")
    return value


def _register_active_run(content_id: str, session_id: str, cancel_event: threading.Event) -> None:
    with _ACTIVE_RUNS_LOCK:
        previous = _ACTIVE_RUNS.get(content_id)
        if previous is not None:
            previous.cancel_event.set()
        _ACTIVE_RUNS[content_id] = _ActiveRun(session_id=session_id, cancel_event=cancel_event)


def _clear_active_run(content_id: str, session_id: str) -> None:
    with _ACTIVE_RUNS_LOCK:
        active = _ACTIVE_RUNS.get(content_id)
        if active and active.session_id == session_id:
            _ACTIVE_RUNS.pop(content_id, None)


def _cancel_active_run(content_id: str, session_id: str) -> bool:
    with _ACTIVE_RUNS_LOCK:
        active = _ACTIVE_RUNS.get(content_id)
        if active and active.session_id == session_id:
            active.cancel_event.set()
            return True
    return False


@bp.route("/stream/<content_id>", methods=["GET"])
@handle_errors
@rate_limit("generate")
def stream_read_aloud(content_id: str) -> FlaskResponse:
    """SSE stream: pushes sentence-ready signals for the read-aloud pipeline."""
    content_id = validate_content_id(content_id)

    target_language = request.args.get("target_language", "en")
    source_language = request.args.get("source_language")
    tts_model = request.args.get("tts_model")
    start_paragraph = validate_positive_int(
        request.args.get("start_paragraph"),
        field_name="start_paragraph",
        default=0,
    )
    if start_paragraph is None:
        start_paragraph = 0

    container = get_container()
    session_id = uuid4().hex
    cancel_event = threading.Event()
    _register_active_run(content_id, session_id, cancel_event)

    # Resolve TTS model through the cascading chain:
    # request param → per-content config → global config → YAML task_models → provider default
    _, resolved_tts = resolve_models_for_task(
        container=container,
        content_id=content_id,
        task_key="note_read_aloud",
        llm_model=None,
        tts_model=tts_model or None,
    )

    req = ReadAloudRequest(
        content_id=content_id,
        session_id=session_id,
        target_language=target_language,
        source_language=source_language or None,
        tts_model=resolved_tts,
        start_paragraph=start_paragraph,
    )

    # Stream SSE events from the read-aloud channel
    channel = _stream_channel(content_id, session_id)
    started = False

    # Launch generation in a background daemon thread after subscription is active.
    # This avoids dropping early events due to subscribe/start race.
    def _start_generation_after_subscribe() -> list[dict[str, str]]:
        nonlocal started
        if started:
            return []
        started = True

        def _run_generation() -> None:
            try:
                container.read_aloud_usecase.generate_stream(req, stop_event=cancel_event)
            finally:
                _clear_active_run(content_id, session_id)

        thread = threading.Thread(
            target=_run_generation,
            daemon=True,
            name=f"read-aloud-{content_id}-{session_id[:8]}",
        )
        thread.start()
        return [{"event": "read_aloud_session", "session_id": session_id}]

    return FlaskResponse(
        stream_with_context(
            container.event_publisher.stream(
                channel,
                timeout=30.0,
                send_initial=True,
                initial_events_factory=_start_generation_after_subscribe,
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
@handle_errors
def get_sentence_audio(content_id: str, sentence_key: str) -> FlaskResponse:
    """REST endpoint: retrieve a single sentence's MP3 audio from cache."""
    content_id = validate_content_id(content_id)
    variant_key = _parse_variant_key(request.args.get("variant_key"))

    container = get_container()
    audio_data = container.read_aloud_cache.load_audio(content_id, variant_key, sentence_key)

    if not audio_data:
        return FlaskResponse("Audio not found", status=404)

    return FlaskResponse(
        audio_data,
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Length": str(len(audio_data)),
        },
    )


@bp.route("/cancel/<content_id>", methods=["POST"])
@handle_errors
def cancel_read_aloud(content_id: str) -> FlaskResponse:
    """Cancel an active read-aloud run for content/session."""
    content_id = validate_content_id(content_id)

    session_id = request.args.get("session_id")
    if not session_id:
        data = request.get_json(silent=True) or {}
        if isinstance(data, dict):
            session_id = data.get("session_id") or data.get("sessionId")
    if not session_id:
        return bad_request("session_id is required")

    session_id = validate_task_id(str(session_id), field_name="session_id")
    cancelled = _cancel_active_run(content_id, session_id)

    return success(
        {
            "content_id": content_id,
            "session_id": session_id,
            "cancelled": cancelled,
        }
    )
