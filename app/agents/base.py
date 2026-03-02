"""
Base Agent Class

Defines the core interface and lifecycle management for all AI agents.
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
import traceback

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent lifecycle status"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    WAITING = "waiting"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"


class AgentConfig(BaseModel):
    """Configuration for an AI agent"""
    name: str = Field(..., description="Unique agent name")
    description: str = Field(default="", description="Agent description")
    version: str = Field(default="1.0.0", description="Agent version")
    max_concurrent_tasks: int = Field(default=1, description="Max concurrent tasks")
    timeout_seconds: int = Field(default=300, description="Task timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    retry_delay_seconds: float = Field(default=1.0, description="Delay between retries")
    enabled: bool = Field(default=True, description="Whether agent is enabled")
    config: Dict[str, Any] = Field(default_factory=dict, description="Custom agent config")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "query_agent",
                "description": "Converts natural language to SQL",
                "version": "1.0.0",
                "max_concurrent_tasks": 5,
                "timeout_seconds": 300,
                "retry_attempts": 3,
                "retry_delay_seconds": 1.0,
                "enabled": True,
                "config": {"llm_provider": "openai", "model": "gpt-4"}
            }
        }


class BaseAgent(ABC):
    """
    Base class for all AI agents.

    Provides lifecycle management, error handling, retry logic, and
    a framework for agent-specific implementations.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.status: AgentStatus = AgentStatus.IDLE
        self.logger = logging.getLogger(f"agents.{config.name}")
        self._task_lock = asyncio.Lock()
        self._active_tasks: int = 0
        self._total_tasks_processed: int = 0
        self._total_errors: int = 0
        self._created_at: datetime = datetime.utcnow()
        self._last_heartbeat: Optional[datetime] = None
        self._callbacks: Dict[str, Callable] = {}

    @property
    def is_processing(self) -> bool:
        """Check if agent is currently processing tasks"""
        return self.status == AgentStatus.PROCESSING

    @property
    def active_tasks(self) -> int:
        """Get number of currently active tasks"""
        return self._active_tasks

    @property
    def metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        return {
            "name": self.config.name,
            "status": self.status.value,
            "active_tasks": self._active_tasks,
            "total_tasks_processed": self._total_tasks_processed,
            "total_errors": self._total_errors,
            "created_at": self._created_at.isoformat(),
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "uptime_seconds": (datetime.utcnow() - self._created_at).total_seconds(),
        }

    async def initialize(self) -> None:
        """
        Initialize the agent.

        Called once when agent is registered or loaded.
        Override this method to perform any setup operations.
        """
        self.logger.info(f"Initializing agent: {self.config.name}")
        self.status = AgentStatus.INITIALIZING

        try:
            await self._on_initialize()
            self.status = AgentStatus.IDLE
            self._update_heartbeat()
            self.logger.info(f"Agent initialized: {self.config.name}")
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.logger.error(f"Failed to initialize agent {self.config.name}: {e}")
            raise

    async def shutdown(self) -> None:
        """
        Shutdown the agent gracefully.

        Called when agent is unregistered or application is shutting down.
        Override this method to perform cleanup operations.
        """
        self.logger.info(f"Shutting down agent: {self.config.name}")
        self.status = AgentStatus.SHUTTING_DOWN

        try:
            await self._on_shutdown()
            self.status = AgentStatus.SHUTDOWN
            self.logger.info(f"Agent shutdown complete: {self.config.name}")
        except Exception as e:
            self.logger.error(f"Error during agent shutdown {self.config.name}: {e}")
            raise

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task with retry logic and error handling.

        Args:
            input_data: Input data for the task

        Returns:
            Output data from processing

        Raises:
            RuntimeError: If agent is not enabled or processing fails
        """
        if not self.config.enabled:
            raise RuntimeError(f"Agent {self.config.name} is not enabled")

        async with self._task_lock:
            if self._active_tasks >= self.config.max_concurrent_tasks:
                raise RuntimeError(
                    f"Agent {self.config.name} has reached max concurrent tasks: "
                    f"{self._active_tasks}/{self.config.max_concurrent_tasks}"
                )

        self._active_tasks += 1
        self.status = AgentStatus.PROCESSING
        self._update_heartbeat()

        last_error = None

        for attempt in range(self.config.retry_attempts):
            try:
                self.logger.info(
                    f"Processing task (attempt {attempt + 1}/{self.config.retry_attempts})"
                )

                # Set timeout for the task
                result = await asyncio.wait_for(
                    self._on_process(input_data),
                    timeout=self.config.timeout_seconds
                )

                self._active_tasks -= 1
                self._total_tasks_processed += 1
                self.status = AgentStatus.IDLE
                self._update_heartbeat()

                self.logger.info(f"Task processed successfully")
                return result

            except asyncio.TimeoutError:
                last_error = TimeoutError(
                    f"Task timed out after {self.config.timeout_seconds} seconds"
                )
                self.logger.warning(f"Task timed out (attempt {attempt + 1})")

            except Exception as e:
                last_error = e
                self._total_errors += 1
                self.logger.error(
                    f"Task processing error (attempt {attempt + 1}): {e}\n"
                    f"{traceback.format_exc()}"
                )

            # Wait before retrying (except on last attempt)
            if attempt < self.config.retry_attempts - 1:
                await asyncio.sleep(self.config.retry_delay_seconds * (attempt + 1))

        # All retry attempts failed
        self._active_tasks -= 1
        self.status = AgentStatus.ERROR
        self._update_heartbeat()

        self.logger.error(f"All retry attempts failed for task")
        raise RuntimeError(f"Task processing failed: {last_error}") from last_error

    async def health_check(self) -> Dict[str, Any]:
        """
        Check agent health status.

        Returns:
            Health status information
        """
        is_healthy = self.status not in [AgentStatus.ERROR, AgentStatus.SHUTDOWN]
        heartbeat_age = None

        if self._last_heartbeat:
            heartbeat_age = (datetime.utcnow() - self._last_heartbeat).total_seconds()

        return {
            "name": self.config.name,
            "status": self.status.value,
            "healthy": is_healthy,
            "active_tasks": self._active_tasks,
            "heartbeat_age_seconds": heartbeat_age,
            "metrics": self.metrics,
        }

    def register_callback(self, event: str, callback: Callable) -> None:
        """
        Register a callback for an event.

        Args:
            event: Event name (e.g., "task_complete", "error")
            callback: Callback function
        """
        self._callbacks[event] = callback
        self.logger.debug(f"Registered callback for event: {event}")

    def _update_heartbeat(self) -> None:
        """Update the last heartbeat timestamp"""
        self._last_heartbeat = datetime.utcnow()

    def _trigger_callback(self, event: str, data: Dict[str, Any]) -> None:
        """Trigger a registered callback"""
        if event in self._callbacks:
            try:
                self._callbacks[event](data)
            except Exception as e:
                self.logger.error(f"Error in callback for event '{event}': {e}")

    # Abstract methods to be implemented by concrete agents

    @abstractmethod
    async def _on_initialize(self) -> None:
        """
        Initialize the agent (implementation-specific).

        Override this to set up resources, load models, etc.
        """
        pass

    @abstractmethod
    async def _on_shutdown(self) -> None:
        """
        Shutdown the agent (implementation-specific).

        Override this to clean up resources, close connections, etc.
        """
        pass

    @abstractmethod
    async def _on_process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task (implementation-specific).

        Args:
            input_data: Input data for the task

        Returns:
            Output data from processing
        """
        pass

    def __repr__(self) -> str:
        return f"BaseAgent(name={self.config.name}, status={self.status.value})"
