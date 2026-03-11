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


@router.post("/query", summary="Execute Natural Language Query", response_description="Query execution result with generated SQL and results")
async def query_agent(
    request: QueryAgentRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Execute a query using the Query Agent.

    The Query Agent translates natural language questions into SQL,
    executes them against the connected ClickHouse database, and returns
    the results with optimization insights.

    **Authentication required** - User must be logged in.

    ## Request Body

    - `query` (string, required): Natural language query describing what data you want.
      Example: "How many users signed up each month last year?"

    ## Response

    Returns a dictionary containing:

    - `sql` (string): The generated SQL query
    - `rows` (list): Query results as a list of dictionaries
    - `formatted_output` (string): Human-readable formatted output (if requested)
    - `optimization_applied` (list, optional): List of optimizations applied
    - `explanation` (object, optional): Query explanation if explanation feature enabled

    ## Errors

    - `400 Bad Request`: Invalid query or parsing error
    - `401 Unauthorized`: Not authenticated
    - `403 Forbidden`: Not authorized
    - `503 Service Unavailable`: Query Agent not available or LLM provider down
    - `500 Internal Server Error`: Agent processing error

    ## Example

    **Request:**
    ```json
    {
      "query": "Show me the top 10 customers by revenue"
    }
    ```

    **Response:**
    ```json
    {
      "sql": "SELECT customer_id, SUM(amount) as total FROM orders GROUP BY customer_id ORDER BY total DESC LIMIT 10",
      "rows": [
        {"customer_id": 123, "total": 45000.50},
        {"customer_id": 456, "total": 38000.00}
      ],
      "optimization_applied": ["Added index hint", "Pushed aggregation"],
      "explanation": {
        "query_type": "aggregation",
        "complexity": "medium",
        "tables_accessed": ["orders"]
      }
    }
    ```

    ## Features

    - Query result caching (configurable TTL)
    - Automatic query optimization hints
    - Multi-dialect SQL support (ClickHouse, PostgreSQL, MySQL, SQLite)
    - Performance metrics tracking
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


@router.get("/status", summary="Get All Agent Status", response_description="Health and metrics for all AI agents")
async def agent_status(
    current_user: dict = Depends(get_current_active_user)
):
    """
    Retrieve the health status and metrics of all registered AI agents.

    **Authentication required** - User must be logged in.

    ## Response

    Returns a dictionary containing:

    - `agents` (dict): Health status for each agent, including:
      - `status` (string): Agent status (healthy, degraded, unhealthy, unknown)
      - `last_check` (string): ISO timestamp of last health check
      - `uptime_seconds` (number): How long agent has been running
      - `version` (string): Agent version
      - `capabilities` (list): List of agent capabilities
      - `error_count` (number): Number of errors detected
      - `last_error` (string, optional): Last error message if any
    - `registry_metrics` (dict): Registry-level metrics:
      - `total_agents` (number): Total number of registered agents
      - `healthy_agents` (number): Number of healthy agents
      - `active_agents` (number): Number of currently active agents
      - `queue_size` (number): Global task queue size
      - `uptime` (number): Registry uptime in seconds

    ## Errors

    - `401 Unauthorized`: Not authenticated
    - `403 Forbidden`: Not authorized to view agent status

    ## Example

    **Response:**
    ```json
    {
      "agents": {
        "query_agent": {
          "status": "healthy",
          "last_check": "2025-01-01T12:00:00Z",
          "uptime_seconds": 3600,
          "version": "1.0.0",
          "capabilities": ["nl_to_sql", "query_explanation", "query_optimization"],
          "error_count": 0
        },
        "design_agent": {
          "status": "healthy",
          "last_check": "2025-01-01T12:00:00Z",
          "uptime_seconds": 3600,
          "version": "1.0.0",
          "capabilities": ["platform_design", "infrastructure_provisioning", "cost_estimation"],
          "error_count": 0
        },
        "support_agent": {
          "status": "degraded",
          "last_check": "2025-01-01T12:00:00Z",
          "uptime_seconds": 3500,
          "version": "1.0.0",
          "capabilities": ["question_answering", "troubleshooting"],
          "error_count": 2,
          "last_error": "LLM provider rate limit exceeded"
        }
      },
      "registry_metrics": {
        "total_agents": 3,
        "healthy_agents": 2,
        "active_agents": 3,
        "queue_size": 0,
        "uptime": 3660
      }
    }
    ```

    ## Monitoring

    Use this endpoint to:
    - Monitor agent health in production systems
    - Check which agents are available for requests
    - Detect agent degradation before failures
    - Integrate with external monitoring systems (Grafana, Datadog)
    """
    health_status = await registry.health_check_all()
    metrics = registry.get_metrics()

    return {
        "agents": health_status,
        "registry_metrics": metrics
    }


@router.get("/query-agent/status", summary="Query Agent Health Status", response_description="Health status of the Query Agent")
async def query_agent_health(
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get detailed health status of the Query Agent.

    **Authentication required** - User must be logged in.

    The Query Agent is responsible for natural language to SQL translation
    and query execution.

    ## Response

    Returns a dictionary containing:

    - `status` (string): Agent status ("healthy", "degraded", "unhealthy", "unknown")
    - `last_check` (string): ISO 8601 timestamp of last health check
    - `uptime_seconds` (number): How long the agent has been running
    - `version` (string): Agent version identifier
    - `llm_provider` (string): Which LLM provider is configured (claude, openai, glm)
    - `llm_model` (string): Which LLM model is in use
    - `cache_hit_rate` (number, optional): Cache performance metric (0-1)
    - `queries_processed` (number, optional): Total queries processed since startup
    - `avg_query_time_ms` (number, optional): Average query processing time
    - `error_count` (number): Number of errors encountered
    - `last_error` (string, optional): Most recent error message if any

    ## Errors

    - `404 Not Found`: Query Agent is not registered
    - `401 Unauthorized`: Not authenticated
    - `403 Forbidden`: Not authorized

    ## Example

    **Response:**
    ```json
    {
      "status": "healthy",
      "last_check": "2025-01-01T12:00:00Z",
      "uptime_seconds": 86400,
      "version": "1.0.0",
      "llm_provider": "anthropic",
      "llm_model": "claude-3-opus-20240229",
      "cache_hit_rate": 0.65,
      "queries_processed": 15420,
      "avg_query_time_ms": 250,
      "error_count": 3
    }
    ```

    ## Usage

    Use this endpoint to:
    - Verify Query Agent is functioning correctly
    - Monitor LLM provider health and performance
    - Check cache effectiveness
    - Alert on agent degradation
    - Gather performance metrics for dashboards
    """
    agent = registry.get("query_agent")
    if not agent:
        raise HTTPException(status_code=404, detail="Query agent not found")

    health = await agent.health_check()
    return health


@router.post("/design", summary="Execute Design Agent Action", response_description="Design action result with platform design or deployment status")
async def design_agent(
    request: DesignAgentRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Execute a design agent action for platform infrastructure.

    The Design Agent is an AI that designs, plans, and provisions
    scalable data platforms using Kubernetes and ClickHouse.

    **Authentication required** - User must be logged in.

    ## Supported Actions

    ### 1. `design_platform`
    Generate a complete infrastructure design from requirements.

    **Parameters:**
    - `description` (string, required): Natural language description of platform needs.
      Example: "I need a real-time analytics platform with 10TB data, 1000 QPS, high availability, $1000/month budget"
    - `workload_type` (string, optional): Override detected workload type.
    - `data_volume_tb` (number, optional): Explicit data volume in TB
    - `query_rate_qps` (number, optional): Expected queries per second
    - `availability_requirement` (string, optional): "standard", "high", "critical"
    - `budget_monthly` (number, optional): Monthly budget in USD

    **Returns:** DesignSolution with infrastructure layout, cost estimates, availability calculations.

    ### 2. `provision_cluster`
    Plan a cluster deployment (dry-run). Does NOT actually deploy.

    **Parameters:**
    - `design_id` (string, required): ID of previously generated design
    - `namespace` (string, optional): Kubernetes namespace (default: "aidatalabs")
    - `dry_run` (boolean, optional): If true, only plan without deploying (default: true)

    **Returns:** Deployment plan with manifest preview, resource requirements.

    ### 3. `get_design`
    Retrieve a previously generated platform design.

    **Parameters:**
    - `design_id` (string, required): Design ID to retrieve

    **Returns:** Full DesignSolution details.

    ### 4. `get_deployment_status`
    Check status of a deployment operation.

    **Parameters:**
    - `deployment_id` (string, required): Deployment ID to check

    **Returns:** Deployment status (pending, running, completed, failed) with progress.

    ### 5. `recommend_configuration`
    Get configuration recommendations for different tiers.

    **Parameters:**
    - `workload_type` (string, required): Type of workload
    - `data_volume_tb` (number, required): Data volume in TB
    - `query_rate_qps` (number, required): Expected QPS

    **Returns:** Three configuration options (standard, performance, high-availability) with specs and costs.

    ## Errors

    - `400 Bad Request`: Missing required parameters or invalid action
    - `404 Not Found`: Design or deployment not found
    - `503 Service Unavailable`: Design Agent not available
    - `500 Internal Server Error`: Agent processing error

    ## Example

    **Request:**
    ```json
    {
      "action": "design_platform",
      "parameters": {
        "description": "I need a real-time analytics platform with 10TB of data, handling about 1000 queries per second, with high availability. My budget is $1000 per month."
      }
    }
    ```

    **Response:**
    ```json
    {
      "design_id": "design_abc123",
      "estimated_monthly_cost": 850.50,
      "estimated_availability": 0.9995,
      "clickhouse_cluster": {
        "shard_count": 3,
        "replica_count": 2,
        "zookeeper_nodes": 3,
        "storage_per_node": "1000GB",
        "storage_tier": "ssd"
      },
      "kubernetes_cluster": {
        "node_count": 6,
        "total_cpu": "12 cores",
        "total_memory": "48Gi"
      },
      "recommended_configuration": "performance"
    }
    ```

    ## Capabilities

    - Natural language requirement parsing
    - Multi-objective infrastructure optimization
    - Kubernetes manifest generation (12 manifest types)
    - ClickHouse cluster sizing and configuration
    - Cost estimation with transparent pricing model
    - Availability calculations based on redundancy
    - Configuration recommendations across 3 tiers (standard/performance/HA)
    - Dry-run deployment planning

    ## Notes

    - Actual cluster deployment is NOT performed by this agent in MVP (dry-run only)
    - Generated manifests can be applied manually via kubectl
    - Extended capabilities planned for Phase 3 (actual deployment operators)
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


@router.get("/design-agent/status", summary="Design Agent Health Status", response_description="Health status of the Platform Designer Agent")
async def design_agent_health(
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get detailed health status of the Platform Designer Agent.

    **Authentication required** - User must be logged in.

    The Design Agent designs and manages data platforms using Kubernetes
    and ClickHouse. It translates business requirements into infrastructure
    blueprints and generates Kubernetes manifests.

    ## Response

    Returns a dictionary containing:

    - `status` (string): Agent status ("healthy", "degraded", "unhealthy", "unknown")
    - `last_check` (string): ISO 8601 timestamp of last health check
    - `uptime_seconds` (number): How long the agent has been running
    - `version` (string): Agent version identifier (currently "1.0.0")
    - `capabilities` (list): List of supported actions:
      - "parse_requirements"
      - "design_platform"
      - "generate_manifests"
      - "provision_cluster"
      - "estimate_cost"
      - "recommend_configuration"
      - "get_design"
      - "get_deployment_status"
      - "list_designs"
    - `designs_count` (number): Number of cached platform designs
    - `deployments_count` (number): Number of tracked deployments
    - `k8s_configured` (boolean): Whether Kubernetes configuration is loaded
    - `clickhouse_configured` (boolean): Whether ClickHouse configuration is loaded
    - `last_design_time` (string, optional): Timestamp of last design operation
    - `error_count` (number): Number of errors encountered
    - `last_error` (string, optional): Most recent error message if any

    ## Errors

    - `404 Not Found`: Design Agent is not registered
    - `401 Unauthorized`: Not authenticated
    - `403 Forbidden`: Not authorized

    ## Example

    **Response:**
    ```json
    {
      "status": "healthy",
      "last_check": "2025-01-01T12:00:00Z",
      "uptime_seconds": 86400,
      "version": "1.0.0",
      "capabilities": [
        "parse_requirements",
        "design_platform",
        "generate_manifests",
        "provision_cluster",
        "estimate_cost",
        "recommend_configuration",
        "get_design",
        "get_deployment_status",
        "list_designs"
      ],
      "designs_count": 15,
      "deployments_count": 3,
      "k8s_configured": true,
      "clickhouse_configured": true,
      "last_design_time": "2025-01-01T11:45:00Z",
      "error_count": 0
    }
    ```

    ## Notes

    The Design Agent includes:
    - **Design Engine**: Parses requirements, computes optimal infrastructure
    - **K8s Manifest Generator**: Produces production-ready YAML for ClickHouse, ZooKeeper, monitoring
    - **Cost Estimation**: Transparent pricing based on compute, memory, storage
    - **Dry-run Provisioning**: Planning without actual deployment (MVP)

    Future enhancements: live Kubernetes API integration, ClickHouse Operator, Terraform generation.
    """
    agent = registry.get("design_agent")
    if not agent:
        raise HTTPException(status_code=404, detail="Design agent not found")

    health = await agent.health_check()
    return health


@router.post("/support", summary="Execute Support Agent Action", response_description="Support action result with assistance response")
async def support_agent(
    request: SupportAgentRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Execute a support action using the Support Agent.

    The Support Agent provides 24/7 customer support, answers questions,
    troubleshoots issues, and escalates to human support when needed.

    **Authentication required** - User must be logged in.

    ## Supported Actions

    ### 1. `answer_question`
    Answer a user's question about the platform.

    **Parameters:**
    - `question` (string, required): The question to answer
    - `context` (string, optional): Additional context or previous conversation

    **Returns:** Answer with confidence score and source references.

    ### 2. `troubleshoot`
    Help diagnose and resolve an issue.

    **Parameters:**
    - `issue_description` (string, required): Description of the problem
    - `error_logs` (string, optional): Any error messages or logs
    - `reproduction_steps` (string, optional): Steps to reproduce

    **Returns:** Diagnostic assessment, suggested fixes, and next steps.

    ### 3. `get_documentation`
    Retrieve documentation for a specific topic.

    **Parameters:**
    - `topic` (string, required): Documentation topic (e.g., "query-agent", "clickhouse-optimization")
    - `format` (string, optional): Desired format ("markdown", "html", "summary")

    **Returns:** Documentation content formatted as requested.

    ### 4. `submit_feedback`
    Submit user feedback for improvement.

    **Parameters:**
    - `feedback` (string, required): User feedback text
    - `category` (string, optional): Feedback category (bug, feature, improvement)
    - `rating` (integer, optional): User satisfaction rating (1-5)

    **Returns:** Confirmation and feedback ID.

    ### 5. `escalate_issue`
    Escalate an unresolved issue to human support.

    **Parameters:**
    - `issue_summary` (string, required): Summary of the issue
    - `conversation_history` (list, optional): Previous support interactions
    - `urgency` (string, optional): "low", "medium", "high", "critical"

    **Returns:** Escalation confirmation and ticket ID.

    ### 6. `get_conversation_history`
    Retrieve previous conversation with the support agent.

    **Parameters:**
    - `user_id` (string, optional): User ID (defaults to current user)
    - `limit` (integer, optional): Maximum number of conversations to return (default 10)

    **Returns:** List of conversation sessions with timestamps.

    ## Errors

    - `400 Bad Request`: Invalid action or missing required parameters
    - `404 Not Found`: Requested conversation or documentation not found
    - `503 Service Unavailable`: Support Agent not available
    - `500 Internal Server Error`: Agent processing error

    ## Example

    **Request:**
    ```json
    {
      "action": "answer_question",
      "parameters": {
        "question": "How do I optimize my ClickHouse queries?",
        "context": "I'm running analytics on large event tables"
      }
    }
    ```

    **Response:**
    ```json
    {
      "answer": "To optimize ClickHouse queries, ensure you're using appropriate primary keys, avoid SELECT *, consider using projections for common aggregations, and leverage materialized views for pre-computed results...",
      "confidence": 0.92,
      "sources": [
        "QUERY_OPTIMIZATION_GUIDE",
        "CLICKHOUSE_BEST_PRACTICES"
      ],
      "related_topics": ["query-caching", "schema-design", "indexing"]
    }
    ```

    ## Capabilities

    - Natural language Q&A using RAG over documentation
    - Multi-step troubleshooting workflows
    - Contextual documentation retrieval
    - Feedback collection and analysis
    - Intelligent escalation routing
    - Conversation history tracking
    - Integration with knowledge base (Notion, Confluence, etc.)

    ## Notes

    - Support Agent uses Retrieval-Augmented Generation (RAG) for accurate answers
    - All conversations are logged for continuous improvement
    - Escalated issues create tickets in integrated support system (future)
    - Feedback is used to improve documentation and agent responses
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
