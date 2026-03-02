"""
Agent Task Queue

Manages task queuing and execution for agents.
"""

import logging
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime, timedelta
import uuid

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(int, Enum):
    """Task priority levels (higher number = higher priority)"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class Task(BaseModel):
    """Task for agent execution"""
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    agent_name: str = Field(..., description="Agent to execute the task")
    task_type: str = Field(..., description="Type of task")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Task input data")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="Task priority")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task status")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Task creation time")
    started_at: Optional[datetime] = Field(None, description="Task start time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")
    timeout_seconds: int = Field(default=300, description="Task timeout in seconds")
    retry_count: int = Field(default=0, description="Number of retries")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Task metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "agent_name": "query_agent",
                "task_type": "nl_to_sql",
                "input_data": {"query": "Show me all users from the US"},
                "priority": TaskPriority.NORMAL,
                "timeout_seconds": 300
            }
        }

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get task duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def age_seconds(self) -> float:
        """Get task age in seconds"""
        return (datetime.utcnow() - self.created_at).total_seconds()


class TaskQueue:
    """
    Task queue for managing agent tasks.

    Supports priority queuing, retries, timeouts, and task tracking.
    """

    def __init__(self, max_concurrent_tasks: int = 10):
        self.logger = logging.getLogger("agents.task_queue")
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._tasks: Dict[str, Task] = {}
        self._agent_tasks: Dict[str, Dict[str, Task]] = {}
        self._max_concurrent_tasks: int = max_concurrent_tasks
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, List[Callable]] = {}

    async def start(self) -> None:
        """Start the task queue worker"""
        if self._running:
            self.logger.warning("Task queue already running")
            return

        self.logger.info("Starting task queue")
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        """Stop the task queue worker"""
        if not self._running:
            return

        self.logger.info("Stopping task queue")
        self._running = False

        # Cancel worker task
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # Wait for active tasks to complete (with timeout)
        if self._active_tasks:
            self.logger.info(f"Waiting for {len(self._active_tasks)} active tasks...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_tasks.values(), return_exceptions=True),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                self.logger.warning("Timeout waiting for active tasks to complete")

        self.logger.info("Task queue stopped")

    async def _worker(self) -> None:
        """Worker task that processes the queue"""
        self.logger.debug("Task queue worker started")

        while self._running:
            try:
                # Wait for active tasks to complete if at capacity
                while len(self._active_tasks) >= self._max_concurrent_tasks:
                    await asyncio.sleep(0.1)

                    # Clean up completed tasks
                    self._cleanup_completed_tasks()

                    if not self._running:
                        break

                if not self._running:
                    break

                # Get next task from queue (with timeout)
                try:
                    priority_item = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                priority, task_id = priority_item
                task = self._tasks.get(task_id)

                if not task or task.status != TaskStatus.QUEUED:
                    continue

                # Execute the task
                await self._execute_task(task)

            except Exception as e:
                self.logger.error(f"Error in task queue worker: {e}")

        self.logger.debug("Task queue worker stopped")

    def _cleanup_completed_tasks(self) -> None:
        """Clean up completed task futures"""
        completed = [
            task_id for task_id, future in self._active_tasks.items()
            if future.done()
        ]

        for task_id in completed:
            del self._active_tasks[task_id]

    async def _execute_task(self, task: Task) -> None:
        """
        Execute a task.

        Args:
            task: Task to execute
        """
        agent_name = task.agent_name

        # Mark as processing
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.utcnow()

        # Track active task
        async def task_wrapper():
            try:
                # Get the agent from registry (this will be injected)
                from app.agents.registry import AgentRegistry
                # Note: In production, pass registry instance or use dependency injection

                result = await asyncio.wait_for(
                    self._process_task(task),
                    timeout=task.timeout_seconds
                )

                task.result = result
                task.status = TaskStatus.COMPLETED

            except asyncio.TimeoutError:
                task.status = TaskStatus.TIMEOUT
                task.error = f"Task timed out after {task.timeout_seconds} seconds"
                self.logger.error(
                    f"Task {task.id} timed out for agent {agent_name}"
                )

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.retry_count += 1
                self.logger.error(f"Task {task.id} failed for agent {agent_name}: {e}")

                # Retry if allowed
                if task.retry_count < task.max_retries:
                    task.status = TaskStatus.QUEUED
                    await self.requeue(task.id)
                    return

            finally:
                task.completed_at = datetime.utcnow()

                # Remove from agent's active tasks
                if agent_name in self._agent_tasks:
                    self._agent_tasks[agent_name].pop(task.id, None)

                # Trigger callbacks
                self._trigger_callbacks(task.status.value, task)

        future = asyncio.create_task(task_wrapper())
        self._active_tasks[task.id] = future

    async def _process_task(self, task: Task) -> Dict[str, Any]:
        """
        Process a task (to be overridden or injected).

        Args:
            task: Task to process

        Returns:
            Task result
        """
        # This is a placeholder - in production, you'd inject a registry or processor
        # For now, we'll return a simple success response
        return {"status": "success", "data": {}}

    async def submit(
        self,
        agent_name: str,
        task_type: str,
        input_data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs
    ) -> Task:
        """
        Submit a task to the queue.

        Args:
            agent_name: Agent to execute the task
            task_type: Type of task
            input_data: Task input data
            priority: Task priority
            **kwargs: Additional task parameters

        Returns:
            Created task
        """
        task = Task(
            agent_name=agent_name,
            task_type=task_type,
            input_data=input_data,
            priority=priority,
            **kwargs
        )

        self._tasks[task.id] = task

        # Add to agent's task list
        if agent_name not in self._agent_tasks:
            self._agent_tasks[agent_name] = {}

        self._agent_tasks[agent_name][task.id] = task

        # Add to priority queue (negative priority for max-heap behavior)
        await self._queue.put((-priority.value, task.id))

        task.status = TaskStatus.QUEUED

        self.logger.info(
            f"Task submitted: {task.id} ({task_type}) -> {agent_name} "
            f"[priority={priority.name}]"
        )

        return task

    async def requeue(self, task_id: str) -> None:
        """
        Requeue a failed task for retry.

        Args:
            task_id: Task ID to requeue
        """
        task = self._tasks.get(task_id)

        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.QUEUED

        # Add back to queue
        await self._queue.put((-task.priority.value, task.id))

        self.logger.info(f"Task requeued: {task_id} (retry {task.retry_count})")

    async def cancel(self, task_id: str) -> bool:
        """
        Cancel a task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if task was cancelled, False if not found or already completed
        """
        task = self._tasks.get(task_id)

        if not task:
            return False

        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False

        task.status = TaskStatus.CANCELLED

        # Cancel active task if processing
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()

        self.logger.info(f"Task cancelled: {task_id}")
        self._trigger_callbacks(TaskStatus.CANCELLED.value, task)

        return True

    def get(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None if not found
        """
        return self._tasks.get(task_id)

    def get_agent_tasks(
        self,
        agent_name: str,
        status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """
        Get tasks for a specific agent.

        Args:
            agent_name: Agent name
            status: Filter by status

        Returns:
            List of tasks
        """
        tasks = list(self._agent_tasks.get(agent_name, {}).values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        return tasks

    def get_all_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: Optional[int] = None
    ) -> List[Task]:
        """
        Get all tasks with optional filtering.

        Args:
            status: Filter by status
            limit: Maximum number of tasks to return

        Returns:
            List of tasks
        """
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        # Sort by created time (newest first)
        tasks = sorted(tasks, key=lambda t: t.created_at, reverse=True)

        if limit:
            tasks = tasks[:limit]

        return tasks

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get task queue metrics.

        Returns:
            Dictionary of metrics
        """
        total_tasks = len(self._tasks)

        tasks_by_status = {}
        for task in self._tasks.values():
            status = task.status.value
            tasks_by_status[status] = tasks_by_status.get(status, 0) + 1

        active_task_count = sum(
            1 for t in self._tasks.values()
            if t.status == TaskStatus.PROCESSING
        )

        avg_duration = None
        completed_tasks = [t for t in self._tasks.values() if t.duration_seconds]
        if completed_tasks:
            avg_duration = sum(t.duration_seconds for t in completed_tasks) / len(completed_tasks)

        return {
            "running": self._running,
            "total_tasks": total_tasks,
            "queue_size": self._queue.qsize(),
            "active_tasks": active_task_count,
            "max_concurrent_tasks": self._max_concurrent_tasks,
            "tasks_by_status": tasks_by_status,
            "avg_duration_seconds": avg_duration,
            "agents_with_tasks": len(self._agent_tasks),
        }

    def register_callback(self, status: str, callback: Callable[[Task], None]) -> None:
        """
        Register a callback for task status changes.

        Args:
            status: Task status to listen for
            callback: Callback function
        """
        if status not in self._callbacks:
            self._callbacks[status] = []

        self._callbacks[status].append(callback)

    def _trigger_callbacks(self, status: str, task: Task) -> None:
        """Trigger callbacks for a status change"""
        if status in self._callbacks:
            for callback in self._callbacks[status]:
                try:
                    callback(task)
                except Exception as e:
                    self.logger.error(f"Error in callback for status '{status}': {e}")

    def __repr__(self) -> str:
        return (
            f"TaskQueue("
            f"running={self._running}, "
            f"queue_size={self._queue.qsize()}, "
            f"total_tasks={len(self._tasks)}"
            f")"
        )
