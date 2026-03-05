"""
AI Agents Framework

Base classes and utilities for building AI agents in AI Data Labs platform.
"""

from app.agents.base import BaseAgent, AgentConfig, AgentStatus
from app.agents.registry import AgentRegistry
from app.agents.communication import CommunicationChannel, MessageType
from app.agents.task_queue import TaskQueue, Task, TaskStatus
from app.agents.query_agent import QueryAgent, ClickHouseSchemaLoader, create_query_agent
from app.agents.design_agent import DesignAgent, create_design_agent
from app.agents.support_agent import SupportAgent, create_support_agent

# Global agent registry instance
registry = AgentRegistry()

# Register default agents
registry.register_class("query_agent", QueryAgent, create_query_agent().config)
registry.register_class("design_agent", DesignAgent, create_design_agent().config)
registry.register_class("support_agent", SupportAgent, create_support_agent().config)

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentStatus",
    "AgentRegistry",
    "CommunicationChannel",
    "MessageType",
    "TaskQueue",
    "Task",
    "TaskStatus",
    "QueryAgent",
    "ClickHouseSchemaLoader",
    "create_query_agent",
    "DesignAgent",
    "create_design_agent",
    "SupportAgent",
    "create_support_agent",
    "registry",
]
