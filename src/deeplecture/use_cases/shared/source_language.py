"""Shared source-language resolution helpers."""

from __future__ import annotations

AUTO_LANGUAGE = "auto"


class SourceLanguageResolutionError(ValueError):
    """Raised when a configured source language cannot be resolved."""


def is_auto_language(language: str | None) -> bool:
    """Return whether the configured/requested language is the auto sentinel."""
    return (language or "").strip().lower() == AUTO_LANGUAGE


def resolve_source_language(
    requested_language: str,
    *,
    metadata: object | None,
    field_name: str = "source_language",
) -> str:
    """Resolve a configured source language to a concrete subtitle language key."""
    language = (requested_language or "").strip().lower()
    if not language:
        raise ValueError(f"{field_name} is required")

    if language != AUTO_LANGUAGE:
        return language

    detected = getattr(metadata, "detected_source_language", None) if metadata is not None else None
    resolved = (detected or "").strip().lower()
    if resolved:
        return resolved

    raise SourceLanguageResolutionError(
        f"{field_name} is set to auto, but no detected source language is available yet. "
        "Generate subtitles first to detect the spoken language, then retry."
    )
