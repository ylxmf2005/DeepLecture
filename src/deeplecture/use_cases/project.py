"""Project management use case — CRUD and content assignment."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from deeplecture.domain.entities.project import Project

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces.project import ProjectStorageProtocol

UTC = getattr(datetime, "UTC", timezone.utc)
logger = logging.getLogger(__name__)


class ProjectUseCase:
    """Orchestrates project CRUD and content-project assignment."""

    def __init__(self, *, project_storage: ProjectStorageProtocol) -> None:
        self._storage = project_storage

    def list_projects(self) -> list[dict]:
        """Return all projects with their content counts."""
        projects = self._storage.list_all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "color": p.color,
                "icon": p.icon,
                "content_count": self._storage.count_content(p.id),
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in projects
        ]

    def create_project(
        self,
        *,
        name: str,
        description: str = "",
        color: str = "",
        icon: str = "",
    ) -> Project:
        project = Project(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            color=color,
            icon=icon,
        )
        self._storage.save(project)
        logger.info("Created project %s (%s)", project.id, project.name)
        return project

    def update_project(self, project_id: str, **fields: str) -> Project:
        project = self._storage.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)

        allowed = {"name", "description", "color", "icon"}
        for key, value in fields.items():
            if key in allowed:
                object.__setattr__(project, key, value)

        object.__setattr__(project, "updated_at", datetime.now(UTC))
        self._storage.save(project)
        logger.info("Updated project %s", project_id)
        return project

    def delete_project(self, project_id: str) -> bool:
        project = self._storage.get(project_id)
        if project is None:
            return False
        cleared = self._storage.clear_content_project(project_id)
        deleted = self._storage.delete(project_id)
        logger.info("Deleted project %s (unlinked %d content items)", project_id, cleared)
        return deleted

    def get_project(self, project_id: str) -> Project:
        project = self._storage.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    def assign_content(self, content_id: str, project_id: str | None) -> bool:
        """Assign content to a project or remove assignment (project_id=None)."""
        if project_id is not None:
            project = self._storage.get(project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
        return self._storage.update_content_project(content_id, project_id)


class ProjectNotFoundError(Exception):
    """Raised when a project is not found."""

    def __init__(self, project_id: str) -> None:
        super().__init__(f"Project not found: {project_id}")
        self.project_id = project_id
