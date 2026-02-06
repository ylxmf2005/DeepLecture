"""Task routes."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from flask import Blueprint, stream_with_context
from flask import Response as FlaskResponse

from deeplecture.di import get_container
from deeplecture.domain import TaskStatus
from deeplecture.presentation.api.shared import handle_errors, not_found, success
from deeplecture.presentation.api.shared.validation import validate_content_id, validate_task_id

if TYPE_CHECKING:
    from flask import Response

    from deeplecture.domain import Task

bp = Blueprint("task", __name__)
log = logging.getLogger(__name__)


@bp.route("/<task_id>", methods=["GET"])
@handle_errors
def get_task_status(task_id: str) -> Response:
    """Get task status by ID."""
    task_id = validate_task_id(task_id, field_name="task_id")

    container = get_container()
    task = container.task_manager.get_task(task_id)

    if task is None:
        return not_found(f"Task not found: {task_id}")

    return success(_serialize_task(task))


@bp.route("/content/<content_id>", methods=["GET"])
@handle_errors
def get_tasks_for_content(content_id: str) -> Response:
    """Get all tasks for a content item."""
    content_id = validate_content_id(content_id)

    container = get_container()
    tasks = container.task_manager.get_tasks_by_content(content_id)

    return success(
        {
            "content_id": content_id,
            "tasks": [_serialize_task(t) for t in tasks],
            "count": len(tasks),
        }
    )


@bp.route("/stream/<content_id>", methods=["GET"])
def stream_task_events(content_id: str) -> FlaskResponse:
    """SSE stream for task events."""
    content_id = validate_content_id(content_id)

    container = get_container()

    # Run reconciliation before snapshot to ensure stale tasks are cleaned up
    _reconcile_stale_tasks_on_connect(content_id, container)

    def get_initial_events() -> list[dict]:
        """Factory called AFTER subscribe to avoid race conditions."""
        tasks = container.task_manager.get_tasks_by_content(content_id)
        return [{"event": "initial", "task": _serialize_task(t)} for t in tasks]

    return FlaskResponse(
        stream_with_context(
            container.event_publisher.stream(
                content_id,
                timeout=30.0,
                send_initial=False,
                initial_events_factory=get_initial_events,
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


def _serialize_task(task: Task) -> dict:
    """Serialize Task entity to API format."""
    status_str = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)

    result = None
    result_kind = task.metadata.get("result_kind") if task.metadata else None
    if result_kind and task.is_ready():
        result = {"kind": result_kind}

    return {
        "id": task.id,
        "type": task.type,
        "content_id": task.content_id,
        "status": status_str,
        "progress": task.progress,
        "error": task.error,
        "result": result,
        "metadata": task.metadata or {},
        "created_at": _format_datetime(task.created_at),
        "updated_at": _format_datetime(task.updated_at),
    }


def _format_datetime(dt: datetime | str | None) -> str | None:
    """Format datetime to ISO8601 string."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _reconcile_stale_tasks_on_connect(content_id: str, container) -> None:
    """Reconcile stale content metadata before SSE snapshot.

    Reuses the same reconciliation logic from content routes to ensure
    that 'processing' statuses with no backing task are corrected to 'error'
    before the client receives the initial snapshot.
    """
    from deeplecture.presentation.api.routes.content import _reconcile_stale_processing

    try:
        metadata = container.content_usecase.get_content(content_id)
        _reconcile_stale_processing(metadata, container)
    except (KeyError, ValueError):
        # Content may not exist yet (e.g., during upload); skip reconciliation
        pass
    except Exception:
        log.debug("Reconciliation skipped for %s", content_id, exc_info=True)
