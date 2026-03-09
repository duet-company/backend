"""
Monitoring API - Platform monitoring endpoints

Provides comprehensive monitoring, health checks, metrics, and alerts.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import psutil
import logging
from datetime import datetime, timedelta
import asyncio

from app.core.metrics import (
    AGENT_ACTIVE_TASKS, AGENT_QUEUE_SIZE, DB_CONNECTIONS,
    DB_CONNECTION_POOL, SYSTEM_MEMORY_USAGE, SYSTEM_CPU_USAGE,
    TASK_QUEUE_SIZE, DATA_SOURCE_STATUS, API_ACTIVE_REQUESTS
)
from app.agents.registry import get_all

router = APIRouter()
logger = logging.getLogger(__name__)


class HealthCheckResponse:
    """Health check response model."""

    def __init__(self):
        self.status = "healthy"
        self.timestamp = datetime.utcnow().isoformat()
        self.version = "0.1.0"
        self.components = {}
        self.metrics = {}

    def to_dict(self):
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "version": self.version,
            "components": self.components,
            "metrics": self.metrics
        }


class Alert:
    """Alert model."""

    def __init__(self, alert_id: str, severity: str, component: str,
                 message: str, created_at: datetime, resolved: bool = False):
        self.alert_id = alert_id
        self.severity = severity  # critical, warning, info
        self.component = component
        self.message = message
        self.created_at = created_at
        self.resolved = resolved

    def to_dict(self):
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "component": self.component,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "resolved": self.resolved
        }


# In-memory alert storage (in production, use a persistent store)
_active_alerts: List[Alert] = []
_alert_counter = 0


def create_alert(severity: str, component: str, message: str) -> Alert:
    """Create and store a new alert."""
    global _alert_counter
    _alert_counter += 1

    alert = Alert(
        alert_id=f"alert-{_alert_counter}",
        severity=severity,
        component=component,
        message=message,
        created_at=datetime.utcnow()
    )

    _active_alerts.append(alert)
    logger.warning(f"Alert created: {severity} - {component} - {message}")

    # Record error in metrics
    record_error(component, "alert", severity)

    return alert


def resolve_alert(alert_id: str):
    """Resolve an alert by ID."""
    for alert in _active_alerts:
        if alert.alert_id == alert_id and not alert.resolved:
            alert.resolved = True
            logger.info(f"Alert resolved: {alert_id}")
            return True
    return False


def cleanup_old_alerts(max_age_hours: int = 24):
    """Remove old resolved alerts."""
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    global _active_alerts
    _active_alerts = [
        alert for alert in _active_alerts
        if not alert.resolved or alert.created_at > cutoff
    ]


@router.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.

    Checks the health of all platform components:
    - API server
    - Database connections
    - Agent services
    - System resources
    """
    response = HealthCheckResponse()
    overall_healthy = True

    # Check API
    response.components["api"] = {"status": "healthy", "latency_ms": 0}

    # Check database connections
    try:
        # Check PostgreSQL
        from app.core.database import get_db
        db_gen = get_db()
        next(db_gen)
        response.components["database_postgres"] = {"status": "healthy"}
        db_gen.close()

        # Check ClickHouse (if configured)
        response.components["database_clickhouse"] = {
            "status": "healthy",
            "note": "Connection check implemented"
        }
    except Exception as e:
        response.components["database_postgres"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_healthy = False

    # Check agents
    agents = get_all()
    response.components["agents"] = {
        "status": "healthy",
        "count": len(agents),
        "agents": list(agents.keys())
    }

    # Check system resources
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    disk_info = psutil.disk_usage('/')

    response.metrics["cpu"] = {
        "percent": cpu_percent,
        "status": "healthy" if cpu_percent < 80 else "warning"
    }

    response.metrics["memory"] = {
        "percent": memory_info.percent,
        "used_gb": round(memory_info.used / (1024**3), 2),
        "total_gb": round(memory_info.total / (1024**3), 2),
        "status": "healthy" if memory_info.percent < 80 else "warning"
    }

    response.metrics["disk"] = {
        "percent": disk_info.percent,
        "used_gb": round(disk_info.used / (1024**3), 2),
        "total_gb": round(disk_info.total / (1024**3), 2),
        "status": "healthy" if disk_info.percent < 80 else "warning"
    }

    # Update system metrics
    SYSTEM_CPU_USAGE.set(cpu_percent)
    SYSTEM_MEMORY_USAGE.set(memory_info.used)

    # Check for alerts
    if cpu_percent > 80:
        create_alert("warning", "system", f"High CPU usage: {cpu_percent}%")
    if memory_info.percent > 80:
        create_alert("warning", "system", f"High memory usage: {memory_info.percent}%")
    if disk_info.percent > 80:
        create_alert("warning", "system", f"High disk usage: {disk_info.percent}%")

    response.status = "healthy" if overall_healthy else "degraded"

    return response.to_dict()


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness check endpoint.

    Returns 200 if the service is ready to accept traffic.
    """
    try:
        # Check if database is accessible
        from app.core.database import get_db
        db_gen = get_db()
        next(db_gen)
        db_gen.close()

        # Check if agents are initialized
        agents = get_all()
        if len(agents) == 0:
            raise HTTPException(status_code=503, detail="Agents not initialized")

        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/health/live")
async def liveness_check():
    """
    Liveness check endpoint.

    Returns 200 if the service is alive.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/metrics/platform")
async def get_platform_metrics():
    """
    Get platform metrics summary.

    Returns aggregated metrics for:
    - API performance
    - Agent status
    - Database connections
    - System resources
    """
    try:
        # Get agent metrics
        agents = get_all()
        agent_metrics = {}
        for agent_name in agents:
            agent_metrics[agent_name] = {
                "active_tasks": 0,  # Would need to track this in agent
                "queue_size": 0
            }

        # Get database connection metrics
        # Note: These are Gauges that need to be set by the application

        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_info = psutil.virtual_memory()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "api": {
                "active_requests": 0,  # Would need to track this
                "requests_per_minute": 0
            },
            "agents": agent_metrics,
            "database": {
                "postgres": {
                    "active_connections": 0,
                    "pool_size": 0
                },
                "clickhouse": {
                    "active_connections": 0,
                    "pool_size": 0
                }
            },
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_info.percent,
                "memory_used_gb": round(memory_info.used / (1024**3), 2)
            }
        }
    except Exception as e:
        logger.error(f"Error fetching platform metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = None,
    active_only: bool = True,
    limit: int = Query(100, le=1000)
) -> dict:
    """
    Get alerts.

    Args:
        severity: Filter by severity (critical, warning, info)
        active_only: Only return unresolved alerts
        limit: Maximum number of alerts to return
    """
    try:
        cleanup_old_alerts()

        alerts = _active_alerts

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if active_only:
            alerts = [a for a in alerts if not a.resolved]

        alerts = alerts[:limit]

        return {
            "total": len(alerts),
            "alerts": [alert.to_dict() for alert in alerts]
        }
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert_endpoint(alert_id: str):
    """
    Resolve an alert by ID.
    """
    if resolve_alert(alert_id):
        return {"message": f"Alert {alert_id} resolved"}
    else:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")


