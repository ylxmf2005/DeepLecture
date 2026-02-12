"""Conversation and Q&A routes."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import handle_errors, not_found, rate_limit, success
from deeplecture.presentation.api.shared.model_resolution import resolve_models_for_task
from deeplecture.presentation.api.shared.validation import (
    validate_content_id,
    validate_message,
    validate_title,
)
from deeplecture.use_cases.dto.ask import (
    AskQuestionRequest,
    ContextItem,
    CreateConversationRequest,
    SummarizeContextRequest,
)

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("conversations", __name__)
summaries_bp = Blueprint("summaries", __name__)


@bp.route("", methods=["GET"])
@handle_errors
def list_conversations() -> Response:
    """List all conversations for a content item."""
    content_id = validate_content_id(request.args.get("content_id"), field_name="content_id")

    container = get_container()
    conversations = container.ask_usecase.list_conversations(content_id)

    return success(
        {
            "content_id": content_id,
            "conversations": [
                {
                    "id": c.id,
                    "title": c.title,
                    "created_at": _format_datetime(c.created_at),
                    "updated_at": _format_datetime(c.updated_at),
                    "last_message_preview": c.last_message_preview,
                }
                for c in conversations
            ],
        }
    )


@bp.route("", methods=["POST"])
@handle_errors
def create_conversation() -> Response:
    """Create a new conversation."""
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")
    title = validate_title(data.get("title"), field_name="title", required=False, default="New chat")

    container = get_container()
    req = CreateConversationRequest(content_id=content_id, title=title)
    conversation = container.ask_usecase.create_conversation(req)

    return success({"content_id": content_id, "conversation": conversation.to_dict()})


@bp.route("/<conversation_id>", methods=["GET"])
@handle_errors
def get_conversation(conversation_id: str) -> Response:
    """Get a specific conversation."""
    content_id = validate_content_id(request.args.get("content_id"), field_name="content_id")

    container = get_container()
    conversation = container.ask_usecase.get_conversation(content_id, conversation_id)

    if conversation is None:
        return not_found(f"Conversation not found: {conversation_id}")

    return success({"content_id": content_id, "conversation": conversation.to_dict()})


@bp.route("/<conversation_id>", methods=["DELETE"])
@handle_errors
def delete_conversation(conversation_id: str) -> Response:
    """Delete a conversation."""
    data = request.get_json(silent=True) or {}
    content_id = validate_content_id(data.get("content_id"), field_name="content_id")

    container = get_container()
    deleted = container.ask_usecase.delete_conversation(content_id, conversation_id)

    return success({"deleted": deleted})


@bp.route("/<conversation_id>/messages", methods=["POST"])
@rate_limit("generate")
@handle_errors
def ask_question(conversation_id: str) -> Response:
    """Ask a question within a conversation."""
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")
    message = validate_message(data.get("message"), field_name="message")
    raw_context = data.get("context", [])
    learner_profile = data.get("learner_profile", "")
    context_window = data.get("subtitle_context_window_seconds")
    language = data.get("language") or None

    # Model and prompt selection (optional, None = use defaults)
    llm_model = data.get("llm_model") or None
    prompts = data.get("prompts") or None

    context_items = _parse_context_items(raw_context)

    container = get_container()
    llm_model, _ = resolve_models_for_task(
        container=container,
        content_id=content_id,
        task_key="ask_video",
        llm_model=llm_model,
        tts_model=None,
    )
    req = AskQuestionRequest(
        content_id=content_id,
        conversation_id=conversation_id,
        question=message,
        context_items=context_items,
        learner_profile=learner_profile,
        context_window_seconds=context_window,
        language=language,
        llm_model=llm_model,
        prompts=prompts,
    )

    result = container.ask_usecase.ask_question(req)

    return success({"answer": result.answer})


@summaries_bp.route("", methods=["POST"])
@rate_limit("generate")
@handle_errors
def summarize_context() -> Response:
    """Summarize context (e.g., missed lecture content)."""
    data = request.get_json(silent=True) or {}

    raw_context = data.get("context", [])
    learner_profile = data.get("learner_profile", "")
    language = data.get("language") or None

    # Model and prompt selection (optional, None = use defaults)
    llm_model = data.get("llm_model") or None
    prompts = data.get("prompts") or None

    context_items = _parse_context_items(raw_context)

    container = get_container()
    llm_model, _ = resolve_models_for_task(
        container=container,
        content_id=None,
        task_key="ask_video",
        llm_model=llm_model,
        tts_model=None,
    )
    req = SummarizeContextRequest(
        context_items=context_items,
        learner_profile=learner_profile,
        language=language,
        llm_model=llm_model,
        prompts=prompts,
    )

    result = container.ask_usecase.summarize_context(req)

    return success({"summary": result.summary})


def _parse_context_items(raw_context: list) -> list[ContextItem]:
    """Parse raw context items from request."""
    items: list[ContextItem] = []

    if not isinstance(raw_context, list):
        return items

    for item in raw_context:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type", "").lower()
        if not item_type:
            continue

        if item_type == "timeline":
            data = {
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "start": item.get("start"),
                "end": item.get("end"),
            }
        elif item_type == "subtitle":
            data = {
                "text": item.get("text", ""),
                "startTime": item.get("startTime") or item.get("start_time"),
            }
        elif item_type == "screenshot":
            data = {
                "timestamp": item.get("timestamp"),
                "imagePath": (
                    item.get("imagePath") or item.get("image_path") or item.get("imageUrl") or item.get("image_url")
                ),
            }
        else:
            continue

        items.append(ContextItem(type=item_type, data=data))

    return items


def _format_datetime(dt: datetime | str | None) -> str | None:
    """Format datetime to ISO8601 string."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)
