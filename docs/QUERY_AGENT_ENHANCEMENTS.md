# Query Agent Enhancements

Comprehensive enhancements to the Query Agent with caching, optimization, explanation, and multi-dialect support.

## Features

### 1. Query Result Caching

**What it does:** Caches query results to improve performance and reduce LLM API calls.

**How it works:**
- Creates a hash of the natural language query + schema state
- Stores the generated SQL and results in an LRU cache
- Cache entries expire after configurable TTL (default: 1 hour)
- Automatically invalidates entries when schema changes

**Configuration:**
```python
config = AgentConfig(
    name="query_agent",
    config={
        "enable_cache": True,              # Enable/disable caching (default: True)
        "cache_ttl_seconds": 3600,        # Cache time-to-live in seconds (default: 1 hour)
        "cache_max_entries": 1000,        # Maximum cache entries (default: 1000)
        "cache_max_memory_mb": 100        # Max memory usage in MB (default: 100)
    }
)
```

**Cache Statistics:**
```python
metrics = agent.get_performance_metrics()
cache_stats = metrics.get("cache", {})
# Returns: entries, memory_bytes, hits, misses, hit_rate, etc.
```

**Manual Cache Control:**
```python
# Invalidate specific query
agent.query_cache.invalidate("show me users", "schema hash")

# Clear all cache
agent.query_cache.clear()

# Get cache statistics
stats = agent.query_cache.get_stats()
```

### 2. Query Optimization Hints

**What it does:** Analyzes generated SQL and adds ClickHouse-specific optimization hints.

**Optimizations Applied:**

- **SETTINGS clause:** Adds performance-oriented settings for JOINs, aggregations, ORDER BY
- **Anti-pattern detection:** Identifies SELECT *, NOT IN with NULLs, missing LIMIT, etc.
- **Index suggestions:** Recommends using primary key columns in WHERE clauses
- **Partition pruning:** Checks if partition keys are used in filters
- **JOIN optimization:** Suggests USING clause for equijoins
- **Aggregation optimization:** Warns about COUNT(DISTINCT) memory issues
- **FINAL modifier:** Adds FINAL for ReplacingMergeTree tables
- **Memory management:** Detects large LIMIT values and ORDER BY without LIMIT

**Configuration:**
```python
config = AgentConfig(
    name="query_agent",
    config={
        "enable_optimization": True  # Enable/disable optimization (default: True)
    }
)
```

**View Optimization Hints:**
```python
result = await agent.process({"query": "Show me users"})
optimizations = result.get("optimization_applied", [])
# List of applied optimization hints
```

**Detailed Query Analysis:**
```python
if agent.query_optimizer:
    explanation = agent.query_optimizer.explain_query("SELECT * FROM users")
    # Returns: query_type, complexity, estimated_rows, recommendations
```

### 3. Query Explanation Features

**What it does:** Generates human-readable explanations of SQL queries with natural language descriptions.

**Explanation Includes:**

- **Natural language interpretation:** What the query does in plain English
- **Query type classification:** join_query, aggregation, simple_select, etc.
- **Complexity assessment:** low, medium, high
- **Execution plan:** Step-by-step breakdown (SCAN, JOIN, FILTER, AGGREGATE, SORT, LIMIT)
- **Tables and columns accessed:** Full list of referenced database objects
- **Optimization hints:** Suggestions for improving performance
- **Potential issues:** Warnings about anti-patterns and risks
- **Recommendations:** Actionable advice

**Configuration:**
```python
config = AgentConfig(
    name="query_agent",
    config={
        "enable_explanation": True  # Enable/disable explanation (default: True)
    }
)
```

**Get Explanation for Query:**
```python
result = await agent.process({
    "query": "How many users signed up each month?",
    "generate_explanation": True  # Override config for this query if needed
})

explanation = result.get("explanation", {})
print(explanation.get("formatted_explanation"))
# Beautifully formatted multi-line explanation
```

