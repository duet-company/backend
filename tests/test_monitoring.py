"""
Tests for monitoring and metrics
"""

import pytest
from fastapi.testclient import TestClient
import time

from app.main import app
from app.core.metrics import (
    MetricsContext, AgentMetricsContext, DatabaseMetricsContext,
    record_llm_request, record_query_execution, record_chat_request,
    update_db_connections, update_agent_queue, update_task_queue,
    record_task_processed, update_data_source_status, record_data_source_query,
    initialize_metrics
)

client = TestClient(app)


class TestMetrics:
    """Test metrics collection."""

    def test_metrics_initialization(self):
        """Test that metrics are initialized properly."""
        initialize_metrics(build_version="0.1.0", git_commit="abc123")

    def test_api_metrics_context(self):
        """Test API metrics context manager."""
        with MetricsContext("GET", "/api/test"):
            time.sleep(0.01)

    def test_api_metrics_context_with_error(self):
        """Test API metrics context manager with error."""
        with pytest.raises(ValueError):
            with MetricsContext("GET", "/api/error"):
                raise ValueError("Test error")

    def test_agent_metrics_context(self):
        """Test agent metrics context manager."""
        with AgentMetricsContext("QueryAgent", "nl2sql"):
            time.sleep(0.01)

    def test_agent_metrics_context_with_error(self):
        """Test agent metrics context manager with error."""
        with pytest.raises(ValueError):
            with AgentMetricsContext("QueryAgent", "nl2sql"):
                raise ValueError("Test error")

    def test_database_metrics_context(self):
        """Test database metrics context manager."""
        with DatabaseMetricsContext("postgres", "select"):
            time.sleep(0.001)

    def test_database_metrics_context_with_error(self):
        """Test database metrics context manager with error."""
        with pytest.raises(ValueError):
            with DatabaseMetricsContext("postgres", "select"):
                raise ValueError("Test error")

    def test_record_llm_request(self):
        """Test recording LLM request metrics."""
        record_llm_request(
            provider="anthropic",
            model="claude-3-opus",
            status="success",
            prompt_tokens=100,
            completion_tokens=50,
            latency=2.5
        )

    def test_record_query_execution(self):
        """Test recording query execution metrics."""
        record_query_execution(
            status="success",
            query_type="select",
            latency=1.2
        )

    def test_record_chat_request(self):
        """Test recording chat request metrics."""
        record_chat_request(
            status="success",
            latency=2.0
        )

    def test_update_db_connections(self):
        """Test updating database connection metrics."""
        update_db_connections(
            db_type="postgres",
            active=5,
            pool_size=10
        )

    def test_update_agent_queue(self):
        """Test updating agent queue metrics."""
        update_agent_queue(
            agent_name="QueryAgent",
            queue_size=25
        )

    def test_update_task_queue(self):
        """Test updating task queue metrics."""
        update_task_queue(
            queue_name="default",
            size=100
        )

    def test_record_task_processed(self):
        """Test recording task processed metrics."""
        record_task_processed(
            queue_name="default",
            status="success"
        )

    def test_update_data_source_status(self):
        """Test updating data source status."""
        update_data_source_status(
            source_id="test-source-1",
            source_type="clickhouse",
            status=1  # connected
        )

    def test_record_data_source_query(self):
        """Test recording data source query metrics."""
        record_data_source_query(
            source_id="test-source-1",
            source_type="clickhouse",
            status="success"
        )


class TestMonitoringAPI:
    """Test monitoring API endpoints."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "components" in data
        assert "metrics" in data

    def test_readiness_check(self):
        """Test readiness check endpoint."""
        response = client.get("/health/ready")
        # May return 200 or 503 depending on initialization state
        assert response.status_code in [200, 503]

    def test_liveness_check(self):
        """Test liveness check endpoint."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    def test_platform_metrics(self):
        """Test platform metrics endpoint."""
        response = client.get("/api/v1/monitoring/metrics/platform")
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "api" in data
        assert "agents" in data
        assert "database" in data
        assert "system" in data

    def test_get_alerts(self):
        """Test getting alerts."""
        response = client.get("/api/v1/monitoring/alerts")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "alerts" in data
        assert isinstance(data["alerts"], list)

    def test_get_alerts_with_filters(self):
        """Test getting alerts with filters."""
        response = client.get("/api/v1/monitoring/alerts?severity=warning&active_only=true")
        assert response.status_code == 200

    def test_agents_status(self):
        """Test getting agents status."""
        response = client.get("/api/v1/monitoring/agents/status")
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "total_agents" in data
        assert "agents" in data
        assert isinstance(data["agents"], dict)

    def test_query_performance(self):
        """Test query performance endpoint."""
        response = client.get("/api/v1/monitoring/query-performance?hours=24&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "since" in data
        assert "until" in data
        assert "total_queries" in data
        assert "avg_latency_ms" in data

    def test_data_sources_status(self):
        """Test data sources status endpoint."""
        response = client.get("/api/v1/monitoring/data-sources/status")
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "data_sources" in data
        assert "total_count" in data

    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        # Should return Prometheus text format
        assert "text/plain" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_metrics_context_integration():
    """Test metrics context managers work correctly."""
    # API context
    with MetricsContext("POST", "/api/v1/query"):
        await asyncio.sleep(0.01)

    # Agent context
    with AgentMetricsContext("QueryAgent", "nl2sql"):
        await asyncio.sleep(0.01)

    # Database context
    with DatabaseMetricsContext("clickhouse", "select"):
        await asyncio.sleep(0.001)

    # All should complete without errors


# Import asyncio for async tests
import asyncio
