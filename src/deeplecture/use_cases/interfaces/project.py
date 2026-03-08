"""Port interface for project storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from deeplecture.domain.entities.project import Project


@runtime_checkable
class ProjectStorageProtocol(Protocol):
    """Storage protocol for project CRUD operations."""

    def get(self, project_id: str) -> Project | None: ...

    def save(self, project: Project) -> None: ...

    def delete(self, project_id: str) -> bool: ...

    def list_all(self) -> list[Project]: ...

    def count_content(self, project_id: str) -> int: ...

    def clear_content_project(self, project_id: str) -> int: ...

    def update_content_project(self, content_id: str, project_id: str | None) -> bool: ...