**Explanation Format:**
```
==================================================
QUERY EXPLANATION
==================================================

📝 Natural Language Query:
   How many users signed up each month?

💻 Generated SQL:
   SELECT
      toYYYYMM(created_at) AS month,
      COUNT(*) AS user_count
   FROM users
   GROUP BY month
   ORDER BY month

🔍 Query Type: AGGREGATION
📊 Complexity: MEDIUM

📁 Tables Accessed (1):
   • users

⚡ Execution Plan:
   1. [✓] SCAN TABLE users
         Read all data from table 'users'
   2. [✓] FILTER (WHERE)
         Filter rows based on conditions
   3. [✓] AGGREGATE (GROUP BY)
         Group rows by month and compute aggregates
   4. [✓] SORT (ORDER BY)
         Sort results by month

💡 Optimization Hints (2):
   1. Consider adding LIMIT to prevent large result sets
   2. Ensure join columns are indexed

⚠️ Potential Issues (1):
   1. Large aggregations can be memory-intensive

✨ Recommendations (3):
   1. Consider using max_bytes_before_external_group_by for large datasets
   2. Add index on created_at column for faster grouping
   3. Use partition pruning if table is partitioned by month

==================================================
```

### 4. Multi-Dialect SQL Support

**What it does:** Supports multiple SQL dialects for query explanation and optimization.

**Supported Dialects:**

- `clickhouse` (default) - ClickHouse-specific optimizations
- `postgresql` - PostgreSQL syntax and features
- `mysql` - MySQL/MariaDB syntax
- `sqlite` - SQLite-specific considerations
- `sqlserver` - Microsoft SQL Server
- `oracle` - Oracle Database

**Configuration:**
```python
config = AgentConfig(
    name="query_agent",
    config={
        "sql_dialect": "postgresql"  # or "mysql", "sqlite", etc.
    }
)
```

**Dialect-Specific Features:**

- **ClickHouse:** ReplacingMergeTree FINAL modifier, max_bytes_before_external_group_by
- **PostgreSQL:** Index suggestions, EXPLAIN ANALYZE integration
- **MySQL:** Engine-specific recommendations (InnoDB vs MyISAM)
- **SQLite:** Query planner optimization hints

**Switch Dialect Per Query:**
```python
# Query agent uses config's dialect by default
# To switch dialect temporarily:
result = await agent.process({
    "query": "Show me top 10 users",
    # No per-query dialect switch yet, but you can create separate agent instances
})
```

### 5. Performance Metrics Tracking

**What it does:** Tracks comprehensive performance metrics for all query operations.

**Metrics Tracked:**

- **Query Count:** Total queries processed
- **Generation Time:** Time spent generating SQL from LLM
- **Execution Time:** Time spent executing SQL in ClickHouse
- **Cache Performance:** Hit rate, miss rate, memory usage
- **Success Rate:** Percentage of successful queries
- **Optimizations Applied:** Count of optimization hints used
- **Errors:** Number of SQL errors and exceptions

**Get Performance Metrics:**
```python
metrics = agent.get_performance_metrics()

print(f"Total queries: {metrics['total_queries']}")
print(f"Avg generation time: {metrics['avg_generation_time_ms']:.2f}ms")
print(f"Avg execution time: {metrics['avg_execution_time_ms']:.2f}ms")
print(f"Cache hit rate: {metrics['cache'].get('hit_rate', 0):.2%}")
print(f"Success rate: {metrics['success_rate']:.2%}")
```

**Agent Health Check:**
```python
health = await agent.health_check()
# Includes metrics in health status
print(health["metrics"])
```

### 6. Improved NL to SQL Conversion

**What it does:** Enhanced prompt engineering for better SQL generation accuracy.

**Improvements:**

- **Better schema context:** Includes table engines, column descriptions, comments
- **Structured prompting:** Clear rules and examples
- **Safety first:** Stronger validation against dangerous operations
- **Dialect-aware:** Generates ClickHouse-specific functions (toDate, formatDateTime, etc.)
- **Explainability:** Can provide reasoning for generated SQL

**Prompt Engineering:**

