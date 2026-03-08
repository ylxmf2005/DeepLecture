"""Tests for Project entity."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from deeplecture.domain.entities.project import Project

UTC = getattr(datetime, "UTC", timezone.utc)


class TestProject:
    def test_create_minimal(self) -> None:
        p = Project(id="abc", name="Linear Algebra")
        assert p.id == "abc"
        assert p.name == "Linear Algebra"
        assert p.description == ""
        assert p.color == ""
        assert p.icon == ""
        assert p.created_at.tzinfo is not None
        assert p.updated_at.tzinfo is not None

    def test_create_full(self) -> None:
        now = datetime.now(UTC)
        p = Project(
            id="abc",
            name="LA",
            description="MIT 18.06",
            color="#3B82F6",
            icon="\U0001f4d0",
            created_at=now,
            updated_at=now,
        )
        assert p.description == "MIT 18.06"
        assert p.color == "#3B82F6"
        assert p.icon == "\U0001f4d0"

    def test_coerce_iso_string(self) -> None:
        p = Project(
            id="abc",
            name="LA",
            created_at="2026-03-08T12:00:00+00:00",
            updated_at="2026-03-08T12:00:00",
        )
        assert isinstance(p.created_at, datetime)
        assert isinstance(p.updated_at, datetime)
        assert p.updated_at.tzinfo is not None

    def test_invalid_datetime_type(self) -> None:
        with pytest.raises(TypeError, match="must be datetime or ISO-8601"):
            Project(id="abc", name="LA", created_at=12345)
