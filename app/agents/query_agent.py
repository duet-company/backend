"""
Query Agent (NL → SQL)

AI agent that translates natural language queries into SQL for ClickHouse
and executes them, returning formatted results.

Enhanced with:
- Query result caching
- Query optimization hints
- Query explanation features
- Multi-dialect SQL support
- Performance metrics tracking
"""

import logging
import os
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
from clickhouse_driver import Client as ClickHouseClient

from app.agents.base import BaseAgent, AgentConfig, AgentStatus
from app.models.query import Query as QueryModel, QueryStatus, QueryType
from app.core.database import SessionLocal
from app.agents.query_cache import QueryCache
from app.agents.query_optimizer import QueryOptimizer
from app.agents.query_explainer import QueryExplainer, SQLDialect


logger = logging.getLogger("agents.query_agent")


class ClickHouseSchemaLoader:
    """Loads and caches ClickHouse schema information"""

    def __init__(self, clickhouse_url: str = None):
        self.clickhouse_url = clickhouse_url or os.getenv(
            "CLICKHOUSE_URL",
            "clickhouse://default:@localhost:9000/default"
        )
        self.client: Optional[ClickHouseClient] = None
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes

    def connect(self) -> None:
        """Connect to ClickHouse"""
        if self.client is None:
            self.client = ClickHouseClient.from_url(self.clickhouse_url)
            logger.info("Connected to ClickHouse")

    def disconnect(self) -> None:
        """Disconnect from ClickHouse"""
        if self.client:
            self.client.disconnect()
            self.client = None

    def get_schema(self, refresh: bool = False) -> Dict[str, Any]:
        """
        Get database schema (tables, columns, types)

        Args:
            refresh: Force refresh cache

        Returns:
            Schema dictionary
        """
        if (self._schema_cache is None or refresh or
            (self._cache_timestamp and
             (datetime.utcnow() - self._cache_timestamp).total_seconds() > self._cache_ttl_seconds)):
            self._fetch_schema()

        return self._schema_cache

    def _fetch_schema(self) -> None:
        """Fetch schema from ClickHouse and cache it"""
        if self.client is None:
            self.connect()

        logger.info("Fetching ClickHouse schema")

        try:
            # Get list of tables
            tables_result = self.client.execute(
                "SELECT name, engine, create_table_query FROM system.tables "
                "WHERE database = currentDatabase() AND name NOT LIKE '.%'"
            )

            schema = {"tables": {}}

            for table_name, engine, create_query in tables_result:
                # Get columns for each table
                columns_result = self.client.execute(
                    "SELECT name, type, default_expression, is_in_primary_key, "
                    "comment FROM system.columns "
                    "WHERE database = currentDatabase() AND table = %(table)s "
                    "ORDER BY position",
                    {"table": table_name}
                )

                columns = []
                for col_name, col_type, default, is_pk, comment in columns_result:
                    columns.append({
                        "name": col_name,
                        "type": col_type,
                        "default": default,
                        "primary_key": is_pk,
                        "description": comment
                    })

                schema["tables"][table_name] = {
                    "engine": engine,
                    "columns": columns,
                    "create_query": create_query
                }

            self._schema_cache = schema
            self._cache_timestamp = datetime.utcnow()

            logger.info(f"Schema fetched: {len(schema['tables'])} tables")

        except Exception as e:
            logger.error(f"Failed to fetch schema: {e}")
            raise

    def format_schema_for_prompt(self) -> str:
        """Format schema as human-readable text for LLM prompt"""
        schema = self.get_schema()

        lines = ["ClickHouse Database Schema:", ""]

        for table_name, table_info in sorted(schema["tables"].items()):
            lines.append(f"Table: {table_name}")
            lines.append(f"  Engine: {table_info['engine']}")
            lines.append("  Columns:")

            for col in table_info["columns"]:
                pk_marker = " (PK)" if col["primary_key"] else ""
                desc = f" - {col['name']}: {col['type']}{pk_marker}"
                if col["description"]:
                    desc += f" ({col['description']})"
                lines.append(f"    {desc}")

            lines.append("")

        return "\n".join(lines)


