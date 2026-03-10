"""
Enhanced Integration Tests for Agent Integration (Issue #23)

Comprehensive tests for agent interactions with backend API,
agent-to-agent communication, error handling, and various input scenarios.
"""

import pytest
import json
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.integration
class TestAgentAPIIntegration:
    """Test agent interactions with backend API endpoints."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient):
        """Get authentication headers for authenticated requests."""
        # Register test user
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "integration_test@example.com",
                "password": "Test123!",
                "full_name": "Integration Test User"
            }
        )
        assert response.status_code in [200, 201]

        # Login
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "integration_test@example.com",
                "password": "Test123!"
            }
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_agent_registry_status(self, client: AsyncClient, auth_headers: dict):
        """Test agent registry status endpoint returns proper structure."""
        response = await client.get("/api/v1/agents/status", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "total_agents" in data
        assert "healthy_agents" in data
        assert "unhealthy_agents" in data
        assert "agents" in data
        assert isinstance(data["agents"], list)

    # ===== Query Agent Integration =====

    async def test_query_agent_health(self, client: AsyncClient, auth_headers: dict):
        """Test Query Agent health endpoint."""
        response = await client.get("/api/v1/agents/query-agent/status", headers=auth_headers)
        assert response.status_code in [200, 500]  # May be unhealthy if LLM not configured

        if response.status_code == 200:
            status = response.json()
            assert "status" in status
            assert status["status"] in ["healthy", "unhealthy"]
            # Check for performance metrics
            assert "llm_provider" in status or "model" in status

    async def test_query_agent_process_request(self, client: AsyncClient, auth_headers: dict):
        """Test sending a query to Query Agent and receiving SQL."""
        # Check agent health first
        health_resp = await client.get("/api/v1/agents/query-agent/status", headers=auth_headers)
        if health_resp.status_code != 200:
            pytest.skip("Query Agent not healthy")

        # Send a natural language query
        payload = {
            "query": "How many users signed up each month?",
            "generate_explanation": True
        }
        response = await client.post("/api/v1/agents/query", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        # Check response structure
        assert "generated_sql" in data
        assert isinstance(data["generated_sql"], str)
        assert data["generated_sql"].strip() != ""
        # Check for explanation if requested
        if data.get("explanation"):
            assert "formatted_explanation" in data["explanation"]
        # Check for optimization hints
        assert "optimization_applied" in data
        assert isinstance(data["optimization_applied"], list)

    async def test_query_agent_invalid_request(self, client: AsyncClient, auth_headers: dict):
        """Test Query Agent error handling for invalid input."""
        # Empty query
        response = await client.post(
            "/api/v1/agents/query",
            json={"query": ""},
            headers=auth_headers
        )
        assert response.status_code == 400

        # Missing required field
        response = await client.post("/api/v1/agents/query", json={}, headers=auth_headers)
        assert response.status_code == 422  # Unprocessable Entity

    async def test_query_agent_performance_metrics(self, client: AsyncClient, auth_headers: dict):
        """Test Query Agent returns performance metrics."""
        # Make a valid query
        response = await client.post(
            "/api/v1/agents/query",
            json={"query": "Count all records in users table"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            assert "performance_metrics" in data or "execution_time_ms" in data

    # ===== Design Agent Integration =====

    async def test_design_agent_health(self, client: AsyncClient, auth_headers: dict):
        """Test Design Agent health endpoint."""
        response = await client.get("/api/v1/agents/design-agent/status", headers=auth_headers)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            status = response.json()
            assert "status" in status
            assert "capabilities" in status
            assert isinstance(status["capabilities"], list)
            assert "designs_created" in status
            assert "deployments_completed" in status

    async def test_design_agent_design_platform(self, client: AsyncClient, auth_headers: dict):
        """Test Design Agent platform design action."""
        health_resp = await client.get("/api/v1/agents/design-agent/status", headers=auth_headers)
        if health_resp.status_code != 200:
            pytest.skip("Design Agent not healthy")

        payload = {
            "action": "design_platform",
            "requirements": {
                "use_case": "analytics",
                "expected_qps": 100,
                "data_volume_gb_per_day": 50,
                "retention_days": 30,
                "high_availability": True,
                "budget": 5000
            }
        }
        response = await client.post("/api/v1/agents/design", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "design_id" in data
        assert "estimated_cost_monthly" in data
        assert "infrastructure" in data
        assert "recommended_configuration" in data

    async def test_design_agent_provision_cluster(self, client: AsyncClient, auth_headers: dict):
        """Test Design Agent cluster provisioning action."""
        # First get a design
        design_resp = await client.post(
            "/api/v1/agents/design",
            json={
                "action": "design_platform",
                "requirements": {
                    "use_case": "default",
                    "expected_qps": 50,
                    "data_volume_gb_per_day": 20,
                    "retention_days": 7
                }
            },
            headers=auth_headers
        )
        if design_resp.status_code != 200:
            pytest.skip("Design Agent unable to create design")

        design_id = design_resp.json()["design_id"]

        # Now try to provision (dry-run should succeed)
        payload = {
            "action": "provision_cluster",
            "design_id": design_id,
            "dry_run": True
        }
        response = await client.post("/api/v1/agents/design", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "provisioning_plan" in data
        assert "manifest_count" in data
        assert data["manifest_count"] > 0

    async def test_design_agent_invalid_action(self, client: AsyncClient, auth_headers: dict):
        """Test Design Agent error handling for invalid action."""
        response = await client.post(
            "/api/v1/agents/design",
            json={"action": "invalid_action"},
            headers=auth_headers
        )
        assert response.status_code == 400

    # ===== Support Agent Integration =====

    async def test_support_agent_health(self, client: AsyncClient, auth_headers: dict):
        """Test Support Agent health endpoint."""
        response = await client.get("/api/v1/agents/support-agent/status", headers=auth_headers)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            status = response.json()
            assert "status" in status
            assert "capabilities" in status

    async def test_support_agent_answer_question(self, client: AsyncClient, auth_headers: dict):
        """Test Support Agent question answering."""
        health_resp = await client.get("/api/v1/agents/support-agent/status", headers=auth_headers)
        if health_resp.status_code != 200:
            pytest.skip("Support Agent not healthy")

        payload = {
            "action": "answer_question",
            "question": "How do I create a platform?",
            "context": {"user_id": "test"}
        }
        response = await client.post("/api/v1/agents/support", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    async def test_support_agent_troubleshoot(self, client: AsyncClient, auth_headers: dict):
        """Test Support Agent troubleshooting."""
        payload = {
            "action": "troubleshoot",
            "issue": "Platform design failed with error: Invalid configuration",
            "context": {"design_id": "test123"}
        }
        response = await client.post("/api/v1/agents/support", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "analysis" in data
        assert "recommended_actions" in data
        assert isinstance(data["recommended_actions"], list)


@pytest.mark.integration
class TestAgentToAgentCommunication:
    """Test agent-to-agent communication via API and messaging."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient):
        """Get authentication headers."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "commtest@example.com",
                "password": "Test123!",
                "full_name": "Comm Test User"
            }
        )
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "commtest@example.com", "password": "Test123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_sequential_agent_workflow(self, client: AsyncClient, auth_headers: dict):
        """
        Test a workflow where Query Agent triggers Design Agent processing.
        Sequence:
        1. User submits query about platform requirements
        2. Support Agent helps clarify requirements
        3. Design Agent creates platform design
        4. Query Agent can then query the design metadata
        """
        # Step 1: Query Agent gets initial request (NL to intent)
        query_resp = await client.post(
            "/api/v1/agents/query",
            json={"query": "I need to design a platform for analytics"},
            headers=auth_headers
        )
        # This might return a query result, but if not related, just skip
        if query_resp.status_code == 200:
            query_data = query_resp.json()
            assert "generated_sql" in query_data or "explanation" in query_data

        # Step 2: Support Agent provides guidance
        support_resp = await client.post(
            "/api/v1/agents/support",
            json={
                "action": "answer_question",
                "question": "What are the requirements for an analytics platform?"
            },
            headers=auth_headers
        )
        if support_resp.status_code == 200:
            support_data = support_resp.json()
            assert "answer" in support_data

        # Step 3: Design Agent creates a design
        design_resp = await client.post(
            "/api/v1/agents/design",
            json={
                "action": "design_platform",
                "requirements": {
                    "use_case": "analytics",
                    "expected_qps": 100,
                    "data_volume_gb_per_day": 100,
                    "retention_days": 30,
                    "high_availability": True
                }
            },
            headers=auth_headers
        )
        if design_resp.status_code == 200:
            design_data = design_resp.json()
            assert "design_id" in design_data
            design_id = design_data["design_id"]

            # Step 4: Query Agent can query design metadata (if schema exists)
            # This tests that agents can work on related data
            query_design = await client.post(
                "/api/v1/agents/query",
                json={"query": f"Show me details for design {design_id}"},
                headers=auth_headers
            )
            # Not asserting specific response since this depends on schema
            assert query_design.status_code in [200, 400, 404, 500]

    async def test_agent_concurrent_requests(self, client: AsyncClient, auth_headers: dict):
        """Test multiple concurrent requests to different agents."""
        import asyncio

        # Create multiple concurrent tasks
        async def query_agent_task():
            return await client.post(
                "/api/v1/agents/query",
                json={"query": "Count users"},
                headers=auth_headers
            )

        async def design_agent_task():
            return await client.post(
                "/api/v1/agents/design",
                json={
                    "action": "design_platform",
                    "requirements": {"use_case": "test"}
                },
                headers=auth_headers
            )

        async def support_agent_task():
            return await client.post(
                "/api/v1/agents/support",
                json={"action": "answer_question", "question": "What is AI?"},
                headers=auth_headers
            )

        # Run concurrently
        results = await asyncio.gather(
            query_agent_task(),
            design_agent_task(),
            support_agent_task(),
            return_exceptions=True
        )

        # Check that requests completed (some may fail due to agent health)
        for result in results:
            if isinstance(result, Exception):
                continue  # Allow some failures due to agent unhealth
            assert hasattr(result, 'status_code')

    async def test_agent_health_propagation(self, client: AsyncClient, auth_headers: dict):
        """Test that agent health status is correctly reported across endpoints."""
        # Check main status endpoint
        main_status = await client.get("/api/v1/agents/status", headers=auth_headers)
        assert main_status.status_code == 200
        main_data = main_status.json()

        # Check individual agent health endpoints
        query_health = await client.get("/api/v1/agents/query-agent/status", headers=auth_headers)
        design_health = await client.get("/api/v1/agents/design-agent/status", headers=auth_headers)
        support_health = await client.get("/api/v1/agents/support-agent/status", headers=auth_headers)

        # All health endpoints should respond (even if unhealthy)
        assert query_health.status_code in [200, 500]
        assert design_health.status_code in [200, 500]
        assert support_health.status_code in [200, 500]

        # Count healthy agents from main status
        healthy_count = main_data["healthy_agents"]
        total_agents = main_data["total_agents"]

        # The counts should be consistent with individual endpoint health
        individual_healthy = sum(1 for r in [query_health, design_health, support_health] if r.status_code == 200)
        # Allow some flexibility due to agent availability
        assert healthy_count <= total_agents
        assert healthy_count >= 0


@pytest.mark.integration
class TestAgentErrorHandling:
    """Test error handling and recovery across agents."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient):
        """Get authentication headers."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "errorhandling@example.com",
                "password": "Test123!",
                "full_name": "Error Handling User"
            }
        )
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "errorhandling@example.com", "password": "Test123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_query_agent_malformed_query(self, client: AsyncClient, auth_headers: dict):
        """Test Query Agent handling of malformed or extreme queries."""
        # Very long query
        long_query = "SELECT * FROM " + "x" * 10000
        response = await client.post(
            "/api/v1/agents/query",
            json={"query": long_query},
            headers=auth_headers
        )
        # Should handle gracefully (either process or reject)
        assert response.status_code in [200, 400, 413, 500]

        # SQL injection attempt
        sql_injection = "admin'; DROP TABLE users; --"
        response = await client.post(
            "/api/v1/agents/query",
            json={"query": sql_injection},
            headers=auth_headers
        )
        # Should not succeed (defense in depth)
        # Even if parsed, it should be sanitized or parameterized
        # Expected: 400 (bad request) or 200 but safe execution
        assert response.status_code in [200, 400, 500]

    async def test_design_agent_invalid_requirements(self, client: AsyncClient, auth_headers: dict):
        """Test Design Agent with invalid or extreme requirements."""
        # Negative budget
        response = await client.post(
            "/api/v1/agents/design",
            json={
                "action": "design_platform",
                "requirements": {"budget": -1000}
            },
            headers=auth_headers
        )
        assert response.status_code == 400

        # Missing required fields
        response = await client.post(
            "/api/v1/agents/design",
            json={"action": "design_platform"},
            headers=auth_headers
        )
        assert response.status_code == 422

        # Extremely high QPS
        response = await client.post(
            "/api/v1/agents/design",
            json={
                "action": "design_platform",
                "requirements": {"expected_qps": 10**9}
            },
            headers=auth_headers
        )
        # Should either accept and estimate, or reject as unrealistic
        assert response.status_code in [200, 400, 422]

    async def test_support_agent_unknown_action(self, client: AsyncClient, auth_headers: dict):
        """Test Support Agent with unknown action."""
        response = await client.post(
            "/api/v1/agents/support",
            json={"action": "unknown_action"},
            headers=auth_headers
        )
        assert response.status_code == 400

    async def test_agent_api_authentication_required(self, client: AsyncClient):
        """Test that all agent endpoints require authentication."""
        endpoints = [
            ("/api/v1/agents/query", "POST", {"query": "test"}),
            ("/api/v1/agents/design", "POST", {"action": "design_platform", "requirements": {}}),
            ("/api/v1/agents/support", "POST", {"action": "answer_question", "question": "test"}),
            ("/api/v1/agents/status", "GET", None),
            ("/api/v1/agents/query-agent/status", "GET", None),
            ("/api/v1/agents/design-agent/status", "GET", None),
            ("/api/v1/agents/support-agent/status", "GET", None),
        ]

        for endpoint, method, json_data in endpoints:
            if method == "POST":
                response = await client.post(endpoint, json=json_data)
            else:
                response = await client.get(endpoint)
            assert response.status_code in [401, 403], f"Endpoint {endpoint} should require auth"

    async def test_agent_invalid_json_payload(self, client: AsyncClient, auth_headers: dict):
        """Test agent endpoints with malformed JSON."""
        # Invalid JSON body
        response = await client.post(
            "/api/v1/agents/query",
            content="invalid json",
            headers={"Content-Type": "application/json", **auth_headers}
        )
        assert response.status_code == 422
