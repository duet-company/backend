"""
Unit tests for Query Agent
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.agents.query_agent import QueryAgent, ClickHouseSchemaLoader, create_query_agent
from app.agents.base import AgentConfig
from app.models.query import QueryStatus, QueryType


class TestQueryAgent:
    """Tests for QueryAgent"""

    @pytest.fixture
    def agent_config(self):
        """Create test agent configuration"""
        return AgentConfig(
            name="test_query_agent",
            description="Test query agent",
            max_concurrent_tasks=5,
            timeout_seconds=60,
            retry_attempts=1,
            config={
                "llm_provider": "openai",
                "llm_model": "gpt-4",
                "max_results": 100,
                "enable_sql_validation": True
            }
        )

    @pytest.fixture
    def mock_schema_loader(self):
        """Mock ClickHouseSchemaLoader"""
        with patch('app.agents.query_agent.ClickHouseSchemaLoader') as mock:
            loader_instance = Mock()
            loader_instance.connect = Mock()
            loader_instance.get_schema.return_value = {
                "tables": {
                    "users": {
                        "engine": "MergeTree",
                        "columns": [
                            {"name": "id", "type": "UInt32", "primary_key": True},
                            {"name": "name", "type": "String"},
                            {"name": "email", "type": "String"},
                            {"name": "created_at", "type": "DateTime"}
                        ]
                    },
                    "orders": {
                        "engine": "MergeTree",
                        "columns": [
                            {"name": "id", "type": "UInt32", "primary_key": True},
                            {"name": "user_id", "type": "UInt32"},
                            {"name": "amount", "type": "Float64"},
                            {"name": "status", "type": "String"}
                        ]
                    }
                }
            }
            loader_instance.format_schema_for_prompt.return_value = "Mock schema"
            mock.return_value = loader_instance
            yield loader_instance

    @pytest.fixture
    def mock_clickhouse_client(self):
        """Mock ClickHouse client"""
        client = Mock()
        client.execute = Mock(return_value=([{'id': 1, 'name': 'Test'}]))
        return client

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent_config, mock_schema_loader):
        """Test QueryAgent initialization"""
        with patch('app.agents.query_agent.SessionLocal'):
            agent = QueryAgent(agent_config)
            await agent.initialize()

            assert agent.status.value == "idle"
            assert agent.schema_loader is not None
            mock_schema_loader.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_shutdown(self, agent_config):
        """Test QueryAgent shutdown"""
        with patch('app.agents.query_agent.SessionLocal'):
            agent = QueryAgent(agent_config)
            await agent.initialize()

            # Set a mock schema loader
            agent.schema_loader = Mock()
            agent.schema_loader.disconnect = Mock()

            await agent.shutdown()

            agent.schema_loader.disconnect.assert_called_once()
            assert agent.status.value == "shutdown"

    @pytest.mark.asyncio
    async def test_process_missing_query(self, agent_config):
        """Test that missing query raises error"""
        with patch('app.agents.query_agent.SessionLocal'):
            agent = QueryAgent(agent_config)
            await agent.initialize()

            with pytest.raises(ValueError, match="Missing required field"):
                await agent.process({})

    @pytest.mark.asyncio
    async def test_sql_generation_openai(self, agent_config):
        """Test SQL generation with OpenAI"""
        with patch('app.agents.query_agent.SessionLocal'), \
             patch('app.agents.query_agent.httpx.AsyncClient') as mock_client:

            # Mock OpenAI response
            mock_response = Mock()
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "SELECT * FROM users LIMIT 100"
                    }
                }]
            }
            mock_response.raise_for_status = Mock()

            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            agent = QueryAgent(agent_config)
            await agent.initialize()

            sql = await agent._generate_sql("Show me all users", "Mock schema")

            assert sql == "SELECT * FROM users LIMIT 100"
            mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_sql_generation_anthropic(self, agent_config):
        """Test SQL generation with Anthropic"""
        agent_config.config["llm_provider"] = "anthropic"
        agent_config.config["llm_api_key"] = "test-key"

        with patch('app.agents.query_agent.SessionLocal'), \
             patch('app.agents.query_agent.httpx.AsyncClient') as mock_client:

            # Mock Anthropic response
            mock_response = Mock()
            mock_response.json.return_value = {
                "content": [{
                    "text": "SELECT * FROM users LIMIT 100"
                }]
            }
            mock_response.raise_for_status = Mock()

            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            agent = QueryAgent(agent_config)
            await agent.initialize()

            sql = await agent._generate_sql("Show me all users", "Mock schema")

            assert sql == "SELECT * FROM users LIMIT 100"

    def test_sql_extraction_from_markdown(self, agent_config):
        """Test extracting SQL from LLM markdown response"""
        with patch('app.agents.query_agent.SessionLocal'):
            agent = QueryAgent(agent_config)

            response = "Here is the SQL:\n```sql\nSELECT * FROM users LIMIT 100\n```"
            sql = agent._extract_sql_from_response(response)
            assert sql == "SELECT * FROM users LIMIT 100"

            response2 = "```SELECT * FROM users LIMIT 100```"
            sql2 = agent._extract_sql_from_response(response2)
            assert sql2 == "SELECT * FROM users LIMIT 100"

            response3 = "SELECT * FROM users LIMIT 100"
            sql3 = agent._extract_sql_from_response(response3)
            assert sql3 == "SELECT * FROM users LIMIT 100"

    def test_sql_validation_valid(self, agent_config):
        """Test SQL validation with valid SELECT"""
        with patch('app.agents.query_agent.SessionLocal'):
            agent = QueryAgent(agent_config)
            # Should not raise
            agent._validate_sql("SELECT * FROM users LIMIT 10")

    def test_sql_validation_dangerous(self, agent_config):
        """Test SQL validation blocks dangerous operations"""
        with patch('app.agents.query_agent.SessionLocal'):
            agent = QueryAgent(agent_config)

            with pytest.raises(ValueError, match="dangerous"):
                agent._validate_sql("DROP TABLE users")

            with pytest.raises(ValueError, match="dangerous"):
                agent._validate_sql("DELETE FROM users")

            with pytest.raises(ValueError, match="Only SELECT"):
                agent._validate_sql("INSERT INTO users VALUES (1)")

    @pytest.mark.asyncio
    async def test_execute_query_success(self, agent_config, mock_schema_loader, mock_clickhouse_client):
        """Test successful query execution"""
        # Mock the result from execute
        mock_result = (
            [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}],  # rows
            [('id', 'UInt32'), ('name', 'String')]  # columns
        )
        mock_clickhouse_client.execute.return_value = mock_result
        mock_schema_loader.client = mock_clickhouse_client

        with patch('app.agents.query_agent.SessionLocal'):
            agent = QueryAgent(agent_config)
            agent.schema_loader = mock_schema_loader

            rows, columns, exec_time = await agent._execute_query("SELECT * FROM users")

            assert len(rows) == 2
            assert columns == ['id', 'name']
            assert isinstance(exec_time, int)

    @pytest.mark.asyncio
    async def test_format_results(self, agent_config):
        """Test result formatting"""
        with patch('app.agents.query_agent.SessionLocal'):
            agent = QueryAgent(agent_config)

            rows = [
                (1, 'Alice', 'alice@example.com'),
                (2, 'Bob', 'bob@example.com')
            ]
            columns = ['id', 'name', 'email']

            formatted = agent._format_results(rows, columns)

            assert 'id | name | email' in formatted
            assert 'Alice' in formatted
            assert 'Bob' in formatted

    @pytest.mark.asyncio
    async def test_format_results_empty(self, agent_config):
        """Test formatting empty results"""
        with patch('app.agents.query_agent.SessionLocal'):
            agent = QueryAgent(agent_config)

            formatted = agent._format_results([], [])

            assert formatted == "No results found."

    @pytest.mark.asyncio
    async def test_end_to_end_success(
        self, agent_config, mock_schema_loader, mock_clickhouse_client
    ):
        """Test end-to-end query processing"""
        # Mock LLM call
        with patch('app.agents.query_agent.SessionLocal'), \
             patch('app.agents.query_agent.httpx.AsyncClient') as mock_http:

            mock_http_response = Mock()
            mock_http_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "SELECT * FROM users LIMIT 100"
                    }
                }]
            }
            mock_http_response.raise_for_status = Mock()

            mock_http_instance = AsyncMock()
            mock_http_instance.post.return_value = mock_http_response
            mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_http_instance)
            mock_http.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock ClickHouse execution
            mock_result = (
                [{'id': 1, 'name': 'Alice'}],
                [('id', 'UInt32'), ('name', 'String')]
            )
            mock_clickhouse_client.execute.return_value = mock_result
            mock_schema_loader.client = mock_clickhouse_client

            agent = QueryAgent(agent_config)
            agent.schema_loader = mock_schema_loader
            await agent.initialize()

            # Mock QueryModel.save to avoid DB writes
            with patch('app.agents.query_agent.QueryModel') as MockQueryModel:
                mock_query = Mock()
                mock_query.id = 1
                mock_query.mark_completed = Mock()
                MockQueryModel.return_value = mock_query

                result = await agent.process({
                    "query": "Show me all users",
                    "user_id": 1
                })

                assert result["generated_sql"] == "SELECT * FROM users LIMIT 100"
                assert result["row_count"] == 1
                assert result["query_id"] == 1
                assert "id | name" in result["formatted_output"]


@pytest.mark.asyncio
async def test_create_query_agent_factory():
    """Test factory function creates agent with correct config"""
    with patch('app.agents.query_agent.SessionLocal'):
        agent = create_query_agent()

        assert agent.config.name == "query_agent"
        assert agent.config.enabled is True
        assert agent.config.max_concurrent_tasks == 10
        assert agent.config.config["llm_provider"] == "openai"
        assert agent.config.config["max_results"] == 1000
