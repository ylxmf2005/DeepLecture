"""Integration tests for Project API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from deeplecture.domain.entities.project import Project
from deeplecture.use_cases.project import ProjectNotFoundError

if TYPE_CHECKING:
    from flask.testing import FlaskClient


@pytest.fixture
def mock_project_usecase(mock_container: MagicMock) -> MagicMock:
    """Ensure project_usecase mock is on the container."""
    mock_container.project_usecase = MagicMock()
    return mock_container.project_usecase


class TestListProjects:
    def test_returns_project_list(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        mock_project_usecase.list_projects.return_value = [
            {
                "id": "p1",
                "name": "LA",
                "description": "",
                "color": "#3B82F6",
                "icon": "",
                "content_count": 5,
                "created_at": "2026-03-08T12:00:00+00:00",
                "updated_at": "2026-03-08T12:00:00+00:00",
            }
        ]
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["projects"][0]["name"] == "LA"

    def test_returns_empty_list(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        mock_project_usecase.list_projects.return_value = []
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["count"] == 0


class TestCreateProject:
    def test_create_success(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        mock_project_usecase.create_project.return_value = Project(
            id="p1", name="LA", description="MIT", color="#3B82F6", icon=""
        )
        resp = client.post("/api/projects", json={"name": "LA", "description": "MIT", "color": "#3B82F6"})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "LA"

    def test_create_missing_name(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        resp = client.post("/api/projects", json={})
        assert resp.status_code == 400

    def test_create_empty_name(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        resp = client.post("/api/projects", json={"name": "   "})
        assert resp.status_code == 400


class TestUpdateProject:
    def test_update_success(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        mock_project_usecase.update_project.return_value = Project(id="p1", name="Linear Algebra")
        resp = client.put(
            "/api/projects/00000000-0000-0000-0000-000000000001",
            json={"name": "Linear Algebra"},
        )
        assert resp.status_code == 200

    def test_update_not_found(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        mock_project_usecase.update_project.side_effect = ProjectNotFoundError("p1")
        resp = client.put(
            "/api/projects/00000000-0000-0000-0000-000000000001",
            json={"name": "x"},
        )
        assert resp.status_code == 404

    def test_update_no_fields(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        resp = client.put("/api/projects/00000000-0000-0000-0000-000000000001", json={})
        assert resp.status_code == 400


class TestDeleteProject:
    def test_delete_success(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        mock_project_usecase.delete_project.return_value = True
        resp = client.delete("/api/projects/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["deleted"] is True

    def test_delete_not_found(self, client: FlaskClient, mock_project_usecase: MagicMock) -> None:
        mock_project_usecase.delete_project.return_value = False
        resp = client.delete("/api/projects/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 404
