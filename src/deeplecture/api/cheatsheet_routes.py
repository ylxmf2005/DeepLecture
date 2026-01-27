"""Cheatsheet API routes."""

from __future__ import annotations

import logging
from flask import Flask, request

from deeplecture.api.error_utils import api_error, api_success
from deeplecture.services.cheatsheet_service import CheatsheetService
from deeplecture.services.content_service import ContentService

logger = logging.getLogger(__name__)


def register_cheatsheet_routes(
    app: Flask,
    *,
    task_manager=None,
    content_service: ContentService = None,
) -> None:
    """
    Register routes for per-video cheatsheet (open-book exam review).
    """
    cheatsheet_service = CheatsheetService(
        task_manager=task_manager, content_service=content_service
    )

    @app.route("/api/content/<content_id>/cheatsheet", methods=["GET", "POST"])
    @app.route("/api/cheatsheet", methods=["GET", "POST"])
    def cheatsheet_collection(content_id: str | None = None):
        """
        GET: Retrieve a cheatsheet for content
        POST: Create or update a cheatsheet for content
        """
        if request.method == "GET":
            video_id = content_id or request.args.get("video_id")
            if not video_id:
                return api_error(400, "Missing video_id")

            try:
                dto = cheatsheet_service.get_cheatsheet(video_id)
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
                return api_error(500, "Failed to load cheatsheet", logger=logger, exc=exc)

        # POST
        data = request.json or {}
        video_id = content_id or data.get("video_id")
        content = data.get("content", "")

        if not video_id:
            return api_error(400, "Missing video_id")

        try:
            dto = cheatsheet_service.save_cheatsheet(video_id, content)
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
            return api_error(500, "Failed to save cheatsheet", logger=logger, exc=exc)

    @app.route("/api/content/<content_id>/cheatsheet/generate", methods=["POST"])
    @app.route("/api/cheatsheet/generate", methods=["POST"])
    def generate_cheatsheet(content_id: str | None = None):
        """
        Start background generation of the cheatsheet for content using AI.

        Parameters:
            - video_id/content_id: Content identifier
            - context_mode: "auto" | "subtitle" | "slide" | "both" (default: "auto")
            - instruction: User instruction (optional)
            - min_criticality: "high" | "medium" | "low" (default: "medium")
            - subject_type: "auto" | "stem" | "humanities" (default: "auto")
            - target_pages: Target length in pages (default: 2)
        """
        data = request.json or {}
        video_id = content_id or data.get("video_id")
        if not video_id:
            return api_error(400, "Missing video_id")

        context_mode = data.get("context_mode", "auto")
        user_instruction = data.get("instruction", "") or ""
        min_criticality = data.get("min_criticality", "medium")
        subject_type = data.get("subject_type", "auto")
        target_pages_raw = data.get("target_pages", 2)

        target_pages = 2
        if target_pages_raw is not None:
            try:
                target_pages_int = int(target_pages_raw)
                if target_pages_int > 0:
                    target_pages = target_pages_int
            except (TypeError, ValueError):
                pass

        # Validate parameters
        valid_context_modes = {"auto", "subtitle", "slide", "both"}
        if context_mode not in valid_context_modes:
            return api_error(
                400, f"context_mode must be one of: {', '.join(valid_context_modes)}"
            )

        valid_criticality = {"high", "medium", "low"}
        if min_criticality not in valid_criticality:
            return api_error(
                400, f"min_criticality must be one of: {', '.join(valid_criticality)}"
            )

        valid_subjects = {"auto", "stem", "humanities"}
        if subject_type not in valid_subjects:
            return api_error(
                400, f"subject_type must be one of: {', '.join(valid_subjects)}"
            )

        try:
            if task_manager is None:
                return api_error(500, "Task manager not configured")

            cheatsheet_path = cheatsheet_service.get_cheatsheet_path(str(video_id))

            metadata_payload = {
                "video_id": str(video_id),
                "context_mode": str(context_mode or "auto"),
                "user_instruction": str(user_instruction),
                "min_criticality": str(min_criticality),
                "subject_type": str(subject_type),
                "target_pages": target_pages,
            }

            task_id = task_manager.submit_task(
                str(video_id),
                "cheatsheet_generation",
                metadata=metadata_payload,
            )

            return api_success(
                {
                    "task_id": task_id,
                    "status": "pending",
                    "message": "Cheatsheet generation task submitted",
                    "cheatsheet_path": cheatsheet_path,
                },
            )
        except FileNotFoundError as exc:
            return api_error(404, str(exc), logger=logger)
        except ValueError as exc:
            return api_error(400, str(exc), logger=logger)
        except Exception as exc:
            return api_error(
                500, "Failed to start cheatsheet generation", logger=logger, exc=exc
            )
