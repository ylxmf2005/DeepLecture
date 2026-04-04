"""
Shared utilities for Use Cases layer.

Contains cross-cutting utilities used by multiple use cases.
These are application-layer concerns, not domain or infrastructure.
"""

from deeplecture.use_cases.shared.llm_json import parse_llm_json
from deeplecture.use_cases.shared.prompt_safety import (
    create_safe_prompt_builder,
    detect_injection,
    sanitize_context,
    sanitize_learner_profile,
    sanitize_question,
    sanitize_user_input,
    wrap_user_content,
)
from deeplecture.use_cases.shared.source_language import (
    AUTO_LANGUAGE,
    SourceLanguageResolutionError,
    is_auto_language,
    resolve_source_language,
)
from deeplecture.use_cases.shared.subtitle import (
    build_subtitle_language_candidates,
    get_preferred_subtitle_languages,
    load_first_available_subtitle_segments,
    load_subtitle_segments_with_fallback,
)

__all__ = [
    "AUTO_LANGUAGE",
    "SourceLanguageResolutionError",
    "build_subtitle_language_candidates",
    "create_safe_prompt_builder",
    "detect_injection",
    "get_preferred_subtitle_languages",
    "is_auto_language",
    "load_first_available_subtitle_segments",
    "load_subtitle_segments_with_fallback",
    "parse_llm_json",
    "resolve_source_language",
    "sanitize_context",
    "sanitize_learner_profile",
    "sanitize_question",
    "sanitize_user_input",
    "wrap_user_content",
]