The system prompt now includes:
- Complete database schema with table engines
- Column types, primary keys, descriptions
- ClickHouse-specific best practices
- Safety rules (no DML, only SELECT)
- Format requirements

**Model Configuration:**
```python
config = AgentConfig(
    name="query_agent",
    config={
        "llm_provider": "openai",      # or "anthropic"
        "llm_model": "gpt-4",          # or "claude-3-opus", etc.
        "llm_api_key": "your-api-key"
    }
)
```

## Usage Examples

### Basic Query with All Features Enabled

```python
from app.agents.query_agent import QueryAgent, AgentConfig

config = AgentConfig(
    name="query_agent",
    description="Enhanced AI Query Agent",
    enabled=True,
    config={
        "llm_provider": "openai",
        "llm_model": "gpt-4",
        "clickhouse_url": "clickhouse://default:@localhost:9000/default",
        "enable_cache": True,
        "cache_ttl_seconds": 3600,
        "enable_optimization": True,
        "enable_explanation": True,
        "sql_dialect": "clickhouse",
        "max_results": 1000,
        "enable_sql_validation": True
    }
)

agent = QueryAgent(config)
await agent.initialize()

result = await agent.process({
    "query": "How many active users do we have each day?",
    "user_id": 123,
    "generate_explanation": True
})

print("Generated SQL:", result["generated_sql"])
print("\nOptimizations applied:", result.get("optimization_applied", []))
print("\nExplanation:")
print(result.get("explanation", {}).get("formatted_explanation"))
print("\nResults:", result["formatted_output"])
print(f"\nExecution time: {result['execution_time_ms']}ms")
```

### Using Cache for Repeated Queries

```python
# First query - cache miss (generates SQL, executes)
result1 = await agent.process({"query": "Total users"})
print("Cache hit:", result1.get("cache_hit", False))  # False

# Same query again - cache hit (returns cached result instantly)
result2 = await agent.process({"query": "Total users"})
print("Cache hit:", result2.get("cache_hit", False))  # True

# Different query - cache miss
result3 = await agent.process({"query": "Total orders"})
print("Cache hit:", result3.get("cache_hit", False))  # False
```

### Monitoring Performance

```python
# Get current metrics
metrics = agent.get_performance_metrics()

print(f"Queries processed: {metrics['total_queries']}")
print(f"Cache hit rate: {metrics['cache'].get('hit_rate', 0):.2%}")
print(f"Avg generation time: {metrics['avg_generation_time_ms']:.1f}ms")
print(f"Avg execution time: {metrics['avg_execution_time_ms']:.1f}ms")
print(f"Success rate: {metrics['success_rate']:.2%}")

# Log metrics periodically
import time
while True:
    metrics = agent.get_performance_metrics()
    logger.info(f"Query metrics: {json.dumps(metrics, indent=2)}")
    time.sleep(60)  # Log every minute
```

### Disabling Features Per Query

```python
# Query with caching disabled (still generates SQL)
result = await agent.process({
    "query": "Show me recent orders",
    "generate_explanation": False,  # Skip explanation generation
    "apply_optimization": False    # Skip optimization
})
```

### Creating Multiple Agents with Different Configs

```python
# Agent for analytical queries (heavy optimization, long TTL)
analytical_config = AgentConfig(
    name="analytical_query_agent",
    config={
        "enable_cache": True,
        "cache_ttl_seconds": 86400,  # 24 hours
        "enable_optimization": True,
        "enable_explanation": True
    }
)

# Agent for ad-hoc queries (lighter caching, fast response)
ad_hoc_config = AgentConfig(
    name="ad_hoc_query_agent",
    config={
        "enable_cache": True,
        "cache_ttl_seconds": 300,  # 5 minutes
        "enable_optimization": False,  # No optimization overhead
        "enable_explanation": False    # No explanation overhead
    }
)

analytical_agent = QueryAgent(analytical_config)
ad_hoc_agent = QueryAgent(ad_hoc_config)
```

## Testing

Run the comprehensive test suite:

