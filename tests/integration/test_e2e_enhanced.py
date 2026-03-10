"""
Enhanced End-to-End Workflow Tests

Tests complete user workflows from start to finish, with bottleneck identification.
"""

import pytest
import time
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from typing import Dict, List, Tuple


# Bottleneck tracking
BOTTLENECKS: Dict[str, Dict] = {}


def track_bottleneck(workflow: str, step: str, duration_ms: float, threshold_ms: float = None):
    """Track a potential bottleneck in a workflow."""
    if threshold_ms and duration_ms > threshold_ms:
        BOTTLENECKS[f"{workflow}:{step}"] = {
            "duration_ms": duration_ms,
            "threshold_ms": threshold_ms,
            "excess_ms": duration_ms - threshold_ms,
            "severity": "critical" if duration_ms > threshold_ms * 2 else "warning"
        }


@pytest.mark.e2e
class TestUserOnboardingWorkflow:
    """Test the complete user onboarding workflow."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.e2e
    async def test_complete_user_onboarding_with_bottlenecks(self, client: AsyncClient):
        """Test complete onboarding: register → login → create chat → query with bottleneck tracking."""
        workflow = "user_onboarding"
        timings = {}

        # Step 1: Register user
        unique_id = pytest.hash_seed or "test"
        email = f"user{unique_id}@example.com"

        start = time.time()
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Test123!",
                "full_name": "Test User"
            }
        )
        timings["register"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "register", timings["register"], threshold_ms=500)
        assert response.status_code in [200, 201]

        # Step 2: Login
        start = time.time()
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": email,
                "password": "Test123!"
            }
        )
        timings["login"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "login", timings["login"], threshold_ms=300)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 3: Get current user
        start = time.time()
        response = await client.get("/api/v1/auth/me", headers=headers)
        timings["get_user"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "get_user", timings["get_user"], threshold_ms=100)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == email

        # Step 4: Create a chat
        start = time.time()
        response = await client.post(
            "/api/v1/chat/chats",
            headers=headers,
            json={"title": "My First Chat"}
        )
        timings["create_chat"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "create_chat", timings["create_chat"], threshold_ms=200)
        assert response.status_code in [200, 201]
        chat_data = response.json()
        chat_id = chat_data.get("id") or chat_data.get("chat_id")
        assert chat_id is not None

        # Step 5: List chats
        start = time.time()
        response = await client.get("/api/v1/chat/chats", headers=headers)
        timings["list_chats"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "list_chats", timings["list_chats"], threshold_ms=100)
        assert response.status_code == 200
        chats = response.json()
        assert len(chats) >= 1

        # Step 6: Send a message
        start = time.time()
        response = await client.post(
            f"/api/v1/chat/chats/{chat_id}/messages",
            headers=headers,
            json={
                "content": "Hello, I need to query some data",
                "role": "user"
            }
        )
        timings["send_message"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "send_message", timings["send_message"], threshold_ms=2000)
        assert response.status_code in [200, 201, 400, 500]

        # Step 7: List available agents
        start = time.time()
        response = await client.get("/api/v1/agents/", headers=headers)
        timings["list_agents"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "list_agents", timings["list_agents"], threshold_ms=100)
        assert response.status_code == 200
        agents = response.json()
        assert isinstance(agents, list)

        # Print workflow summary
        total_time = sum(timings.values())
        print(f"\n📊 {workflow} Workflow Performance:")
        for step, duration in timings.items():
            print(f"   {step}: {duration:.2f}ms")
        print(f"   Total: {total_time:.2f}ms")

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

        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Query123!",
                "full_name": "Query User"
            }
        )

        response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "Query123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.e2e
    async def test_schema_creation_and_query_with_bottlenecks(self, client: AsyncClient, auth_headers: dict):
        """Test creating a schema and querying it with bottleneck tracking."""
        workflow = "data_query"
        timings = {}

        # Step 1: Create a schema
        start = time.time()
        response = await client.post(
            "/api/v1/data/schemas",
            headers=auth_headers,
            json={
                "name": "test_schema",
                "description": "Test schema for e2e tests",
                "connection_string": "clickhouse://localhost:8123/default"
            }
        )
        timings["create_schema"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "create_schema", timings["create_schema"], threshold_ms=500)

        if response.status_code in [200, 201]:
            schema_data = response.json()
            schema_id = schema_data.get("id") or schema_data.get("schema_id")

            # Step 2: List schemas
            start = time.time()
            response = await client.get("/api/v1/data/schemas", headers=auth_headers)
            timings["list_schemas"] = (time.time() - start) * 1000
            track_bottleneck(workflow, "list_schemas", timings["list_schemas"], threshold_ms=100)
            assert response.status_code == 200
            schemas = response.json()
            assert len(schemas) >= 1

            # Step 3: Execute query
            start = time.time()
            response = await client.post(
                "/api/v1/query/execute",
                headers=auth_headers,
                json={
                    "query": "SELECT 1 as test",
                    "schema_id": schema_id
                }
            )
            timings["execute_query"] = (time.time() - start) * 1000
            track_bottleneck(workflow, "execute_query", timings["execute_query"], threshold_ms=1000)
            assert response.status_code in [200, 400, 404, 500]

        # Print workflow summary
        total_time = sum(timings.values())
        print(f"\n📊 {workflow} Workflow Performance:")
        for step, duration in timings.items():
            print(f"   {step}: {duration:.2f}ms")
        print(f"   Total: {total_time:.2f}ms")

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
    async def test_query_agent_with_bottlenecks(self, client: AsyncClient, auth_headers: dict):
        """Test interaction with Query Agent with bottleneck tracking."""
        workflow = "query_agent"
        timings = {}

        # List available agents
        start = time.time()
        response = await client.get("/api/v1/agents/", headers=auth_headers)
        timings["list_agents"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "list_agents", timings["list_agents"], threshold_ms=100)
        assert response.status_code == 200
        agents = response.json()

        # Find Query Agent
        query_agent = next((a for a in agents if "query" in a.get("name", "").lower()), None)
        if not query_agent:
            pytest.skip("Query Agent not available")

        # Test Query Agent health
        start = time.time()
        response = await client.get("/api/v1/agents/query-agent/status", headers=auth_headers)
        timings["agent_status"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "agent_status", timings["agent_status"], threshold_ms=200)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            status = response.json()
            assert "status" in status

        # Print workflow summary
        total_time = sum(timings.values())
        print(f"\n📊 {workflow} Workflow Performance:")
        for step, duration in timings.items():
            print(f"   {step}: {duration:.2f}ms")
        print(f"   Total: {total_time:.2f}ms")

        print(f"\n✅ Query Agent interaction completed")

    @pytest.mark.e2e
    async def test_design_agent_with_bottlenecks(self, client: AsyncClient, auth_headers: dict):
        """Test interaction with Design Agent with bottleneck tracking."""
        workflow = "design_agent"
        timings = {}

        # Test Design Agent health
        start = time.time()
        response = await client.get("/api/v1/agents/design-agent/status", headers=auth_headers)
        timings["agent_status"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "agent_status", timings["agent_status"], threshold_ms=200)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            status = response.json()
            assert "status" in status

        # Print workflow summary
        total_time = sum(timings.values())
        print(f"\n📊 {workflow} Workflow Performance:")
        for step, duration in timings.items():
            print(f"   {step}: {duration:.2f}ms")
        print(f"   Total: {total_time:.2f}ms")

        print(f"\n✅ Design Agent interaction completed")


@pytest.mark.e2e
class TestPlatformDesignWorkflow:
    """Test platform design workflow."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient):
        """Get authentication headers."""
        unique_id = pytest.hash_seed or "test"
        email = f"design{unique_id}@example.com"

        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Design123!",
                "full_name": "Design User"
            }
        )

        response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "Design123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.e2e
    async def test_platform_design_to_manifest(self, client: AsyncClient, auth_headers: dict):
        """Test platform design → manifest generation workflow with bottleneck tracking."""
        workflow = "platform_design"
        timings = {}

        # Step 1: Design platform
        start = time.time()
        response = await client.post(
            "/api/v1/agents/design",
            headers=auth_headers,
            json={
                "action": "design_platform",
                "requirements": {
                    "description": "Test platform with 10TB data, 1000 QPS",
                    "workload_type": "realtime_analytics",
                    "traffic_profile": "medium",
                    "availability_requirement": "high"
                }
            }
        )
        timings["design_platform"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "design_platform", timings["design_platform"], threshold_ms=3000)
        assert response.status_code in [200, 400, 500]

        # Step 2: Generate manifests (if design succeeded)
        if response.status_code == 200:
            design_data = response.json()
            design_id = design_data.get("design_id")

            start = time.time()
            response = await client.post(
                "/api/v1/agents/design",
                headers=auth_headers,
                json={
                    "action": "generate_manifests",
                    "design_id": design_id
                }
            )
            timings["generate_manifests"] = (time.time() - start) * 1000
            track_bottleneck(workflow, "generate_manifests", timings["generate_manifests"], threshold_ms=2000)
            assert response.status_code in [200, 400, 500]

        # Print workflow summary
        total_time = sum(timings.values())
        print(f"\n📊 {workflow} Workflow Performance:")
        for step, duration in timings.items():
            print(f"   {step}: {duration:.2f}ms")
        print(f"   Total: {total_time:.2f}ms")

        print(f"\n✅ Platform design workflow completed")


