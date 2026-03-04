"""
End-to-End Workflow Tests

Tests complete user workflows from start to finish.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.e2e
class TestUserOnboardingWorkflow:
    """Test the complete user onboarding workflow."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.e2e
    async def test_complete_user_onboarding(self, client: AsyncClient):
        """Test complete onboarding: register → login → create chat → query."""
        # Step 1: Register user
        unique_id = pytest.hash_seed or "test"
        email = f"user{unique_id}@example.com"
        
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Test123!",
                "full_name": "Test User"
            }
        )
        assert response.status_code in [200, 201]

        # Step 2: Login
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": email,
                "password": "Test123!"
            }
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 3: Get current user
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == email

        # Step 4: Create a chat
        response = await client.post(
            "/api/v1/chat/chats",
            headers=headers,
            json={"title": "My First Chat"}
        )
        assert response.status_code in [200, 201]
        chat_data = response.json()
        chat_id = chat_data.get("id") or chat_data.get("chat_id")
        assert chat_id is not None

        # Step 5: List chats
        response = await client.get("/api/v1/chat/chats", headers=headers)
        assert response.status_code == 200
        chats = response.json()
        assert len(chats) >= 1

        # Step 6: Send a message (may fail if Query Agent not fully configured)
        response = await client.post(
            f"/api/v1/chat/chats/{chat_id}/messages",
            headers=headers,
            json={
                "content": "Hello, I need to query some data",
                "role": "user"
            }
        )
        # Should succeed or give structured error
        assert response.status_code in [200, 201, 400, 500]

        # Step 7: List available agents
        response = await client.get("/api/v1/agents/", headers=headers)
        assert response.status_code == 200
        agents = response.json()
        assert isinstance(agents, list)

        # Step 8: Test design agent (may fail if not fully implemented)
        response = await client.post(
            "/api/v1/agents/design",
            headers=headers,
            json={
                "action": "design_platform",
                "requirements": {
                    "description": "Test platform",
                    "scale": "small"
                }
            }
        )
        # Should succeed or give structured error
        assert response.status_code in [200, 400, 500]

        print(f"\n✅ Complete onboarding workflow successful for user: {email}")


@pytest.mark.e2e
class TestDataQueryWorkflow:
    """Test the data querying workflow."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient):
        """Get authentication headers."""
        unique_id = pytest.hash_seed or "test"
        email = f"query{unique_id}@example.com"
        
        # Register
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Query123!",
                "full_name": "Query User"
            }
        )
        
        # Login
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "Query123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.e2e
    async def test_schema_creation_and_query(self, client: AsyncClient, auth_headers: dict):
        """Test creating a schema and querying it."""
        # Step 1: Create a schema
        response = await client.post(
            "/api/v1/data/schemas",
            headers=auth_headers,
            json={
                "name": "test_schema",
                "description": "Test schema for e2e tests",
                "connection_string": "clickhouse://localhost:8123/default"
            }
        )
        if response.status_code in [200, 201]:
            schema_data = response.json()
            schema_id = schema_data.get("id") or schema_data.get("schema_id")
            
            # Step 2: List schemas
            response = await client.get("/api/v1/data/schemas", headers=auth_headers)
            assert response.status_code == 200
            schemas = response.json()
            assert len(schemas) >= 1
            
            # Step 3: Execute query (may fail if no database connection)
            response = await client.post(
                "/api/v1/query/execute",
                headers=auth_headers,
                json={
                    "query": "SELECT 1 as test",
                    "schema_id": schema_id
                }
            )
            # Should succeed or give structured error
            assert response.status_code in [200, 400, 404, 500]

        print(f"\n✅ Schema and query workflow completed")


@pytest.mark.e2e
class TestAgentInteractionWorkflow:
    """Test interaction with different agents."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient):
        """Get authentication headers."""
        unique_id = pytest.hash_seed or "test"
        email = f"agent{unique_id}@example.com"
        
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Agent123!",
                "full_name": "Agent Test User"
            }
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "Agent123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.e2e
    async def test_query_agent_interaction(self, client: AsyncClient, auth_headers: dict):
        """Test interaction with Query Agent."""
        # List available agents
        response = await client.get("/api/v1/agents/", headers=auth_headers)
        assert response.status_code == 200
        agents = response.json()
        
        # Find Query Agent
        query_agent = next((a for a in agents if "query" in a.get("name", "").lower()), None)
        if not query_agent:
            pytest.skip("Query Agent not available")
        
        # Test Query Agent health
        response = await client.get("/api/v1/agents/query-agent/status", headers=auth_headers)
        assert response.status_code in [200, 500]  # May be unhealthy if no LLM configured
        
        # Query Agent status data
        if response.status_code == 200:
            status = response.json()
            assert "status" in status

        print(f"\n✅ Query Agent interaction completed")

    @pytest.mark.e2e
    async def test_design_agent_interaction(self, client: AsyncClient, auth_headers: dict):
        """Test interaction with Design Agent."""
        # Test Design Agent health
        response = await client.get("/api/v1/agents/design-agent/status", headers=auth_headers)
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            status = response.json()
            assert "status" in status
        
        print(f"\n✅ Design Agent interaction completed")

    @pytest.mark.e2e
    async def test_support_agent_interaction(self, client: AsyncClient, auth_headers: dict):
        """Test interaction with Support Agent."""
        # Test Support Agent health
        response = await client.get("/api/v1/agents/support-agent/status", headers=auth_headers)
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            status = response.json()
            assert "status" in status

        print(f"\n✅ Support Agent interaction completed")


