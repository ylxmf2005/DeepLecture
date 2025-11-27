from __future__ import annotations

import logging
from flask import Flask, request

from deeplecture.api.error_utils import api_error, api_success
from deeplecture.services.content_service import ContentService
from deeplecture.services.note_service import NoteService

logger = logging.getLogger(__name__)

def register_note_routes(app: Flask, *, task_manager=None, content_service: ContentService = None) -> None:
    """
    Register routes for per-video markdown notes.
    """
    note_service = NoteService(task_manager=task_manager, content_service=content_service)

    @app.route("/api/content/<content_id>/notes", methods=["GET", "POST"])
    @app.route("/api/notes", methods=["GET", "POST"])
    def notes_collection(content_id: str | None = None):
        """
        GET: Retrieve a note for a video
        POST: Create or update a note for a video
        """
        if request.method == "GET":
            video_id = content_id or request.args.get("video_id")
            if not video_id:
                return api_error(400, "Missing video_id")

            try:
                dto = note_service.get_note(video_id)
                return api_success(
                    {
                        "video_id": video_id,
                        "content": dto.content,
                        "updated_at": dto.updated_at,
                    },
                )
            except FileNotFoundError as exc:
                return api_error(404, str(exc), logger=logger)
            except Exception as exc:
                return api_error(500, "Failed to load note", logger=logger, exc=exc)

        # POST
        data = request.json or {}
        video_id = content_id or data.get("video_id")
        content = data.get("content", "")

        if not video_id:
            return api_error(400, "Missing video_id")

        try:
            dto = note_service.save_note(video_id, content)
            return api_success(
                {
                    "video_id": video_id,
                    "content": dto.content,
                    "updated_at": dto.updated_at,
                },
            )
        except FileNotFoundError as exc:
            return api_error(404, str(exc), logger=logger)
        except Exception as exc:
            return api_error(500, "Failed to save note", logger=logger, exc=exc)

    @app.route("/api/content/<content_id>/notes/generate", methods=["POST"])
    @app.route("/api/notes/generate", methods=["POST"])
    def generate_note(content_id: str | None = None):
        """
        Start background generation of the markdown note for a given video/slide using AI.
        """
        data = request.json or {}
        video_id = content_id or data.get("video_id")
        if not video_id:
            return api_error(400, "Missing video_id")

        context_mode = data.get("context_mode", "auto")
        user_instruction = data.get("instruction", "") or ""
        learner_profile = data.get("learner_profile", "") or ""
        max_parts_raw = data.get("max_parts")

        max_parts = None
        if max_parts_raw is not None:
            try:
                max_parts_int = int(max_parts_raw)
                if max_parts_int > 0:
                    max_parts = max_parts_int
            except (TypeError, ValueError):
                max_parts = None

        try:
            if task_manager is None:
                return api_error(500, "Task manager not configured")

            note_path = note_service.get_note_path(str(video_id))

            metadata_payload = {
                "video_id": str(video_id),
                "context_mode": str(context_mode or "auto"),
                "user_instruction": str(user_instruction),
                "learner_profile": str(learner_profile),
                "max_parts": max_parts,
            }

            task_id = task_manager.submit_task(
                str(video_id),
                "note_generation",
                metadata=metadata_payload,
            )

            return api_success(
                {
                    "task_id": task_id,
                    "status": "pending",
                    "message": "Note generation task submitted",
                    "note_path": note_path,
                },
            )
        except FileNotFoundError as exc:
            return api_error(404, str(exc), logger=logger)
        except ValueError as exc:
            return api_error(400, str(exc), logger=logger)
        except Exception as exc:  # pragma: no cover - defensive
            return api_error(500, "Failed to start note generation", logger=logger, exc=exc)
