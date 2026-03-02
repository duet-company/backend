"""
Agent Registry

Manages agent registration, discovery, and lifecycle.
"""

import logging
from typing import Dict, Optional, List, Type
from datetime import datetime

from app.agents.base import BaseAgent, AgentConfig, AgentStatus


class AgentRegistry:
    """
    Registry for managing AI agents.

    Provides registration, discovery, and lifecycle management
    for all agents in the system.
    """

    def __init__(self):
        self.logger = logging.getLogger("agents.registry")
        self._agents: Dict[str, BaseAgent] = {}
        self._agent_classes: Dict[str, Type[BaseAgent]] = {}
        self._configs: Dict[str, AgentConfig] = {}
        self._created_at: datetime = datetime.utcnow()

    def register_class(
        self,
        name: str,
        agent_class: Type[BaseAgent],
        config: AgentConfig
    ) -> None:
        """
        Register an agent class for later instantiation.

        Args:
            name: Unique agent name
            agent_class: Agent class to register
            config: Agent configuration
        """
        self.logger.info(f"Registering agent class: {name}")

        if name in self._agent_classes:
            self.logger.warning(f"Agent class already registered: {name}, overwriting")

        self._agent_classes[name] = agent_class
        self._configs[name] = config
        self.logger.info(f"Agent class registered: {name}")

    def register_agent(self, agent: BaseAgent) -> None:
        """
        Register an instantiated agent.

        Args:
            agent: Agent instance to register
        """
        name = agent.config.name
        self.logger.info(f"Registering agent instance: {name}")

        if name in self._agents:
            self.logger.warning(f"Agent already registered: {name}, replacing")

        self._agents[name] = agent
        self.logger.info(f"Agent registered: {name}")

    async def create_and_register(self, name: str) -> BaseAgent:
        """
        Create an agent instance from a registered class and register it.

        Args:
            name: Agent name (must be registered as a class)

        Returns:
            Created agent instance

        Raises:
            ValueError: If agent class is not registered
        """
        if name not in self._agent_classes:
            raise ValueError(f"Agent class not registered: {name}")

        self.logger.info(f"Creating agent instance: {name}")

        agent_class = self._agent_classes[name]
        config = self._configs[name]

        agent = agent_class(config)
        await agent.initialize()
        self.register_agent(agent)

        return agent

    async def unregister(self, name: str) -> bool:
        """
        Unregister and shutdown an agent.

        Args:
            name: Agent name to unregister

        Returns:
            True if agent was unregistered, False if not found
        """
        if name not in self._agents:
            self.logger.warning(f"Agent not found: {name}")
            return False

        self.logger.info(f"Unregistering agent: {name}")

        agent = self._agents[name]
        await agent.shutdown()
        del self._agents[name]

        self.logger.info(f"Agent unregistered: {name}")
        return True

    def get(self, name: str) -> Optional[BaseAgent]:
        """
        Get a registered agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(name)

    def get_all(self) -> Dict[str, BaseAgent]:
        """
        Get all registered agents.

        Returns:
            Dictionary of agent name to agent instance
        """
        return self._agents.copy()

    def list_agents(
        self,
        status: Optional[AgentStatus] = None,
        enabled_only: bool = False
    ) -> List[Dict[str, any]]:
        """
        List agents with optional filtering.

        Args:
            status: Filter by agent status
            enabled_only: Only return enabled agents

        Returns:
            List of agent information dictionaries
        """
        agents = []

        for name, agent in self._agents.items():
            if status and agent.status != status:
                continue

            if enabled_only and not agent.config.enabled:
                continue

            agents.append({
                "name": name,
                "description": agent.config.description,
                "version": agent.config.version,
                "status": agent.status.value,
                "enabled": agent.config.enabled,
                "active_tasks": agent.active_tasks,
                "metrics": agent.metrics,
            })

        return agents

    async def initialize_all(self) -> None:
        """
        Initialize all registered agents.

        Raises:
            RuntimeError: If any agent fails to initialize
        """
        self.logger.info("Initializing all registered agents")

        errors = []

        for name, agent in self._agents.items():
            try:
                if agent.status == AgentStatus.IDLE:
                    await agent.initialize()
            except Exception as e:
                self.logger.error(f"Failed to initialize agent {name}: {e}")
                errors.append((name, str(e)))

        if errors:
            raise RuntimeError(f"Failed to initialize agents: {errors}")

        self.logger.info("All agents initialized")

    async def shutdown_all(self) -> None:
        """
        Shutdown all registered agents.
        """
        self.logger.info("Shutting down all registered agents")

        for name, agent in list(self._agents.items()):
            try:
                await agent.shutdown()
            except Exception as e:
                self.logger.error(f"Error shutting down agent {name}: {e}")

        self.logger.info("All agents shutdown")

    def get_metrics(self) -> Dict[str, any]:
        """
        Get registry metrics.

        Returns:
            Dictionary of registry metrics
        """
        total_agents = len(self._agents)
        total_classes = len(self._agent_classes)

        agents_by_status = {}
        for agent in self._agents.values():
            status = agent.status.value
            agents_by_status[status] = agents_by_status.get(status, 0) + 1

        total_active_tasks = sum(a.active_tasks for a in self._agents.values())
        total_tasks_processed = sum(a.metrics["total_tasks_processed"] for a in self._agents.values())
        total_errors = sum(a.metrics["total_errors"] for a in self._agents.values())

        return {
            "registry_uptime_seconds": (datetime.utcnow() - self._created_at).total_seconds(),
            "total_registered_agents": total_agents,
            "total_registered_classes": total_classes,
            "agents_by_status": agents_by_status,
            "total_active_tasks": total_active_tasks,
            "total_tasks_processed": total_tasks_processed,
            "total_errors": total_errors,
        }

    async def health_check_all(self) -> Dict[str, Dict[str, any]]:
        """
        Get health status of all registered agents.

        Returns:
            Dictionary of agent name to health status
        """
        health_status = {}

        for name, agent in self._agents.items():
            try:
                health_status[name] = await agent.health_check()
            except Exception as e:
                health_status[name] = {
                    "name": name,
                    "status": "error",
                    "healthy": False,
                    "error": str(e),
                }

        return health_status

    def __repr__(self) -> str:
        return f"AgentRegistry(agents={len(self._agents)}, classes={len(self._agent_classes)})"