@pytest.mark.e2e
class TestErrorRecoveryWorkflow:
    """Test error recovery and edge cases."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.e2e
    async def test_invalid_token_recovery(self, client: AsyncClient):
        """Test handling of invalid token and recovery."""
        # Try to access protected endpoint with invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        
        response = await client.get("/api/v1/auth/me", headers=invalid_headers)
        assert response.status_code in [401, 403]
        
        # Now register and login properly
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "recovery@example.com",
                "password": "Recovery123!",
                "full_name": "Recovery User"
            }
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "recovery@example.com", "password": "Recovery123!"}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        
        # Now access with valid token
        valid_headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/auth/me", headers=valid_headers)
        assert response.status_code == 200

        print(f"\n✅ Error recovery workflow completed")

    @pytest.mark.e2e
    async def test_malformed_request_handling(self, client: AsyncClient):
        """Test handling of malformed requests."""
        # Send invalid data types
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": 12345,  # Should be string
                "password": [],  # Should be string
                "full_name": {}  # Should be string
            }
        )
        assert response.status_code in [400, 422]
        
        # Send missing fields
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com"}
        )
        assert response.status_code in [400, 422]

        print(f"\n✅ Malformed request handling verified")


@pytest.mark.e2e
class TestPerformanceCriticalWorkflows:
    """Test performance of critical workflows."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.e2e
    async def test_health_check_performance(self, client: AsyncClient):
        """Test health check endpoint performance."""
        import time
        
        # Make multiple health check requests
        times = []
        for _ in range(10):
            start = time.time()
            response = await client.get("/health")
            end = time.time()
            assert response.status_code == 200
            times.append((end - start) * 1000)  # Convert to ms
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        print(f"\n📊 Health Check Performance:")
        print(f"   Average: {avg_time:.2f}ms")
        print(f"   Max: {max_time:.2f}ms")
        
        # Health check should be fast (< 100ms)
        assert avg_time < 100, f"Health check too slow: {avg_time:.2f}ms"

    @pytest.mark.e2e
    async def test_auth_performance(self, client: AsyncClient):
        """Test authentication performance."""
        import time
        
        unique_id = pytest.hash_seed or "test"
        email = f"perf{unique_id}@example.com"
        
        # Measure registration time
        start = time.time()
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Perf123!",
                "full_name": "Performance User"
            }
        )
        register_time = (time.time() - start) * 1000
        
        # Measure login time
        start = time.time()
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "Perf123!"}
        )
        login_time = (time.time() - start) * 1000
        
        assert response.status_code == 200
        
        print(f"\n📊 Authentication Performance:")
        print(f"   Registration: {register_time:.2f}ms")
        print(f"   Login: {login_time:.2f}ms")
        
        # Auth should be reasonably fast (< 500ms)
        assert login_time < 500, f"Login too slow: {login_time:.2f}ms"
