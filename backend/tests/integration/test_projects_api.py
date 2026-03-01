"""Integration tests for project CRUD API endpoints.

These tests verify the complete flow from HTTP request to database operations.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.database import Project


@pytest.mark.asyncio
async def test_create_project_success(async_client: AsyncClient) -> None:
    """Test successful project creation."""
    response = await async_client.post(
        "/api/projects",
        json={"title": "My Research Project", "description": "A test project"}
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert "id" in data
    assert data["title"] == "My Research Project"
    assert data["description"] == "A test project"
    assert data["document_count"] == 0
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_project_without_description(async_client: AsyncClient) -> None:
    """Test project creation with only required fields."""
    response = await async_client.post(
        "/api/projects",
        json={"title": "Minimal Project"}
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["title"] == "Minimal Project"
    assert data["description"] is None


@pytest.mark.asyncio
async def test_create_project_validation_error(async_client: AsyncClient) -> None:
    """Test project creation with invalid data."""
    # Empty title should fail
    response = await async_client.post(
        "/api/projects",
        json={"title": ""}
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_projects_empty(async_client: AsyncClient) -> None:
    """Test listing projects when database is empty."""
    response = await async_client.get("/api/projects")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_projects_with_data(
    async_client: AsyncClient,
    async_session: AsyncSession
) -> None:
    """Test listing projects with existing data."""
    # Create test projects directly in database
    project1 = Project(title="Project 1", description="First project")
    project2 = Project(title="Project 2", description="Second project")
    
    async_session.add_all([project1, project2])
    await async_session.commit()
    
    response = await async_client.get("/api/projects")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["items"]) == 2
    assert data["total"] == 2
    # Most recent first (by updated_at desc)
    assert data["items"][0]["title"] in ["Project 1", "Project 2"]


@pytest.mark.asyncio
async def test_list_projects_pagination(
    async_client: AsyncClient,
    async_session: AsyncSession
) -> None:
    """Test project list pagination."""
    # Create 5 test projects
    for i in range(5):
        project = Project(title=f"Project {i}", description=f"Test {i}")
        async_session.add(project)
    
    await async_session.commit()
    
    # Request first page (2 items)
    response = await async_client.get("/api/projects?limit=2&offset=0")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 0
    
    # Request second page
    response = await async_client.get("/api/projects?limit=2&offset=2")
    data = response.json()
    
    assert len(data["items"]) == 2
    assert data["offset"] == 2


@pytest.mark.asyncio
async def test_get_project_success(
    async_client: AsyncClient,
    async_session: AsyncSession
) -> None:
    """Test getting a project by ID."""
    # Create a test project
    project = Project(title="Test Project", description="Test description")
    async_session.add(project)
    await async_session.commit()
    await async_session.refresh(project)
    
    response = await async_client.get(f"/api/projects/{project.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(project.id)
    assert data["title"] == "Test Project"
    assert data["description"] == "Test description"


@pytest.mark.asyncio
async def test_get_project_not_found(async_client: AsyncClient) -> None:
    """Test getting a non-existent project."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = await async_client.get(f"/api/projects/{fake_uuid}")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_project_success(
    async_client: AsyncClient,
    async_session: AsyncSession
) -> None:
    """Test successful project update."""
    # Create a test project
    project = Project(title="Original Title", description="Original description")
    async_session.add(project)
    await async_session.commit()
    await async_session.refresh(project)
    
    # Update the project
    response = await async_client.put(
        f"/api/projects/{project.id}",
        json={"title": "Updated Title", "description": "Updated description"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["title"] == "Updated Title"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_project_partial(
    async_client: AsyncClient,
    async_session: AsyncSession
) -> None:
    """Test partial project update (only title)."""
    project = Project(title="Original Title", description="Original description")
    async_session.add(project)
    await async_session.commit()
    await async_session.refresh(project)
    
    # Update only title
    response = await async_client.put(
        f"/api/projects/{project.id}",
        json={"title": "New Title"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["title"] == "New Title"
    assert data["description"] == "Original description"


@pytest.mark.asyncio
async def test_update_project_not_found(async_client: AsyncClient) -> None:
    """Test updating a non-existent project."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = await async_client.put(
        f"/api/projects/{fake_uuid}",
        json={"title": "New Title"}
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_success(
    async_client: AsyncClient,
    async_session: AsyncSession
) -> None:
    """Test successful project deletion."""
    project = Project(title="To Be Deleted")
    async_session.add(project)
    await async_session.commit()
    await async_session.refresh(project)
    
    response = await async_client.delete(f"/api/projects/{project.id}")
    
    assert response.status_code == 204
    
    # Verify project was deleted
    get_response = await async_client.get(f"/api/projects/{project.id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_not_found(async_client: AsyncClient) -> None:
    """Test deleting a non-existent project."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = await async_client.delete(f"/api/projects/{fake_uuid}")
    
    assert response.status_code == 404