```bash
# Run all enhancement tests
pytest tests/agents/test_query_agent_enhancements.py -v

# Run specific test class
pytest tests/agents/test_query_agent_enhancements.py::TestQueryCache -v
pytest tests/agents/test_query_agent_enhancements.py::TestQueryOptimizer -v
pytest tests/agents/test_query_agent_enhancements.py::TestQueryExplainer -v
pytest tests/agents/test_query_agent_enhancements.py::TestQueryAgentEnhanced -v
```

## Performance Considerations

### Caching
- **Memory:** Cache size controlled by `max_entries` and `max_memory_mb`
- **TTL:** Default 1 hour, adjust based on query volatility
- **Hit rate:** Monitor via `get_performance_metrics()`
- **Invalidation:** Automatic when schema changes, manual via API

### Optimization
- **Overhead:** ~1-5ms per query for analysis
- **Batching:** Optimizations are computed once per unique query
- **Caching:** Optimized SQL is cached, so overhead amortized

### Explanation
- **Overhead:** ~10-50ms per query for full explanation
- **Lazy:** Only generated when `generate_explanation=True`
- **Formatting:** Can be expensive for complex queries; render on demand

### Multi-Dialect
- **Dialect affects only explanation:** SQL generation remains ClickHouse-specific
- **Switch cost:** Creating new agent instance per dialect has startup cost
- **Recommendation:** Use one agent per dialect in production

## Best Practices

1. **Enable caching** for production workloads (reduces LLM costs and latency)
2. **Set appropriate cache TTL:** Shorter for frequently changing schemas, longer for stable schemas
3. **Monitor cache hit rate:** Should be >60% for typical workloads
4. **Use optimization** for complex analytical queries
5. **Enable explanation** for new users or debugging
6. **Track performance metrics** to identify bottlenecks
7. **Separate agents** for different use cases (ad-hoc vs. dashboard queries)
8. **Validate SQL** always (enabled by default)
9. **Set max_results** to prevent runaway queries
10. **Monitor memory** if caching large result sets

## Migration Guide

If upgrading from the basic Query Agent:

1. **Configuration Update:**
```python
# Old config
config = AgentConfig(
    name="query_agent",
    config={"llm_provider": "openai", "llm_model": "gpt-4"}
)

# New config (backward compatible - old configs still work)
config = AgentConfig(
    name="query_agent",
    config={
        "llm_provider": "openai",
        "llm_model": "gpt-4",
        # New features use defaults if not specified
        "enable_cache": True,
        "cache_ttl_seconds": 3600,
        "enable_optimization": True,
        "enable_explanation": True,
        "sql_dialect": "clickhouse"
    }
)
```

2. **No code changes required** for existing usage - features are opt-in via config

3. **Monitor performance** after upgrade:
```python
metrics = agent.get_performance_metrics()
# Compare metrics before and after
```

4. **Test cache effectiveness:**
```python
# Run typical workload
for query in common_queries:
    await agent.process({"query": query})

stats = agent.query_cache.get_stats()
print(f"Cache hit rate: {stats['hit_rate']:.2%}")
# Adjust cache settings if hit rate is low
```

## Troubleshooting

### Cache Miss Rate Too High

**Symptom:** Cache hit rate < 40%

**Causes:**
- Queries are too unique (high cardinality)
- Schema changes frequently
- Cache TTL too short
- Cache size too small

**Solutions:**
- Increase `cache_ttl_seconds`
- Increase `cache_max_entries` or `cache_max_memory_mb`
- Normalize queries before caching (lowercase, remove extra whitespace)
- Check if schema is changing frequently

### Optimization Overhead High

**Symptom:** Query latency increased by >10ms

**Causes:**
- Complex schema with many tables
- Large number of optimization rules

**Solutions:**
- Set `enable_optimization: False` for simple workloads
- Increase `enable_optimization` to `False` for ad-hoc queries
- Profile to identify slow optimizations

### Explanation Too Slow

**Symptom:** Explanation generation takes >100ms

**Causes:**
- Complex queries with many JOINs and subqueries
- Explanation formatting overhead

