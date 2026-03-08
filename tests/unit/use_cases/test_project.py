"""Tests for ProjectUseCase."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from deeplecture.use_cases.project import ProjectNotFoundError, ProjectUseCase

if TYPE_CHECKING:
    from deeplecture.domain.entities.project import Project

UTC = getattr(datetime, "UTC", timezone.utc)


class FakeProjectStorage:
    """In-memory project storage for unit tests."""

    def __init__(self) -> None:
        self._projects: dict[str, Project] = {}
        self._content_projects: dict[str, str | None] = {}

    def get(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)

    def save(self, project: Project) -> None:
        self._projects[project.id] = project

    def delete(self, project_id: str) -> bool:
        return self._projects.pop(project_id, None) is not None

    def list_all(self) -> list[Project]:
        return sorted(self._projects.values(), key=lambda p: p.created_at, reverse=True)

    def count_content(self, project_id: str) -> int:
        return sum(1 for pid in self._content_projects.values() if pid == project_id)

    def clear_content_project(self, project_id: str) -> int:
        count = 0
        for cid, pid in list(self._content_projects.items()):
            if pid == project_id:
                self._content_projects[cid] = None
                count += 1
        return count

    def update_content_project(self, content_id: str, project_id: str | None) -> bool:
        if content_id not in self._content_projects:
            return False
        self._content_projects[content_id] = project_id
        return True

    # Test helpers
    def add_content(self, content_id: str, project_id: str | None = None) -> None:
        self._content_projects[content_id] = project_id


class TestProjectUseCase:
    def setup_method(self) -> None:
        self.storage = FakeProjectStorage()
        self.uc = ProjectUseCase(project_storage=self.storage)

    def test_create_project(self) -> None:
        project = self.uc.create_project(name="LA", description="MIT 18.06", color="#3B82F6", icon="\U0001f4d0")
        assert project.name == "LA"
        assert project.description == "MIT 18.06"
        assert self.storage.get(project.id) is not None

    def test_list_projects_with_counts(self) -> None:
        p = self.uc.create_project(name="LA")
        self.storage.add_content("c1", p.id)
        self.storage.add_content("c2", p.id)
        self.storage.add_content("c3", None)

        result = self.uc.list_projects()
        assert len(result) == 1
        assert result[0]["content_count"] == 2

    def test_update_project(self) -> None:
        p = self.uc.create_project(name="LA")
        updated = self.uc.update_project(p.id, name="Linear Algebra")
        assert updated.name == "Linear Algebra"

    def test_update_nonexistent_project(self) -> None:
        with pytest.raises(ProjectNotFoundError):
            self.uc.update_project("nonexistent", name="x")

    def test_delete_project_nullifies_content(self) -> None:
        p = self.uc.create_project(name="LA")
        self.storage.add_content("c1", p.id)
        self.storage.add_content("c2", p.id)

        deleted = self.uc.delete_project(p.id)
        assert deleted is True
        assert self.storage.get(p.id) is None
        assert self.storage._content_projects["c1"] is None
        assert self.storage._content_projects["c2"] is None

    def test_delete_nonexistent_project(self) -> None:
        assert self.uc.delete_project("nonexistent") is False

    def test_assign_content(self) -> None:
        p = self.uc.create_project(name="LA")
        self.storage.add_content("c1")
        assert self.uc.assign_content("c1", p.id) is True
        assert self.storage._content_projects["c1"] == p.id

    def test_assign_content_to_nonexistent_project(self) -> None:
        self.storage.add_content("c1")
        with pytest.raises(ProjectNotFoundError):
            self.uc.assign_content("c1", "nonexistent")

    def test_unassign_content(self) -> None:
        p = self.uc.create_project(name="LA")
        self.storage.add_content("c1", p.id)
        assert self.uc.assign_content("c1", None) is True
        assert self.storage._content_projects["c1"] is None

    def test_assign_nonexistent_content(self) -> None:
        p = self.uc.create_project(name="LA")
        assert self.uc.assign_content("no-such-content", p.id) is False
