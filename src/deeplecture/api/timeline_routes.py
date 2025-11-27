from __future__ import annotations

import logging

from flask import Flask, request

from deeplecture.api.error_utils import api_error, api_success
from deeplecture.services.content_service import ContentService
from deeplecture.services.timeline_service import TimelineService


logger = logging.getLogger(__name__)


def register_timeline_routes(app: Flask, *, task_manager=None, content_service: ContentService = None) -> None:
    """
    Register subtitle timeline related routes.
    """

    timeline_service = TimelineService(task_manager=task_manager, content_service=content_service)

    @app.route("/api/content/<content_id>/timelines", methods=["POST"])
    @app.route("/api/timelines", methods=["POST"])
    def create_timeline(content_id: str | None = None):
        """
        Generate (or load cached) interactive timeline based on subtitles.
        """
        try:
            data = request.json or {}
            video_id = content_id or data.get("video_id")
            if not video_id:
                return api_error(400, "Missing video_id")

            raw_language = data.get("language")
            language = str(raw_language) if raw_language else None
            learner_profile = data.get("learner_profile")
            force_flag = data.get("force", False)

            force = (
                str(force_flag).lower() in ("1", "true", "yes", "y")
                if isinstance(force_flag, (str, int, bool))
                else False
            )

            payload = timeline_service.get_or_generate_timeline(
                video_id=str(video_id),
                language=language,
                learner_profile=learner_profile,
                force=force,
            )

            return api_success(payload)
        except FileNotFoundError as exc:
            return api_error(404, str(exc), logger=logger)
        except ValueError as exc:
            return api_error(400, str(exc), logger=logger)
        except RuntimeError as exc:
            return api_error(500, str(exc), logger=logger)
        except Exception as e:
            return api_error(500, "Failed to generate subtitle timeline", logger=logger, exc=e)