class QueryAgent(BaseAgent):
    """
    AI Query Agent that translates natural language to SQL and executes queries.

    Enhanced with caching, optimization, and explanation features.

    Configuration:
        llm_api_key: API key for LLM (OpenAI, Anthropic, etc.)
        llm_provider: "openai" or "anthropic" (default: openai)
        llm_model: Model name (default: gpt-4)
        clickhouse_url: ClickHouse connection URL
        max_results: Maximum rows to return (default: 1000)
        enable_sql_validation: Validate generated SQL (default: True)
        enable_cache: Enable query result caching (default: True)
        cache_ttl_seconds: Cache TTL in seconds (default: 3600)
        enable_optimization: Enable query optimization hints (default: True)
        enable_explanation: Enable query explanation (default: True)
        sql_dialect: SQL dialect for explanation (default: clickhouse)
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)

        self.llm_api_key = config.config.get("llm_api_key") or os.getenv("OPENAI_API_KEY")
        self.llm_provider = config.config.get("llm_provider", "openai")
        self.llm_model = config.config.get("llm_model", "gpt-4")
        self.clickhouse_url = config.config.get("clickhouse_url") or os.getenv(
            "CLICKHOUSE_URL",
            "clickhouse://default:@localhost:9000/default"
        )
        self.max_results = config.config.get("max_results", 1000)
        self.enable_sql_validation = config.config.get("enable_sql_validation", True)
        self.enable_cache = config.config.get("enable_cache", True)
        self.cache_ttl_seconds = config.config.get("cache_ttl_seconds", 3600)
        self.enable_optimization = config.config.get("enable_optimization", True)
        self.enable_explanation = config.config.get("enable_explanation", True)

        # Parse SQL dialect
        dialect_str = config.config.get("sql_dialect", "clickhouse").lower()
        try:
            self.sql_dialect = SQLDialect(dialect_str)
        except ValueError:
            logger.warning(f"Unsupported SQL dialect: {dialect_str}, using clickhouse")
            self.sql_dialect = SQLDialect.CLICKHOUSE

        self.schema_loader: Optional[ClickHouseSchemaLoader] = None
        self.db: Optional[SessionLocal] = None
        self.query_cache: Optional[QueryCache] = None
        self.query_optimizer: Optional[QueryOptimizer] = None
        self.query_explainer: Optional[QueryExplainer] = None

        # Performance metrics
        self._query_metrics: Dict[str, Any] = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_generation_time_ms": 0,
            "total_execution_time_ms": 0,
            "sql_errors": 0,
            "optimization_applied": 0
        }

    async def _on_initialize(self) -> None:
        """Initialize Query Agent - load schema and connect to databases"""
        logger.info("Initializing Query Agent")

        # Initialize session factory
        self.db = SessionLocal

        # Initialize ClickHouse schema loader
        self.schema_loader = ClickHouseSchemaLoader(self.clickhouse_url)
        self.schema_loader.connect()

        # Test schema load
        schema = self.schema_loader.get_schema()
        logger.info(f"Query Agent initialized with {len(schema['tables'])} tables")

        # Initialize query cache (if enabled)
        if self.enable_cache:
            self.query_cache = QueryCache(
                max_entries=self.config.config.get("cache_max_entries", 1000),
                max_memory_mb=self.config.config.get("cache_max_memory_mb", 100),
                ttl_seconds=self.cache_ttl_seconds
            )
            logger.info("Query cache enabled")

        # Initialize query optimizer (if enabled)
        if self.enable_optimization:
            self.query_optimizer = QueryOptimizer()
            logger.info("Query optimizer enabled")

        # Initialize query explainer (if enabled)
        if self.enable_explanation:
            self.query_explainer = QueryExplainer(dialect=self.sql_dialect)
            logger.info(f"Query explainer enabled (dialect: {self.sql_dialect.value})")

    async def _on_shutdown(self) -> None:
        """Shutdown Query Agent - close connections"""
        logger.info("Shutting down Query Agent")

        # Log final cache stats
        if self.query_cache:
            cache_stats = self.query_cache.get_stats()
            logger.info(f"Cache stats: {cache_stats}")

        if self.schema_loader:
            self.schema_loader.disconnect()

    async def _on_process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a natural language query with enhanced features.

        Args:
            input_data: Must contain:
                - query: Natural language query string
                - user_id: (optional) user ID for logging
                - generate_explanation: (optional) Whether to generate explanation (default: config)
                - apply_optimization: (optional) Whether to apply optimization hints (default: config)

        Returns:
            Dict with:
                - natural_language: original query
                - generated_sql: SQL that was generated (possibly optimized)
                - columns: list of column names
                - rows: list of result rows
                - row_count: number of rows returned
                - execution_time_ms: query execution time
                - formatted_output: human-readable result string
                - cache_hit: (bool) whether result was from cache
                - optimization_applied: (list) optimization hints applied
                - explanation: (optional) query explanation if requested
                - metrics: performance metrics for this query
        """
        natural_query = input_data.get("query")
        user_id = input_data.get("user_id")
        generate_explanation = input_data.get("generate_explanation", self.enable_explanation)
        apply_optimization = input_data.get("apply_optimization", self.enable_optimization)

        if not natural_query:
            raise ValueError("Missing required field: query")

        logger.info(f"Processing query: {natural_query}")
        start_total_time = time.time()

        # Create query record
        query_record = QueryModel(
            user_id=user_id or 0,  # Default to 0 if not provided
            natural_language=natural_query,
            query_type=QueryType.NATURAL_LANGUAGE,
            status=QueryStatus.RUNNING
        )
        query_record.save()

        # Get schema for multiple purposes
        schema_text = self.schema_loader.format_schema_for_prompt()
        schema_dict = self.schema_loader.get_schema()

        # Check cache first (if enabled)
        cached_result = None
        if self.enable_cache and self.query_cache:
            cached_result = self.query_cache.get(natural_query, schema_text)
            if cached_result:
                self._query_metrics["cache_hits"] += 1
                logger.info(f"Cache hit for query: {natural_query[:50]}...")
                return {
                    **cached_result,
                    "cache_hit": True,
                    "metrics": {
                        "generation_time_ms": 0,
                        "execution_time_ms": 0,
                        "total_time_ms": int((time.time() - start_total_time) * 1000),
                        "cache_hit": True
                    }
                }
            else:
                self._query_metrics["cache_misses"] += 1

        try:
            # Generate SQL using LLM
            gen_start = time.time()
            sql = await self._generate_sql(natural_query, schema_text)
            generation_time_ms = int((time.time() - gen_start) * 1000)

            self._query_metrics["total_generation_time_ms"] += generation_time_ms
            self._query_metrics["total_queries"] += 1

            logger.info(f"Generated SQL: {sql}")
            query_record.generated_sql = sql

            # Apply optimization hints if requested
            optimization_applied = []
            if apply_optimization and self.query_optimizer:
                optimized_sql = self.query_optimizer.analyze_and_optimize(sql, schema_dict)
                if optimized_sql != sql:
                    sql = optimized_sql
                    optimization_applied = [
                        hint["hint"] for hint in self.query_optimizer.get_hints()
                    ]
                    self._query_metrics["optimization_applied"] += len(optimization_applied)
                    logger.info(f"Applied {len(optimization_applied)} optimization hints")

            # Validate SQL (basic safety checks)
            if self.enable_sql_validation:
                self._validate_sql(sql)

            # Execute query against ClickHouse
            exec_start = time.time()
            rows, column_names, exec_time_ms = await self._execute_query(sql)
            execution_time_ms = int((time.time() - exec_start) * 1000)

            self._query_metrics["total_execution_time_ms"] += execution_time_ms

            # Format results
            formatted = self._format_results(rows, column_names)

            # Build result dictionary
            result = {
                "natural_language": natural_query,
                "generated_sql": sql,
                "optimization_applied": optimization_applied,
                "columns": column_names,
                "rows": rows,
                "row_count": len(rows),
                "execution_time_ms": execution_time_ms,
                "formatted_output": formatted,
                "query_id": query_record.id,
                "cache_hit": False,
                "metrics": {
                    "generation_time_ms": generation_time_ms,
                    "execution_time_ms": execution_time_ms,
                    "total_time_ms": int((time.time() - start_total_time) * 1000),
                    "cache_hit": False
                }
            }

            # Add explanation if requested
            if generate_explanation and self.query_explainer:
                explanation = self.query_explainer.explain(
                    sql,
                    natural_language_query=natural_query,
                    schema=schema_dict
                )
                result["explanation"] = {
                    "query_type": explanation.query_type,
                    "complexity": explanation.complexity,
                    "tables_accessed": explanation.tables_accessed,
                    "columns_accessed": explanation.columns_accessed,
                    "optimization_hints": explanation.optimization_hints,
                    "potential_issues": explanation.potential_issues,
                    "recommendations": explanation.recommendations,
                    "formatted_explanation": self.query_explainer.format_explanation(explanation)
                }

            # Cache the result (if enabled)
            if self.enable_cache and self.query_cache:
                cache_result = {
                    "natural_language": natural_query,
                    "generated_sql": sql,
                    "optimization_applied": optimization_applied,
                    "columns": column_names,
                    "rows": rows,
                    "row_count": len(rows),
                    "execution_time_ms": execution_time_ms,
                    "formatted_output": formatted
                }
                if generate_explanation and self.query_explainer:
                    cache_result["explanation"] = result["explanation"]

                self.query_cache.set(natural_query, sql, cache_result, schema_text)

            # Update query record
            query_record.mark_completed(
                result_data={"rows": rows, "columns": column_names},
                row_count=len(rows),
                execution_time_ms=execution_time_ms
            )

            return result

        except Exception as e:
            query_record.mark_failed(error_message=str(e))
            logger.error(f"Query failed: {e}")
            self._query_metrics["sql_errors"] += 1
            raise

    async def _generate_sql(self, natural_query: str, schema_text: str) -> str:
        """
        Generate SQL from natural language using LLM.

        Args:
            natural_query: User's natural language query
            schema_text: Formatted database schema

        Returns:
            SQL query string
        """
        system_prompt = f"""You are an expert ClickHouse SQL generator. Your job is to convert natural language questions into efficient ClickHouse SQL queries.

{schema_text}

Rules:
1. Always use SELECT statements. Never use INSERT, UPDATE, DELETE, or DROP unless explicitly asked (but user queries are read-only).
2. Use appropriate table aliases when joining tables.
3. Apply proper WHERE clauses to filter data efficiently.
4. Use ClickHouse-specific functions when beneficial (e.g., toDate(), formatDateTime()).
5. LIMIT results to avoid huge result sets (default LIMIT 1000 unless user asks for more).
6. Use descriptive column aliases by using AS keyword
7. If the query is ambiguous, make reasonable assumptions and state them.
8. Return ONLY the SQL, no explanations."""

        user_prompt = f"Convert this natural language query to ClickHouse SQL:\n\n{natural_query}"

        if self.llm_provider == "openai":
            return await self._call_openai(system_prompt, user_prompt)
        elif self.llm_provider == "anthropic":
            return await self._call_anthropic(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenAI API to generate SQL"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.llm_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.llm_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
                },
                timeout=30.0
            )

            response.raise_for_status()
            result = response.json()

            sql = result["choices"][0]["message"]["content"].strip()
            return self._extract_sql_from_response(sql)

    async def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        """Call Anthropic Claude API to generate SQL"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.llm_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.llm_model,
                    "max_tokens": 500,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_prompt}
                    ]
                },
                timeout=30.0
            )

            response.raise_for_status()
            result = response.json()

            sql = result["content"][0]["text"].strip()
            return self._extract_sql_from_response(sql)

    def _extract_sql_from_response(self, response_text: str) -> str:
        """Extract SQL from LLM response (remove markdown code blocks, explanations)"""
        # Remove markdown code blocks
        if "```sql" in response_text.lower():
            # Extract content within ```sql ... ```
            start = response_text.lower().find("```sql") + 6
            end = response_text.lower().find("```", start)
            if end != -1:
                return response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            if end != -1:
                return response_text[start:end].strip()

        # If no code blocks, assume whole response is SQL
        return response_text.strip()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the query agent.

        Returns:
            Dictionary with performance statistics
        """
        metrics = self._query_metrics.copy()

        # Calculate derived metrics
        total_queries = metrics["total_queries"]
        if total_queries > 0:
            metrics["avg_generation_time_ms"] = metrics["total_generation_time_ms"] / total_queries
            metrics["avg_execution_time_ms"] = metrics["total_execution_time_ms"] / total_queries
            metrics["success_rate"] = (total_queries - metrics["sql_errors"]) / total_queries
        else:
            metrics["avg_generation_time_ms"] = 0
            metrics["avg_execution_time_ms"] = 0
            metrics["success_rate"] = 1.0

        # Get cache stats if available
        if self.query_cache:
            cache_stats = self.query_cache.get_stats()
            metrics["cache"] = cache_stats

        # Add agent metrics
        metrics.update(self.metrics)

        return metrics

    def _validate_sql(self, sql: str) -> None:
        """
        Validate generated SQL for safety and correctness.

        Raises:
            ValueError: If SQL is invalid or dangerous
        """
        sql_lower = sql.lower().strip()

        # Check for dangerous operations
        dangerous_keywords = ['drop', 'truncate', 'delete', 'insert', 'update', 'alter', 'create', 'grant']
        for keyword in dangerous_keywords:
            if sql_lower.startswith(keyword):
                raise ValueError(f"Potentially dangerous SQL operation: {keyword}")

        # Check if it's a SELECT query
        if not sql_lower.startswith("select"):
            raise ValueError(f"Only SELECT queries are allowed, got: {sql_lower.split()[0]}")

        # Check for semicolon (should only be one statement)
        if sql.count(';') > 1:
            raise ValueError("Multiple statements not allowed")

    async def _execute_query(self, sql: str) -> (List, List[str], int):
        """
        Execute SQL query against ClickHouse.

        Args:
            sql: SQL query to execute

        Returns:
            Tuple of (rows, column_names, execution_time_ms)
        """
        if self.schema_loader is None or self.schema_loader.client is None:
            raise RuntimeError("ClickHouse client not initialized")

        logger.info(f"Executing query: {sql}")

        try:
            # Enforce limit if not present
            if "limit" not in sql.lower():
                sql = f"{sql.rstrip(';')} LIMIT {self.max_results}"

            start_time = datetime.utcnow()

            # Execute with column types to get column names
            result = self.schema_loader.client.execute(sql, with_column_types=True)
            rows = result[0]
            column_names = [col[0] for col in result[1]]

            end_time = datetime.utcnow()
            exec_time_ms = int((end_time - start_time).total_seconds() * 1000)

            logger.info(f"Query returned {len(rows)} rows in {exec_time_ms}ms")

            return rows, column_names, exec_time_ms

        except Exception as e:
            logger.error(f"ClickHouse query failed: {e}")
            raise RuntimeError(f"Query execution failed: {e}")

    def _format_results(self, rows: List, columns: List[str]) -> str:
        """
        Format query results as human-readable text.

        Args:
            rows: List of result rows (tuples)
            columns: List of column names

        Returns:
            Formatted string (tabulate-like)
        """
        if not rows:
            return "No results found."

        # Simple tabular format
        lines = []

        # Header
        header = " | ".join(str(col) for col in columns)
        lines.append(header)
        lines.append("-" * len(header))

        # Rows (limit to 100 for display)
        display_rows = rows[:100]
        for row in display_rows:
            row_str = " | ".join(str(val) if val is not None else "NULL" for val in row)
            lines.append(row_str)

        if len(rows) > 100:
            lines.append(f"... and {len(rows) - 100} more rows")

        return "\n".join(lines)


def create_query_agent() -> QueryAgent:
    """Factory function to create QueryAgent with default configuration"""
    config = AgentConfig(
        name="query_agent",
        description="AI agent that translates natural language to SQL and executes queries against ClickHouse",
        version="1.0.0",
        max_concurrent_tasks=10,
        timeout_seconds=60,
        retry_attempts=2,
        retry_delay_seconds=1.0,
        enabled=True,
        config={
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "max_results": 1000,
            "enable_sql_validation": True
        }
    )

    return QueryAgent(config)
