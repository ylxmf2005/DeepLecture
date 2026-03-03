"""Prompt template definitions and validation rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

_IMPL_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@dataclass(frozen=True, slots=True)
class PromptTemplateDefinition:
    """Persisted custom prompt template definition."""

    func_id: str
    impl_id: str
    name: str
    description: str | None
    system_template: str
    user_template: str
    source: str = "custom"
    created_at: str | None = None
    updated_at: str | None = None
    active: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "func_id": self.func_id,
            "impl_id": self.impl_id,
            "name": self.name,
            "description": self.description,
            "system_template": self.system_template,
            "user_template": self.user_template,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> PromptTemplateDefinition | None:
        try:
            func_id = str(data["func_id"]).strip()
            impl_id = str(data["impl_id"]).strip()
            name = str(data["name"]).strip()
        except KeyError:
            return None

        description = data.get("description")
        system_template = str(data.get("system_template") or "")
        user_template = str(data.get("user_template") or "")

        return cls(
            func_id=func_id,
            impl_id=impl_id,
            name=name,
            description=str(description).strip() if isinstance(description, str) and description.strip() else None,
            system_template=system_template,
            user_template=user_template,
            source=str(data.get("source") or "custom"),
            created_at=str(data.get("created_at")) if data.get("created_at") is not None else None,
            updated_at=str(data.get("updated_at")) if data.get("updated_at") is not None else None,
            active=bool(data.get("active", True)),
        )


_FUNC_PLACEHOLDER_RULES: dict[str, dict[str, set[str]]] = {
    "timeline_segmentation": {
        "allowed": {"segments", "language", "learner_profile"},
        "required": {"segments"},
    },
    "timeline_explanation": {
        "allowed": {"segments", "language", "chunk_start", "chunk_end", "learner_profile"},
        "required": {"segments", "chunk_start", "chunk_end"},
    },
    "slide_lecture": {
        "allowed": {
            "deck_id",
            "page_index",
            "total_pages",
            "source_language",
            "target_language",
            "neighbor_images",
            "previous_transcript",
            "accumulated_summaries",
        },
        "required": {"deck_id", "page_index", "total_pages"},
    },
    "ask_video": {
        "allowed": {"learner_profile", "language", "context_block", "history_block", "question"},
        "required": {"question"},
    },
    "ask_summarize_context": {
        "allowed": {"learner_profile", "language", "context_block"},
        "required": {"context_block"},
    },
    "subtitle_background": {
        "allowed": {"transcript_text"},
        "required": {"transcript_text"},
    },
    "subtitle_enhance_translate": {
        "allowed": {"background", "segments", "target_language"},
        "required": {"segments"},
    },
    "explanation_system": {
        "allowed": {"learner_profile", "output_language"},
        "required": set(),
    },
    "explanation_user": {
        "allowed": {"timestamp", "subtitle_context"},
        "required": {"timestamp"},
    },
    "note_outline": {
        "allowed": {"language", "context_block", "instruction", "profile", "max_parts"},
        "required": {"language", "context_block"},
    },
    "note_part": {
        "allowed": {"language", "context_block", "instruction", "profile", "part", "outline"},
        "required": {"language", "context_block", "part"},
    },
    "cheatsheet_extraction": {
        "allowed": {"context", "language", "subject_type", "user_instruction", "coverage_mode"},
        "required": {"context", "language"},
    },
    "cheatsheet_rendering": {
        "allowed": {"knowledge_items_json", "language", "target_pages", "min_criticality"},
        "required": {"knowledge_items_json", "language"},
    },
    "quiz_generation": {
        "allowed": {"knowledge_items_json", "language", "question_count", "user_instruction"},
        "required": {"knowledge_items_json", "language"},
    },
    "flashcard_generation": {
        "allowed": {"knowledge_items_json", "language", "user_instruction"},
        "required": {"knowledge_items_json", "language"},
    },
    "test_paper_generation": {
        "allowed": {"knowledge_items_json", "language", "user_instruction"},
        "required": {"knowledge_items_json", "language"},
    },
    "podcast_dialogue": {
        "allowed": {"knowledge_items_json", "language", "host_role", "guest_role", "user_instruction"},
        "required": {"knowledge_items_json", "language"},
    },
    "podcast_dramatize": {
        "allowed": {"dialogue_json", "language", "user_instruction"},
        "required": {"dialogue_json", "language"},
    },
}

_PLACEHOLDER_DESCRIPTIONS: dict[str, str] = {
    "segments": "Subtitle segments data (timestamped text)",
    "language": "Output language for generated content",
    "learner_profile": "User's learning profile and preferences",
    "chunk_start": "Start index of the current segment chunk",
    "chunk_end": "End index of the current segment chunk",
    "deck_id": "Unique identifier for the slide deck",
    "page_index": "Current slide page number (0-based)",
    "total_pages": "Total number of pages in the slide deck",
    "source_language": "Original language of the source material",
    "target_language": "Language to translate into",
    "neighbor_images": "Adjacent slide images for context",
    "previous_transcript": "Transcript from the previous slide",
    "accumulated_summaries": "Running summaries from previous slides",
    "question": "The user's question text",
    "context_block": "Relevant subtitle/transcript context around the query",
    "history_block": "Previous conversation history for multi-turn Q&A",
    "transcript_text": "Raw transcript text from ASR",
    "background": "Extracted background context (topic, keywords, tone)",
    "output_language": "Language for the generated output",
    "timestamp": "Specific video timestamp being explained",
    "subtitle_context": "Subtitle text surrounding the timestamp",
    "instruction": "User-provided custom instructions",
    "profile": "Learner profile for personalized generation",
    "max_parts": "Maximum number of note parts to generate",
    "part": "Specific note part being expanded",
    "outline": "Generated note outline structure",
    "context": "Source content for knowledge extraction",
    "subject_type": "Academic subject type (e.g., math, biology)",
    "user_instruction": "Custom user instructions for generation",
    "coverage_mode": "Knowledge coverage mode (exam_focused, comprehensive)",
    "knowledge_items_json": "JSON array of extracted knowledge items",
    "target_pages": "Target number of cheatsheet pages",
    "min_criticality": "Minimum criticality level to include (low, medium, high)",
    "question_count": "Number of quiz questions to generate",
    "host_role": "Podcast host persona description",
    "guest_role": "Podcast guest persona description",
    "dialogue_json": "JSON dialogue script for dramatization",
}


def list_template_func_ids() -> tuple[str, ...]:
    """Return prompt func_ids that support custom templates."""
    return tuple(sorted(_FUNC_PLACEHOLDER_RULES.keys()))


def get_placeholder_metadata() -> dict[str, dict[str, object]]:
    """Return placeholder metadata for all func_ids (for frontend consumption)."""
    result: dict[str, dict[str, object]] = {}
    for func_id, rules in _FUNC_PLACEHOLDER_RULES.items():
        descriptions: dict[str, str] = {}
        for placeholder in sorted(rules["allowed"]):
            descriptions[placeholder] = _PLACEHOLDER_DESCRIPTIONS.get(placeholder, "")
        result[func_id] = {
            "allowed": sorted(rules["allowed"]),
            "required": sorted(rules["required"]),
            "descriptions": descriptions,
        }
    return result


def now_iso_utc() -> str:
    """UTC timestamp for metadata fields."""
    return datetime.now(timezone.utc).isoformat()


def extract_placeholders(text: str) -> set[str]:
    """Extract `{placeholder}` tokens used in template text."""
    return set(_PLACEHOLDER_RE.findall(text))


def validate_prompt_template_definition(template: PromptTemplateDefinition) -> list[str]:
    """Validate template fields and placeholder constraints."""
    errors: list[str] = []

    if template.func_id not in _FUNC_PLACEHOLDER_RULES:
        errors.append(f"Unknown func_id: {template.func_id}")

    if not _IMPL_ID_RE.match(template.impl_id):
        errors.append("impl_id must match ^[a-z][a-z0-9_-]{1,63}$")

    if template.impl_id == "default":
        errors.append("impl_id 'default' is reserved")

    if not template.name.strip():
        errors.append("name is required")

    if not template.system_template.strip() and not template.user_template.strip():
        errors.append("At least one of system_template or user_template is required")

    if errors:
        return errors

    placeholders = extract_placeholders(template.system_template) | extract_placeholders(template.user_template)
    rules = _FUNC_PLACEHOLDER_RULES[template.func_id]

    unknown = placeholders - rules["allowed"]
    if unknown:
        errors.append(f"Unknown placeholders for {template.func_id}: {', '.join(sorted(unknown))}")

    if template.system_template.strip() and template.user_template.strip():
        missing = rules["required"] - placeholders
        if missing:
            errors.append(f"Missing required placeholders for {template.func_id}: {', '.join(sorted(missing))}")

    return errors