**Solutions:**
- Only enable explanation for debugging: `"generate_explanation": True` per query
- Disable for production: `"enable_explanation": False`
- Cache explanations separately if same queries repeat

### Memory Usage High

**Symptom:** Agent using too much RAM

**Causes:**
- Cache storing large result sets
- Too many cache entries

**Solutions:**
- Reduce `cache_max_memory_mb`
- Reduce `max_results` to limit result set size
- Implement custom cache eviction policy
- Monitor `query_cache.get_stats()["memory_mb"]`

## API Reference

### QueryAgent

**Configuration Options (`config` dict):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `llm_provider` | str | "openai" | LLM provider: "openai" or "anthropic" |
| `llm_model` | str | "gpt-4" | Model name (e.g., "gpt-4", "claude-3-opus") |
| `llm_api_key` | str | env var | API key for LLM provider |
| `clickhouse_url` | str | env var | ClickHouse connection URL |
| `max_results` | int | 1000 | Maximum rows to return |
| `enable_sql_validation` | bool | True | Validate generated SQL for safety |
| `enable_cache` | bool | True | Enable query result caching |
| `cache_ttl_seconds` | int | 3600 | Cache TTL in seconds |
| `cache_max_entries` | int | 1000 | Maximum cache entries |
| `cache_max_memory_mb` | int | 100 | Maximum cache memory in MB |
| `enable_optimization` | bool | True | Enable query optimization hints |
| `enable_explanation` | bool | True | Enable query explanation generation |
| `sql_dialect` | str | "clickhouse" | SQL dialect for explanation |

**Process Input:**

```python
await agent.process({
    "query": "natural language query",
    "user_id": 123,                    # optional
    "generate_explanation": True,      # optional, overrides config
    "apply_optimization": True         # optional, overrides config
})
```

**Returns:**

```python
{
    "natural_language": "...",
    "generated_sql": "...",
    "optimization_applied": [...],      # List of applied optimization hints
    "columns": [...],
    "rows": [...],
    "row_count": 123,
    "execution_time_ms": 456,
    "formatted_output": "...",
    "query_id": 123,
    "cache_hit": False,
    "metrics": {
        "generation_time_ms": 234,
        "execution_time_ms": 456,
        "total_time_ms": 690,
        "cache_hit": False
    },
    "explanation": {                      # only if generate_explanation=True
        "query_type": "aggregation",
        "complexity": "medium",
        "tables_accessed": ["users", "orders"],
        "columns_accessed": ["id", "name"],
        "optimization_hints": [...],
        "potential_issues": [...],
        "recommendations": [...],
        "formatted_explanation": "multi-line string"
    }
}
```

**Methods:**

- `get_performance_metrics()`: Get comprehensive performance statistics
- `query_cache.get_stats()`: Get cache statistics
- `query_cache.invalidate(query, schema_hash)`: Invalidate specific cache entry
- `query_cache.clear()`: Clear entire cache
- `query_optimizer.explain_query(sql)`: Get detailed analysis of SQL query
- `query_explainer.format_explanation(explanation)`: Format explanation as text

## Future Enhancements

Planned improvements for future iterations:

- **Adaptive caching:** Learn query patterns and pre-warm cache
- **Query rewriting:** Automatic SQL optimization (not just hints)
- **Explainability for LLM:** Show prompt sent to LLM for debugging
- **Multi-LLM fallback:** Try alternative LLM if primary fails
- **Query Suggestions:** Proactive query improvements based on user intent
- **Schema evolution detection:** Automatic cache invalidation on schema changes
- **Cost estimation:** Provide estimated ClickHouse query cost in rows/bytes
- **Security scanning:** Detect potential SQL injection patterns
- **Query history:** Store and analyze query patterns over time
- **Personalization:** Learn user preferences for query formats

## Support

For issues, questions, or feature requests:

- GitHub Issues: https://github.com/duet-company/backend/issues
- Documentation: https://docs.aidatalabs.ai/query-agent
- Support: support@aidatalabs.ai

---

**Version:** 2.0.0
**Last Updated:** March 5, 2026
**Compatible with:** Backend API v1.0+
