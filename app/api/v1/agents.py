"""
Agents API - AI agent endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from app.core.security import get_current_active_user
from app.agents import registry

router = APIRouter()
logger = logging.getLogger(__name__)


# Request/Response Models
class QueryAgentRequest(BaseModel):
    """Request model for Query Agent"""
    query: str


class DesignAgentRequest(BaseModel):
    """Request model for Design Agent"""
    action: str
    parameters: Dict[str, Any] = {}


class SupportAgentRequest(BaseModel):
    """Request model for Support Agent"""
    action: str
    parameters: Dict[str, Any] = {}


@router.post("/query")
async def query_agent(
    request: QueryAgentRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Execute query using Query Agent

    Translates natural language to SQL and executes against ClickHouse.

    **Authentication required**

    Args:
        request: Query agent request with natural language query

    Returns:
        Query result with generated SQL, rows, and formatted output
    """
    logger.info(f"Query agent request: {request.query}")

    # Get QueryAgent from registry
    agent = registry.get("query_agent")
    if not agent:
        raise HTTPException(status_code=503, detail="Query agent not available")

    try:
        # Process the query
        result = await agent.process({
            "query": request.query,
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


@router.post("/design")
async def design_agent(
    request: DesignAgentRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Execute design action using Design Agent

    Design and manage data platforms using Kubernetes and ClickHouse.

    **Authentication required**

    Supported actions:
        - design_platform: Design a platform infrastructure
        - provision_cluster: Provision a ClickHouse cluster
        - get_design: Get a platform design by ID
        - get_deployment_status: Get deployment status
        - recommend_configuration: Get configuration recommendations

    Returns:
        Action result with status and data
    """
    logger.info(f"Design agent request: {request.action}")

    # Get DesignAgent from registry
    agent = registry.get("design_agent")
    if not agent:
        raise HTTPException(status_code=503, detail="Design agent not available")

    try:
        # Process the action
        result = await agent.process({
            "action": request.action,
            "parameters": request.parameters,
            "user_id": current_user.get("id", 0)
        })

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Design agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal agent error")


@router.get("/design-agent/status")
async def design_agent_health(
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get Design Agent health status

    **Authentication required**

    Returns:
        Design Agent health information
    """
    agent = registry.get("design_agent")
    if not agent:
        raise HTTPException(status_code=404, detail="Design agent not found")

    health = await agent.health_check()
    return health


@router.post("/support")
async def support_agent(
    request: SupportAgentRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Execute support action using Support Agent

    Provide customer support, troubleshooting, and assistance.

    **Authentication required**

    Supported actions:
        - answer_question: Answer a user question
        - troubleshoot: Troubleshoot an issue
        - get_documentation: Get documentation for a topic
        - submit_feedback: Submit user feedback
        - escalate_issue: Escalate an issue to human support
        - get_conversation_history: Get conversation history

    Returns:
        Action result with status and data
    """
    logger.info(f"Support agent request: {request.action}")

    # Get SupportAgent from registry
    agent = registry.get("support_agent")
    if not agent:
        raise HTTPException(status_code=503, detail="Support agent not available")

    try:
        # Process the action
        result = await agent.process({
            "action": request.action,
            "parameters": request.parameters,
            "user_id": current_user.get("id", 0)
        })

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Support agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal agent error")


@router.get("/support-agent/status")
async def support_agent_health(
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get Support Agent health status

    **Authentication required**

    Returns:
        Support Agent health information
    """
    agent = registry.get("support_agent")
    if not agent:
        raise HTTPException(status_code=404, detail="Support agent not found")

    health = await agent.health_check()
    return health
