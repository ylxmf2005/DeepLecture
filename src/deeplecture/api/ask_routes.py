from __future__ import annotations

import logging
from typing import Any, Dict, List

from flask import Flask, request

from deeplecture.api.error_utils import api_error, api_success
from deeplecture.services.ask_service import AskService
from deeplecture.services.content_service import ContentService

logger = logging.getLogger(__name__)


def register_ask_routes(app: Flask, *, content_service: ContentService = None) -> None:
    """
    Register Ask-tab related routes on the given Flask application.
    """
    ask_service = AskService(content_service=content_service)

    @app.route("/api/content/<content_id>/conversations", methods=["GET", "POST"])
    @app.route("/api/conversations", methods=["GET", "POST"])
    def conversations_collection(content_id: str | None = None):
        """
        GET: List conversations for a video
        POST: Create a new conversation
        """
        if request.method == "GET":
            video_id = content_id or request.args.get("video_id")
            if not video_id:
                return api_error(400, "Missing video_id")

            try:
                items = ask_service.list_conversations(video_id)
                return api_success({"video_id": video_id, "conversations": items})
            except FileNotFoundError as exc:
                return api_error(404, str(exc), logger=logger)
            except Exception as e:
                return api_error(500, "Failed to list conversations", logger=logger, exc=e)

        # POST
        payload: Dict[str, Any] = request.json or {}
        video_id = content_id or payload.get("video_id")
        title = str(payload.get("title") or "").strip()

        if not video_id:
            return api_error(400, "Missing video_id")

        try:
            created = ask_service.create_conversation(video_id, title)
            return api_success(
                {
                    "video_id": video_id,
                    "conversation": created,
                }
            )
        except FileNotFoundError as exc:
            return api_error(404, str(exc), logger=logger)

    @app.route("/api/content/<content_id>/conversations/<conversation_id>", methods=["GET", "DELETE"])
    @app.route("/api/conversations/<conversation_id>", methods=["GET", "DELETE"])
    def conversation_resource(conversation_id: str, content_id: str | None = None):
        """
        GET: Retrieve a conversation
        DELETE: Delete a conversation
        """
        if request.method == "GET":
            video_id = content_id or request.args.get("video_id")
            if not video_id:
                return api_error(400, "Missing video_id")

            try:
                data = ask_service.get_conversation(video_id, conversation_id)
            except FileNotFoundError as exc:
                return api_error(404, str(exc), logger=logger)
            if not data:
                return api_error(404, "Conversation not found")

            return api_success(
                {
                    "video_id": video_id,
                    "conversation": {
                        "id": data.get("id") or conversation_id,
                        "title": data.get("title"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "messages": data.get("messages") or [],
                    },
                }
            )

        # DELETE
        payload = request.json or {}
        video_id = content_id or payload.get("video_id")

        if not video_id:
            video_id = request.args.get("video_id")

        if not video_id:
            return api_error(400, "Missing video_id")

        try:
            deleted = ask_service.delete_conversation(video_id, conversation_id)
            if not deleted:
                return api_error(404, "Conversation not found")
        except FileNotFoundError as exc:
            return api_error(404, str(exc), logger=logger)
        except Exception as exc:
            return api_error(500, "Failed to delete conversation", logger=logger, exc=exc)

        return api_success({"message": "Conversation deleted"})

    @app.route("/api/content/<content_id>/conversations/<conversation_id>/messages", methods=["POST"])
    @app.route("/api/conversations/<conversation_id>/messages", methods=["POST"])
    def create_message(conversation_id: str, content_id: str | None = None):
        """
        Ask a question and get an AI response.
        """
        try:
            data: Dict[str, Any] = request.json or {}
            video_id = content_id or data.get("video_id")
            user_message_raw = data.get("message")
            context_items: List[Dict[str, Any]] = data.get("context") or []
            learner_profile = data.get("learner_profile") or ""
            context_window_override = data.get("subtitle_context_window_seconds")

            if not video_id:
                return api_error(400, "Missing video_id")

            question = str(user_message_raw or "").strip()

            if not question:
                if context_items:
                    question = (
                        "Using these context snippets, explain the key concepts they cover in detail, "
                        "providing a structured explanation and relevant examples."
                    )
                else:
                    return api_error(400, "Missing message")

            answer = ask_service.ask_video(
                video_id=video_id,
                conversation_id=conversation_id,
                question=question,
                context_items=context_items,
                learner_profile=learner_profile,
                context_window_override=context_window_override,
            )

            return api_success({"answer": answer})
        except FileNotFoundError as exc:
            return api_error(404, str(exc), logger=logger)
        except Exception as e:
            return api_error(500, "Failed to answer question", logger=logger, exc=e)

    @app.route("/api/summaries", methods=["POST"])
    def create_summary():
        """
        Generate a summary for a given list of context items.
        Does NOT save to conversation history.
        """
        try:
            data: Dict[str, Any] = request.json or {}
            context_items: List[Dict[str, Any]] = data.get("context") or []
            learner_profile = data.get("learner_profile") or ""

            summary = ask_service.summarize_context(
                context_items=context_items,
                learner_profile=learner_profile,
            )

            return api_success({"summary": summary})

        except Exception as e:
            return api_error(500, "Failed to generate summary", logger=logger, exc=e)
