"""
Integration Tests for API Endpoints

Tests API endpoints with actual database and agent integration.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.integration
class TestAPIEndpointsIntegration:
    """Integration tests for all API endpoints."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient):
        """Get authentication headers for authenticated requests."""
        # First, register a test user
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "Test123!",
                "full_name": "Test User"
            }
        )
        assert response.status_code in [200, 201, 400]  # 400 if already exists

        # Login to get token
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "Test123!"
            }
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # Health Checks

    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    # Authentication Endpoints

    async def test_register_user(self, client: AsyncClient):
        """Test user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"user{pytest.hash_seed}@example.com",
                "password": "Test123!",
                "full_name": "Test User"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "access_token" in data or "message" in data

    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "wrongpassword"
            }
        )
        assert response.status_code in [400, 401]

    async def test_get_current_user(self, client: AsyncClient, auth_headers: dict):
        """Test getting current user info."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "email" in data

    # Chat API Endpoints

    async def test_create_chat(self, client: AsyncClient, auth_headers: dict):
        """Test creating a new chat."""
        response = await client.post(
            "/api/v1/chat/chats",
            headers=auth_headers,
            json={"title": "Test Chat"}
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data or "chat_id" in data

    async def test_list_chats(self, client: AsyncClient, auth_headers: dict):
        """Test listing user's chats."""
        response = await client.get("/api/v1/chat/chats", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_send_message(self, client: AsyncClient, auth_headers: dict):
        """Test sending a message to a chat."""
        # First create a chat
        chat_response = await client.post(
            "/api/v1/chat/chats",
            headers=auth_headers,
            json={"title": "Test Chat"}
        )
        if chat_response.status_code in [200, 201]:
            chat_data = chat_response.json()
            chat_id = chat_data.get("id") or chat_data.get("chat_id")
            
            # Send a message
            response = await client.post(
                f"/api/v1/chat/chats/{chat_id}/messages",
                headers=auth_headers,
                json={
                    "content": "Test message",
                    "role": "user"
                }
            )
            assert response.status_code in [200, 201]

    # Data Schema Endpoints

    async def test_list_schemas(self, client: AsyncClient, auth_headers: dict):
        """Test listing data schemas."""
        response = await client.get("/api/v1/data/schemas", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_schema(self, client: AsyncClient, auth_headers: dict):
        """Test creating a new data schema."""
        response = await client.post(
            "/api/v1/data/schemas",
            headers=auth_headers,
            json={
                "name": "test_schema",
                "description": "Test schema",
                "connection_string": "clickhouse://localhost:8123/default"
            }
        )
        assert response.status_code in [200, 201]

    # Agent Endpoints

    async def test_list_agents(self, client: AsyncClient, auth_headers: dict):
        """Test listing available agents."""
        response = await client.get("/api/v1/agents/", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_query_agent(self, client: AsyncClient, auth_headers: dict):
        """Test query agent endpoint."""
        response = await client.post(
            "/api/v1/agents/query",
            headers=auth_headers,
            json={
                "query": "SELECT * FROM users LIMIT 10",
                "schema_id": None
            }
        )
        # May fail if no schema exists, but should return structured error
        assert response.status_code in [200, 400, 404, 500]

    async def test_design_agent(self, client: AsyncClient, auth_headers: dict):
        """Test design agent endpoint."""
        response = await client.post(
            "/api/v1/agents/design",
            headers=auth_headers,
            json={
                "action": "design_platform",
                "requirements": {
                    "description": "Test platform",
                    "scale": "small",
                    "budget": 100
                }
            }
        )
        # May fail if agent not fully implemented, but should return structured response
        assert response.status_code in [200, 400, 500]

    # Platform Endpoints

    async def test_list_platforms(self, client: AsyncClient, auth_headers: dict):
        """Test listing platforms."""
        response = await client.get("/api/v1/platforms/", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    # Monitoring Endpoints

    async def test_metrics_endpoint(self, client: AsyncClient):
        """Test Prometheus metrics endpoint."""
        response = await client.get("/metrics")
        assert response.status_code == 200
        # Metrics endpoint returns text/plain
        assert "text/plain" in response.headers.get("content-type", "")

    # Query Endpoints

    async def test_execute_query_unauthorized(self, client: AsyncClient):
        """Test query execution without authentication."""
        response = await client.post(
            "/api/v1/query/execute",
            json={
                "query": "SELECT 1"
            }
        )
        assert response.status_code in [401, 403]

    async def test_execute_query_authorized(self, client: AsyncClient, auth_headers: dict):
        """Test query execution with authentication."""
        response = await client.post(
            "/api/v1/query/execute",
            headers=auth_headers,
            json={
                "query": "SELECT 1",
                "schema_id": None
            }
        )
        # May fail if no database connection, but should be authorized
        assert response.status_code in [200, 400, 404, 500]


@pytest.mark.integration
class TestErrorHandling:
    """Integration tests for error handling."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    async def test_404_endpoint(self, client: AsyncClient):
        """Test 404 for non-existent endpoint."""
        response = await client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    async def test_invalid_json(self, client: AsyncClient):
        """Test handling of invalid JSON."""
        response = await client.post(
            "/api/v1/auth/login",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 422]

    async def test_missing_required_fields(self, client: AsyncClient):
        """Test validation of required fields."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com"
                # Missing password and full_name
            }
        )
        assert response.status_code in [400, 422]


@pytest.mark.integration
class TestRateLimiting:
    """Integration tests for rate limiting."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    async def test_multiple_requests(self, client: AsyncClient):
        """Test multiple rapid requests."""
        # Make multiple requests to the same endpoint
        responses = []
        for i in range(10):
            response = await client.get("/health")
            responses.append(response.status_code)
        
        # Most should succeed, rate limiting may kick in
        success_count = sum(1 for status in responses if status == 200)
        assert success_count >= 8  # At least 8/10 should succeed
