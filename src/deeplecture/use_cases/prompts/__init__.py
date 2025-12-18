"""Prompt templates for LLM interactions.

This module provides:
- PromptRegistry: Central registry for runtime prompt selection
- create_default_registry(): Factory function for standard setup
- Legacy functions: Backward-compatible direct prompt builders
"""

from deeplecture.use_cases.prompts.registry import (
    PromptRegistry,
    create_default_registry,
)
from deeplecture.use_cases.prompts.subtitle import (
    build_background_prompt,
    build_enhance_translate_prompt,
)

__all__ = [
    "PromptRegistry",
    "build_background_prompt",
    "build_enhance_translate_prompt",
    "create_default_registry",
]