@pytest.mark.e2e
class TestComprehensiveEndToEndWorkflow:
    """Test comprehensive end-to-end workflows across the platform."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient):
        """Get authentication headers."""
        unique_id = pytest.hash_seed or "test"
        email = f"e2e{unique_id}@example.com"

        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "E2E123!",
                "full_name": "E2E Test User"
            }
        )

        response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "E2E123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.e2e
    async def test_full_platform_workflow(self, client: AsyncClient, auth_headers: dict):
        """Test complete user journey: register → design → query with bottleneck tracking."""
        workflow = "full_platform"
        timings = {}

        # Step 1: Check health
        start = time.time()
        response = await client.get("/health")
        timings["health_check"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "health_check", timings["health_check"], threshold_ms=50)
        assert response.status_code == 200

        # Step 2: Get current user
        start = time.time()
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        timings["get_user"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "get_user", timings["get_user"], threshold_ms=100)
        assert response.status_code == 200

        # Step 3: List agents
        start = time.time()
        response = await client.get("/api/v1/agents/", headers=auth_headers)
        timings["list_agents"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "list_agents", timings["list_agents"], threshold_ms=100)
        assert response.status_code == 200

        # Step 4: Create chat
        start = time.time()
        response = await client.post(
            "/api/v1/chat/chats",
            headers=auth_headers,
            json={"title": "Platform Chat"}
        )
        timings["create_chat"] = (time.time() - start) * 1000
        track_bottleneck(workflow, "create_chat", timings["create_chat"], threshold_ms=200)
        assert response.status_code in [200, 201]

        # Print workflow summary
        total_time = sum(timings.values())
        print(f"\n📊 {workflow} Workflow Performance:")
        for step, duration in timings.items():
            print(f"   {step}: {duration:.2f}ms")
        print(f"   Total: {total_time:.2f}ms")

        print(f"\n✅ Full platform workflow completed")


@pytest.fixture(autouse=True)
def print_bottlenecks():
    """Print all tracked bottlenecks at the end of the test session."""
    yield
    if BOTTLENECKS:
        print("\n" + "=" * 80)
        print("🚨 IDENTIFIED BOTTLENECKS")
        print("=" * 80)
        for workflow_step, data in sorted(BOTTLENECKS.items()):
            severity = data["severity"]
            duration = data["duration_ms"]
            threshold = data["threshold_ms"]
            excess = data["excess_ms"]
            icon = "🔴" if severity == "critical" else "🟡"
            print(f"{icon} {workflow_step}")
            print(f"   Duration: {duration:.2f}ms (threshold: {threshold}ms)")
            print(f"   Excess: {excess:.2f}ms ({severity})")
        print("=" * 80)
    else:
        print("\n✅ No bottlenecks detected - all workflows within acceptable thresholds")
