"""Unit tests for note prompt builders — outline exclusivity & part sibling awareness."""

from __future__ import annotations

import pytest

from deeplecture.use_cases.dto.note import NotePart
from deeplecture.use_cases.prompts.note import (
    build_note_outline_prompt,
    build_note_part_prompt,
)

# =========================================================================
# Outline prompt — exclusivity rules
# =========================================================================


class TestNoteOutlinePromptExclusivity:
    """Outline prompt must enforce mutually-exclusive focus_points."""

    @pytest.mark.unit
    def test_system_prompt_contains_exclusivity_rule(self) -> None:
        """System prompt must instruct LLM that focus_points are mutually exclusive."""
        _user, system = build_note_outline_prompt(
            language="English",
            context_block="Some lecture transcript.",
        )
        lowered = system.lower()
        # Must mention that each concept belongs to exactly one part
        assert "exclusive" in lowered or "mutually" in lowered or "only one part" in lowered

    @pytest.mark.unit
    def test_user_prompt_contains_no_overlap_constraint(self) -> None:
        """User prompt constraints must mention no-overlap / no-duplicate for focus_points."""
        user, _system = build_note_outline_prompt(
            language="English",
            context_block="Some lecture transcript.",
        )
        lowered = user.lower()
        assert "overlap" in lowered or "duplicate" in lowered or "must not appear" in lowered


# =========================================================================
# Part prompt — sibling awareness
# =========================================================================


SAMPLE_OUTLINE = [
    NotePart(id=1, title="Foundations", summary="Core ideas", focus_points=["concept A", "concept B"]),
    NotePart(id=2, title="Applications", summary="Real-world use", focus_points=["concept C", "concept D"]),
    NotePart(id=3, title="Advanced Topics", summary="Beyond basics", focus_points=["concept E"]),
]


class TestNotePartPromptSiblingAwareness:
    """Part prompt must include sibling outline summary and exclusion rules."""

    @pytest.mark.unit
    def test_part_prompt_includes_sibling_titles(self) -> None:
        """When outline is provided, user prompt must list sibling part titles."""
        current = SAMPLE_OUTLINE[1]  # Part 2
        user, _system = build_note_part_prompt(
            language="English",
            context_block="Some lecture transcript.",
            part=current,
            outline=SAMPLE_OUTLINE,
        )
        # Sibling titles should appear
        assert "Foundations" in user
        assert "Advanced Topics" in user

    @pytest.mark.unit
    def test_part_prompt_includes_sibling_focus_points(self) -> None:
        """When outline is provided, sibling focus_points must appear so the LLM knows boundaries."""
        current = SAMPLE_OUTLINE[1]  # Part 2
        user, _system = build_note_part_prompt(
            language="English",
            context_block="Some lecture transcript.",
            part=current,
            outline=SAMPLE_OUTLINE,
        )
        # Siblings' focus_points should appear
        assert "concept A" in user
        assert "concept E" in user

    @pytest.mark.unit
    def test_part_prompt_contains_exclusion_instruction(self) -> None:
        """When outline is provided, prompt must instruct LLM not to elaborate on other parts."""
        current = SAMPLE_OUTLINE[0]  # Part 1
        user, system = build_note_part_prompt(
            language="English",
            context_block="Some lecture transcript.",
            part=current,
            outline=SAMPLE_OUTLINE,
        )
        combined = (user + system).lower()
        # Must contain some form of "do not explain/elaborate" other parts' concepts
        assert "do not" in combined or "only" in combined

    @pytest.mark.unit
    def test_part_prompt_without_outline_still_works(self) -> None:
        """When outline is None, prompt should still generate correctly (backward compat)."""
        current = SAMPLE_OUTLINE[0]
        user, system = build_note_part_prompt(
            language="English",
            context_block="Some lecture transcript.",
            part=current,
        )
        assert f"Part {current.id}" in user
        assert current.title in user

    @pytest.mark.unit
    def test_part_prompt_single_part_outline_no_sibling_section(self) -> None:
        """When outline has only one part (the current), no sibling section should appear."""
        single = [SAMPLE_OUTLINE[0]]
        user, _system = build_note_part_prompt(
            language="English",
            context_block="Some lecture transcript.",
            part=single[0],
            outline=single,
        )
        # No sibling titles should be present (since there are no siblings)
        assert "Applications" not in user
        assert "Advanced Topics" not in user
