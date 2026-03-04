"""
Platform Metrics - Prometheus instrumentation for AI Data Labs

This module defines all core platform metrics for monitoring API, agents, and database performance.
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client import start_http_server
import time
import logging

logger = logging.getLogger(__name__)

# Platform metadata
BUILD_INFO = Info('ai_datalabs_build', 'AI Data Labs build information')

# API Metrics
API_REQUESTS = Counter(
    'ai_datalabs_api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status']
)

API_LATENCY = Histogram(
    'ai_datalabs_api_latency_seconds',
    'API request latency in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

API_ACTIVE_REQUESTS = Gauge(
    'ai_datalabs_api_active_requests',
    'Number of currently active API requests',
    ['endpoint']
)

# Agent Metrics
AGENT_EXECUTIONS = Counter(
    'ai_datalabs_agent_executions_total',
    'Total number of agent executions',
    ['agent_name', 'task_type', 'status']
)

AGENT_LATENCY = Histogram(
    'ai_datalabs_agent_latency_seconds',
    'Agent execution latency in seconds',
    ['agent_name', 'task_type'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
)

AGENT_ACTIVE_TASKS = Gauge(
    'ai_datalabs_agent_active_tasks',
    'Number of active agent tasks',
    ['agent_name']
)

AGENT_QUEUE_SIZE = Gauge(
    'ai_datalabs_agent_queue_size',
    'Number of tasks in agent queue',
    ['agent_name']
)

LLM_REQUESTS = Counter(
    'ai_datalabs_llm_requests_total',
    'Total number of LLM API requests',
    ['provider', 'model', 'status']
)

LLM_TOKENS = Counter(
    'ai_datalabs_llm_tokens_total',
    'Total number of LLM tokens processed',
    ['provider', 'model', 'type']  # type: prompt, completion
)

LLM_LATENCY = Histogram(
    'ai_datalabs_llm_latency_seconds',
    'LLM API request latency in seconds',
    ['provider', 'model'],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0)
)

# Database Metrics
DB_QUERIES = Counter(
    'ai_datalabs_db_queries_total',
    'Total number of database queries',
    ['db_type', 'operation', 'status']
)

DB_QUERY_LATENCY = Histogram(
    'ai_datalabs_db_query_latency_seconds',
    'Database query latency in seconds',
    ['db_type', 'operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

DB_CONNECTIONS = Gauge(
    'ai_datalabs_db_connections_active',
    'Number of active database connections',
    ['db_type']
)

DB_CONNECTION_POOL = Gauge(
    'ai_datalabs_db_connection_pool_size',
    'Database connection pool size',
    ['db_type']
)

# Query/Chat Metrics
QUERY_EXECUTIONS = Counter(
    'ai_datalabs_query_executions_total',
    'Total number of query executions',
    ['status', 'query_type']
)

QUERY_LATENCY = Histogram(
    'ai_datalabs_query_latency_seconds',
    'Query execution latency in seconds',
    ['query_type'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)

CHAT_REQUESTS = Counter(
    'ai_datalabs_chat_requests_total',
    'Total number of chat requests',
    ['status']
)

CHAT_LATENCY = Histogram(
    'ai_datalabs_chat_latency_seconds',
    'Chat request latency in seconds',
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0)
)

# Error Metrics
ERRORS_TOTAL = Counter(
    'ai_datalabs_errors_total',
    'Total number of errors',
    ['component', 'error_type', 'severity']
)

# System Metrics
SYSTEM_MEMORY_USAGE = Gauge(
    'ai_datalabs_system_memory_usage_bytes',
    'System memory usage in bytes'
)

SYSTEM_CPU_USAGE = Gauge(
    'ai_datalabs_system_cpu_usage_percent',
    'System CPU usage percentage'
)

# Task Queue Metrics
TASK_QUEUE_SIZE = Gauge(
    'ai_datalabs_task_queue_size',
    'Number of tasks in queue',
    ['queue_name']
)

TASK_PROCESSED = Counter(
    'ai_datalabs_task_processed_total',
    'Total number of tasks processed',
    ['queue_name', 'status']
)

# Data Source Metrics
DATA_SOURCE_STATUS = Gauge(
    'ai_datalabs_data_source_status',
    'Data source connection status',
    ['source_id', 'source_type']
)

DATA_SOURCE_QUERIES = Counter(
    'ai_datalabs_data_source_queries_total',
    'Total queries per data source',
    ['source_id', 'source_type', 'status']
)


class MetricsContext:
    """Context manager for measuring API latency."""

    def __init__(self, method: str, endpoint: str):
        self.method = method
        self.endpoint = endpoint
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        API_ACTIVE_REQUESTS.labels(endpoint=self.endpoint).inc()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        API_LATENCY.labels(
            method=self.method,
            endpoint=self.endpoint
        ).observe(duration)

        status = 'success' if exc_type is None else 'error'
        API_REQUESTS.labels(
            method=self.method,
            endpoint=self.endpoint,
            status=status
        ).inc()

        API_ACTIVE_REQUESTS.labels(endpoint=self.endpoint).dec()

        if exc_type is not None:
            ERRORS_TOTAL.labels(
                component='api',
                error_type=exc_type.__name__,
                severity='critical' if isinstance(exc_val, Exception) else 'warning'
            ).inc()


class AgentMetricsContext:
    """Context manager for measuring agent execution latency."""

    def __init__(self, agent_name: str, task_type: str):
        self.agent_name = agent_name
        self.task_type = task_type
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        AGENT_ACTIVE_TASKS.labels(agent_name=self.agent_name).inc()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        AGENT_LATENCY.labels(
            agent_name=self.agent_name,
            task_type=self.task_type
        ).observe(duration)

        status = 'success' if exc_type is None else 'error'
        AGENT_EXECUTIONS.labels(
            agent_name=self.agent_name,
            task_type=self.task_type,
            status=status
        ).inc()

        AGENT_ACTIVE_TASKS.labels(agent_name=self.agent_name).dec()

        if exc_type is not None:
            ERRORS_TOTAL.labels(
                component='agent',
                error_type=exc_type.__name__,
                severity='critical' if isinstance(exc_val, Exception) else 'warning'
            ).inc()


class DatabaseMetricsContext:
    """Context manager for measuring database query latency."""

    def __init__(self, db_type: str, operation: str):
        self.db_type = db_type
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        DB_QUERY_LATENCY.labels(
            db_type=self.db_type,
            operation=self.operation
        ).observe(duration)

        status = 'success' if exc_type is None else 'error'
        DB_QUERIES.labels(
            db_type=self.db_type,
            operation=self.operation,
            status=status
        ).inc()

        if exc_type is not None:
            ERRORS_TOTAL.labels(
                component='database',
                error_type=exc_type.__name__,
                severity='warning'
            ).inc()


def record_llm_request(provider: str, model: str, status: str,
                       prompt_tokens: int = 0, completion_tokens: int = 0,
                       latency: float = 0):
    """Record LLM API request metrics."""
    LLM_REQUESTS.labels(
        provider=provider,
        model=model,
        status=status
    ).inc()

    if prompt_tokens > 0:
        LLM_TOKENS.labels(
            provider=provider,
            model=model,
            type='prompt'
        ).inc(prompt_tokens)

    if completion_tokens > 0:
        LLM_TOKENS.labels(
            provider=provider,
            model=model,
            type='completion'
        ).inc(completion_tokens)

    if latency > 0:
        LLM_LATENCY.labels(
            provider=provider,
            model=model
        ).observe(latency)


def record_query_execution(status: str, query_type: str, latency: float):
    """Record query execution metrics."""
    QUERY_EXECUTIONS.labels(status=status, query_type=query_type).inc()
    QUERY_LATENCY.labels(query_type=query_type).observe(latency)


def record_chat_request(status: str, latency: float):
    """Record chat request metrics."""
    CHAT_REQUESTS.labels(status=status).inc()
    CHAT_LATENCY.observe(latency)


def update_db_connections(db_type: str, active: int, pool_size: int):
    """Update database connection metrics."""
    DB_CONNECTIONS.labels(db_type=db_type).set(active)
    DB_CONNECTION_POOL.labels(db_type=db_type).set(pool_size)


def update_agent_queue(agent_name: str, queue_size: int):
    """Update agent queue size metric."""
    AGENT_QUEUE_SIZE.labels(agent_name=agent_name).set(queue_size)


def update_task_queue(queue_name: str, size: int):
    """Update task queue size metric."""
    TASK_QUEUE_SIZE.labels(queue_name=queue_name).set(size)


def record_task_processed(queue_name: str, status: str):
    """Record task processed metric."""
    TASK_PROCESSED.labels(queue_name=queue_name, status=status).inc()


def update_data_source_status(source_id: str, source_type: str, status: int):
    """
    Update data source status metric.
    status: 1 = connected, 0 = disconnected
    """
    DATA_SOURCE_STATUS.labels(
        source_id=source_id,
        source_type=source_type
    ).set(status)


def record_data_source_query(source_id: str, source_type: str, status: str):
    """Record data source query metric."""
    DATA_SOURCE_QUERIES.labels(
        source_id=source_id,
        source_type=source_type,
        status=status
    ).inc()


def initialize_metrics(build_version: str = "0.1.0", git_commit: str = "unknown"):
    """Initialize platform metrics with build information."""
    BUILD_INFO.info({
        'version': build_version,
        'git_commit': git_commit,
        'python_version': '3.11'
    })
    logger.info("Metrics initialized with build version %s", build_version)


def start_metrics_server(port: int = 9090):
    """Start Prometheus metrics HTTP server."""
    start_http_server(port)
    logger.info("Prometheus metrics server started on port %d", port)
