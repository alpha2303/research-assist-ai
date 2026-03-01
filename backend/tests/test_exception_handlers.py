"""Tests for global FastAPI exception handlers in app.main.

Verifies that all responses conform to the ErrorResponse schema:
  {"error": str, "message": str, "details": ... | null}

These tests use a lightweight client that does NOT require a running database.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    """Lightweight test client — no DB dependency."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_validation_error_returns_422_with_error_response(client: AsyncClient) -> None:
    """POST with invalid body → 422 with ErrorResponse shape."""
    response = await client.post("/api/projects", json={})  # title is required
    assert response.status_code == 422

    body = response.json()
    assert body["error"] == "Validation error"
    assert isinstance(body["message"], str)
    assert "details" in body
    assert "validation_errors" in body["details"]
    assert isinstance(body["details"]["validation_errors"], list)


@pytest.mark.asyncio
async def test_validation_error_keys_match_error_response_schema(client: AsyncClient) -> None:
    """422 response must contain exactly error, message, details."""
    response = await client.post("/api/projects", json={})
    assert set(response.json().keys()) == {"error", "message", "details"}


@pytest.mark.asyncio
async def test_http_405_returns_405(client: AsyncClient) -> None:
    """PATCH on a route that only accepts GET/POST → 405."""
    response = await client.patch("/api/projects", json={})
    assert response.status_code == 405


@pytest.mark.asyncio
async def test_health_endpoint_not_affected(client: AsyncClient) -> None:
    """GET /api/health still returns a normal response."""
    response = await client.get("/api/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "healthy"
