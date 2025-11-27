from __future__ import annotations

import json
import queue
from typing import Optional

from flask import Flask, Response, jsonify

from deeplecture.api.error_utils import api_error, api_success
from deeplecture.infra.sse_manager import SSEManager
from deeplecture.workers import TaskManager


def _serialize_task(task):
    return TaskManager._serialize_task(task)


def register_task_routes(
    app: Flask,
    task_manager: Optional[TaskManager] = None,
    sse_manager: Optional[SSEManager] = None,
) -> None:
    if task_manager is None:
        raise ValueError("TaskManager instance is required for task routes")

    @app.route("/api/content/<content_id>/events", methods=["GET"])
    @app.route("/api/events/<content_id>", methods=["GET"])
    def stream_events(content_id: str):
        if sse_manager is None:
            return api_error(503, "SSE manager not configured")

        subscriber = sse_manager.subscribe(content_id)

        # Send initial state: all tasks for this content
        # This ensures clients get current status even if they connected after task completion
        try:
            current_tasks = task_manager.get_tasks_by_content(content_id)
            for task in current_tasks:
                subscriber.put_nowait({"event": "initial", "task": _serialize_task(task)})
        except Exception:
            pass  # Best effort - don't fail SSE setup if initial state fetch fails

        def event_stream(q: queue.Queue):
            while True:
                try:
                    event = q.get()
                    yield f"data: {json.dumps(event)}\n\n"
                except GeneratorExit:
                    break
                except Exception:
                    break

        response = Response(event_stream(subscriber), mimetype="text/event-stream")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @app.route("/api/tasks/<task_id>", methods=["GET"])
    def get_task(task_id: str):
        task = task_manager.get_task(task_id)
        if not task:
            return api_error(404, f"Task not found: {task_id}")
        return api_success(_serialize_task(task))

    @app.route("/api/content/<content_id>/tasks", methods=["GET"])
    @app.route("/api/tasks/by-content/<content_id>", methods=["GET"])
    def get_tasks_for_content(content_id: str):
        tasks = task_manager.get_tasks_by_content(content_id)
        serialized = [_serialize_task(task) for task in tasks]
        return api_success({"content_id": content_id, "tasks": serialized})