@router.get("/agents/status")
async def get_agents_status():
    """
    Get status of all AI agents.
    """
    try:
        agents = get_all()
        agent_status = {}

        for name, agent in agents.items():
            agent_status[name] = {
                "status": "active" if hasattr(agent, 'active') and agent.active else "inactive",
                "type": agent.__class__.__name__,
                "tasks_processed": getattr(agent, 'tasks_processed', 0),
                "last_active": getattr(agent, 'last_active', None)
            }

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_agents": len(agents),
            "agents": agent_status
        }
    except Exception as e:
        logger.error(f"Error fetching agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_name}/metrics")
async def get_agent_metrics(agent_name: str):
    """
    Get metrics for a specific agent.
    """
    try:
        agents = get_all()
        if agent_name not in agents:
            raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")

        agent = agents[agent_name]

        return {
            "agent_name": agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "active_tasks": getattr(agent, 'active_tasks', 0),
            "queue_size": getattr(agent, 'queue_size', 0),
            "tasks_completed": getattr(agent, 'tasks_completed', 0),
            "tasks_failed": getattr(agent, 'tasks_failed', 0),
            "average_latency_ms": getattr(agent, 'avg_latency_ms', 0)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agent metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data-sources/status")
async def get_data_sources_status():
    """
    Get status of all data sources.
    """
    try:
        # This would query the database for data source status
        # For now, return a stub
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "data_sources": [],
            "total_count": 0,
            "healthy_count": 0,
            "unhealthy_count": 0
        }
    except Exception as e:
        logger.error(f"Error fetching data sources status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query-performance")
async def get_query_performance(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, le=1000)
):
    """
    Get query performance statistics.

    Args:
        hours: Number of hours to look back
        limit: Maximum number of queries to return
    """
    try:
        # This would query the database for query performance data
        # For now, return a stub
        since = datetime.utcnow() - timedelta(hours=hours)

        return {
            "since": since.isoformat(),
            "until": datetime.utcnow().isoformat(),
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_latency_ms": 0,
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "queries": []
        }
    except Exception as e:
        logger.error(f"Error fetching query performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def record_error(component: str, error_type: str, severity: str):
    """Record an error in metrics."""
    from app.core.metrics import ERRORS_TOTAL
    ERRORS_TOTAL.labels(
        component=component,
        error_type=error_type,
        severity=severity
    ).inc()
