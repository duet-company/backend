"""
Agents API - AI agent endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
import logging

from app.core.security import get_current_active_user
from app.agents import registry

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/query")
async def query_agent(
    query: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Execute query using Query Agent

    Translates natural language to SQL and executes against ClickHouse.

    **Authentication required**

    Args:
        query: Natural language query string

    Returns:
        Query result with generated SQL, rows, and formatted output
    """
    logger.info(f"Query agent request: {query}")

    # Get QueryAgent from registry
    agent = registry.get("query_agent")
    if not agent:
        raise HTTPException(status_code=503, detail="Query agent not available")

    try:
        # Process the query
        result = await agent.process({
            "query": query,
            "user_id": current_user.get("id", 0)
        })

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Query agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal agent error")


@router.get("/status")
async def agent_status(
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get status of all AI agents

    **Authentication required**

    Returns:
        Dictionary with agent health and metrics
    """
    health_status = await registry.health_check_all()
    metrics = registry.get_metrics()

    return {
        "agents": health_status,
        "registry_metrics": metrics
    }


@router.get("/query-agent/status")
async def query_agent_health(
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get Query Agent health status

    **Authentication required**

    Returns:
        Query Agent health information
    """
    agent = registry.get("query_agent")
    if not agent:
        raise HTTPException(status_code=404, detail="Query agent not found")

    health = await agent.health_check()
    return health
