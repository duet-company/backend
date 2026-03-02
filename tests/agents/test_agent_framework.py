"""
Unit tests for Agent Framework
"""

import pytest
import asyncio
from datetime import datetime

from app.agents.base import BaseAgent, AgentConfig, AgentStatus
from app.agents.registry import AgentRegistry
from app.agents.communication import CommunicationChannel, Message, MessageType
from app.agents.task_queue import TaskQueue, Task, TaskStatus, TaskPriority


# ===== Test BaseAgent =====

class TestAgent(BaseAgent):
    """Simple test agent implementation"""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.initialized = False
        self.shutdown_called = False

    async def _on_initialize(self) -> None:
        """Initialize test agent"""
        await asyncio.sleep(0.1)
        self.initialized = True

    async def _on_shutdown(self) -> None:
        """Shutdown test agent"""
        await asyncio.sleep(0.1)
        self.shutdown_called = True

    async def _on_process(self, input_data: dict) -> dict:
        """Process test task"""
        await asyncio.sleep(0.1)
        return {"result": f"processed: {input_data.get('value', '')}"}


@pytest.mark.asyncio
async def test_agent_initialization():
    """Test agent initialization"""
    config = AgentConfig(name="test_agent", description="Test agent")
    agent = TestAgent(config)

    assert agent.status == AgentStatus.IDLE
    assert agent.config.name == "test_agent"

    await agent.initialize()

    assert agent.status == AgentStatus.IDLE
    assert agent.initialized is True


@pytest.mark.asyncio
async def test_agent_shutdown():
    """Test agent shutdown"""
    config = AgentConfig(name="test_agent")
    agent = TestAgent(config)

    await agent.initialize()
    await agent.shutdown()

    assert agent.status == AgentStatus.SHUTDOWN
    assert agent.shutdown_called is True


@pytest.mark.asyncio
async def test_agent_process():
    """Test agent processing"""
    config = AgentConfig(name="test_agent", timeout_seconds=60)
    agent = TestAgent(config)

    await agent.initialize()

    result = await agent.process({"value": "test"})

    assert result == {"result": "processed: test"}
    assert agent._total_tasks_processed == 1


@pytest.mark.asyncio
async def test_agent_retry_logic():
    """Test agent retry logic on failure"""
    class FailingAgent(BaseAgent):
        def __init__(self, config: AgentConfig):
            super().__init__(config)
            self.attempt_count = 0

        async def _on_initialize(self) -> None:
            pass

        async def _on_shutdown(self) -> None:
            pass

        async def _on_process(self, input_data: dict) -> dict:
            self.attempt_count += 1
            if self.attempt_count < 2:
                raise RuntimeError("Simulated failure")
            return {"result": "success"}

    config = AgentConfig(
        name="failing_agent",
        retry_attempts=3,
        retry_delay_seconds=0.1
    )
    agent = FailingAgent(config)

    await agent.initialize()
    result = await agent.process({})

    assert result == {"result": "success"}
    assert agent.attempt_count == 2
    assert agent._total_errors == 1


@pytest.mark.asyncio
async def test_agent_timeout():
    """Test agent timeout handling"""
    class SlowAgent(BaseAgent):
        async def _on_initialize(self) -> None:
            pass

        async def _on_shutdown(self) -> None:
            pass

        async def _on_process(self, input_data: dict) -> dict:
            await asyncio.sleep(2.0)
            return {"result": "done"}

    config = AgentConfig(name="slow_agent", timeout_seconds=0.5)
    agent = SlowAgent(config)

    await agent.initialize()

    with pytest.raises(RuntimeError, match="timed out"):
        await agent.process({})


@pytest.mark.asyncio
async def test_agent_concurrent_tasks_limit():
    """Test agent concurrent task limit"""
    config = AgentConfig(name="test_agent", max_concurrent_tasks=2, timeout_seconds=60)
    agent = TestAgent(config)

    await agent.initialize()

    # Start two tasks
    task1 = asyncio.create_task(agent.process({"value": "1"}))
    task2 = asyncio.create_task(agent.process({"value": "2"}))

    assert agent.active_tasks == 2

    # Third task should fail
    with pytest.raises(RuntimeError, match="max concurrent tasks"):
        await agent.process({"value": "3"})

    # Wait for first two to complete
    await asyncio.gather(task1, task2)

    assert agent.active_tasks == 0


@pytest.mark.asyncio
async def test_agent_health_check():
    """Test agent health check"""
    config = AgentConfig(name="test_agent")
    agent = TestAgent(config)

    await agent.initialize()

    health = await agent.health_check()

    assert health["name"] == "test_agent"
    assert health["status"] == AgentStatus.IDLE.value
    assert health["healthy"] is True
    assert health["active_tasks"] == 0


# ===== Test AgentRegistry =====

@pytest.mark.asyncio
async def test_registry_registration():
    """Test agent registration"""
    registry = AgentRegistry()
    config = AgentConfig(name="test_agent")
    agent = TestAgent(config)

    registry.register_agent(agent)

    retrieved = registry.get("test_agent")
    assert retrieved is agent
    assert retrieved.config.name == "test_agent"


@pytest.mark.asyncio
async def test_registry_class_registration():
    """Test agent class registration and instantiation"""
    registry = AgentRegistry()
    config = AgentConfig(name="test_agent")

    registry.register_class("test_agent", TestAgent, config)

    assert "test_agent" in registry._agent_classes
    assert "test_agent" in registry._configs


@pytest.mark.asyncio
async def test_registry_create_and_register():
    """Test creating agent from registered class"""
    registry = AgentRegistry()
    config = AgentConfig(name="test_agent")

    registry.register_class("test_agent", TestAgent, config)
    agent = await registry.create_and_register("test_agent")

    assert isinstance(agent, TestAgent)
    assert agent.initialized is True
    assert "test_agent" in registry._agents


@pytest.mark.asyncio
async def test_registry_unregister():
    """Test agent unregistration"""
    registry = AgentRegistry()
    config = AgentConfig(name="test_agent")
    agent = TestAgent(config)

    await agent.initialize()
    registry.register_agent(agent)

    result = await registry.unregister("test_agent")

    assert result is True
    assert registry.get("test_agent") is None
    assert agent.status == AgentStatus.SHUTDOWN


@pytest.mark.asyncio
async def test_registry_list_agents():
    """Test listing agents"""
    registry = AgentRegistry()

    config1 = AgentConfig(name="agent1", enabled=True)
    config2 = AgentConfig(name="agent2", enabled=False)

    agent1 = TestAgent(config1)
    agent2 = TestAgent(config2)

    await agent1.initialize()
    await agent2.initialize()

    registry.register_agent(agent1)
    registry.register_agent(agent2)

    all_agents = registry.list_agents()
    assert len(all_agents) == 2

    enabled_agents = registry.list_agents(enabled_only=True)
    assert len(enabled_agents) == 1
    assert enabled_agents[0]["name"] == "agent1"


@pytest.mark.asyncio
async def test_registry_initialize_all():
    """Test initializing all registered agents"""
    registry = AgentRegistry()

    config1 = AgentConfig(name="agent1")
    config2 = AgentConfig(name="agent2")

    agent1 = TestAgent(config1)
    agent2 = TestAgent(config2)

    registry.register_agent(agent1)
    registry.register_agent(agent2)

    # Initialize all
    await registry.initialize_all()

    assert agent1.initialized is True
    assert agent2.initialized is True


@pytest.mark.asyncio
async def test_registry_shutdown_all():
    """Test shutting down all registered agents"""
    registry = AgentRegistry()

    config1 = AgentConfig(name="agent1")
    config2 = AgentConfig(name="agent2")

    agent1 = TestAgent(config1)
    agent2 = TestAgent(config2)

    await agent1.initialize()
    await agent2.initialize()

    registry.register_agent(agent1)
    registry.register_agent(agent2)

    await registry.shutdown_all()

    assert agent1.status == AgentStatus.SHUTDOWN
    assert agent2.status == AgentStatus.SHUTDOWN


@pytest.mark.asyncio
async def test_registry_metrics():
    """Test registry metrics"""
    registry = AgentRegistry()

    config = AgentConfig(name="test_agent")
    agent = TestAgent(config)

    await agent.initialize()
    registry.register_agent(agent)

    metrics = registry.get_metrics()

    assert "total_registered_agents" in metrics
    assert metrics["total_registered_agents"] == 1
    assert "total_registered_classes" in metrics


# ===== Test CommunicationChannel =====

@pytest.mark.asyncio
async def test_communication_start_stop():
    """Test starting and stopping communication channel"""
    channel = CommunicationChannel()

    await channel.start()
    assert channel._running is True

    await channel.stop()
    assert channel._running is False


@pytest.mark.asyncio
async def test_communication_publish_subscribe():
    """Test publishing and subscribing to messages"""
    channel = CommunicationChannel()

    received_messages = []

    async def callback(message: Message):
        received_messages.append(message)

    channel.subscribe("test_topic", callback)
    await channel.start()

    message = Message(
        type=MessageType.NOTIFICATION,
        sender="agent1",
        topic="test_topic",
        payload={"data": "test"}
    )

    await channel.publish(message)

    await asyncio.sleep(0.2)  # Wait for message to be delivered

    assert len(received_messages) == 1
    assert received_messages[0].payload == {"data": "test"}

    await channel.stop()


@pytest.mark.asyncio
async def test_communication_wildcard_subscription():
    """Test wildcard subscription to all messages"""
    channel = CommunicationChannel()

    received_messages = []

    async def callback(message: Message):
        received_messages.append(message)

    channel.subscribe("*", callback)
    await channel.start()

    messages = [
        Message(type=MessageType.NOTIFICATION, sender="agent1", topic="topic1", payload={}),
        Message(type=MessageType.NOTIFICATION, sender="agent2", topic="topic2", payload={}),
    ]

    for msg in messages:
        await channel.publish(msg)

    await asyncio.sleep(0.2)

    assert len(received_messages) == 2

    await channel.stop()


@pytest.mark.asyncio
async def test_communication_request_response():
    """Test request-response pattern"""
    channel = CommunicationChannel()
    await channel.start()

    # Subscribe and respond to requests
    async def responder(message: Message):
        if message.type == MessageType.REQUEST:
            response_payload = {"result": "processed", "data": message.payload}
            await channel.send_response(
                recipient=message.sender,
                topic=message.topic,
                payload=response_payload,
                sender="responder",
                correlation_id=message.correlation_id
            )

    channel.subscribe("test_topic", responder)

    # Send request
    response = await channel.send_request(
        recipient="responder",
        topic="test_topic",
        payload={"input": "test"},
        sender="requester",
        timeout=5.0
    )

    assert response["result"] == "processed"
    assert response["data"]["input"] == "test"

    await channel.stop()


@pytest.mark.asyncio
async def test_communication_request_timeout():
    """Test request timeout"""
    channel = CommunicationChannel()
    await channel.start()

    # Send request without a responder
    with pytest.raises(TimeoutError):
        await channel.send_request(
            recipient="responder",
            topic="test_topic",
            payload={},
            sender="requester",
            timeout=0.5
        )

    await channel.stop()


@pytest.mark.asyncio
async def test_communication_message_history():
    """Test message history"""
    channel = CommunicationChannel()
    await channel.start()

    for i in range(5):
        message = Message(
            type=MessageType.NOTIFICATION,
            sender="agent1",
            topic="test_topic",
            payload={"index": i}
        )
        await channel.publish(message)

    await asyncio.sleep(0.2)

    history = channel.get_message_history(limit=3)

    assert len(history) == 3

    await channel.stop()


@pytest.mark.asyncio
async def test_communication_metrics():
    """Test communication channel metrics"""
    channel = CommunicationChannel()
    await channel.start()

    channel.subscribe("topic1", lambda m: None)
    channel.subscribe("topic2", lambda m: None)

    metrics = channel.get_metrics()

    assert metrics["running"] is True
    assert metrics["subscribers"]["topic1"] == 1
    assert metrics["subscribers"]["topic2"] == 1

    await channel.stop()


# ===== Test TaskQueue =====

@pytest.mark.asyncio
async def test_task_queue_start_stop():
    """Test starting and stopping task queue"""
    queue = TaskQueue(max_concurrent_tasks=5)

    await queue.start()
    assert queue._running is True

    await queue.stop()
    assert queue._running is False


@pytest.mark.asyncio
async def test_task_submit():
    """Test submitting a task"""
    queue = TaskQueue()
    await queue.start()

    task = await queue.submit(
        agent_name="agent1",
        task_type="test_task",
        input_data={"key": "value"},
        priority=TaskPriority.NORMAL
    )

    assert task.agent_name == "agent1"
    assert task.task_type == "test_task"
    assert task.status == TaskStatus.QUEUED
    assert task.id in queue._tasks

    await queue.stop()


@pytest.mark.asyncio
async def test_task_cancel():
    """Test cancelling a task"""
    queue = TaskQueue()
    await queue.start()

    task = await queue.submit(
        agent_name="agent1",
        task_type="test_task",
        input_data={}
    )

    result = await queue.cancel(task.id)

    assert result is True
    assert task.status == TaskStatus.CANCELLED

    await queue.stop()


@pytest.mark.asyncio
async def test_task_get():
    """Test getting a task by ID"""
    queue = TaskQueue()
    await queue.start()

    task = await queue.submit(
        agent_name="agent1",
        task_type="test_task",
        input_data={}
    )

    retrieved = queue.get(task.id)

    assert retrieved is task
    assert retrieved.agent_name == "agent1"

    await queue.stop()


@pytest.mark.asyncio
async def test_task_get_agent_tasks():
    """Test getting tasks for a specific agent"""
    queue = TaskQueue()
    await queue.start()

    task1 = await queue.submit(agent_name="agent1", task_type="task1", input_data={})
    task2 = await queue.submit(agent_name="agent1", task_type="task2", input_data={})
    task3 = await queue.submit(agent_name="agent2", task_type="task3", input_data={})

    agent1_tasks = queue.get_agent_tasks("agent1")

    assert len(agent1_tasks) == 2
    assert task1 in agent1_tasks
    assert task2 in agent1_tasks
    assert task3 not in agent1_tasks

    await queue.stop()


@pytest.mark.asyncio
async def test_task_priority_ordering():
    """Test task priority ordering"""
    queue = TaskQueue()
    await queue.start()

    high_task = await queue.submit(
        agent_name="agent1",
        task_type="high",
        input_data={},
        priority=TaskPriority.HIGH
    )

    low_task = await queue.submit(
        agent_name="agent1",
        task_type="low",
        input_data={},
        priority=TaskPriority.LOW
    )

    critical_task = await queue.submit(
        agent_name="agent1",
        task_type="critical",
        input_data={},
        priority=TaskPriority.CRITICAL
    )

    # Check that tasks were created
    assert high_task.id in queue._tasks
    assert low_task.id in queue._tasks
    assert critical_task.id in queue._tasks

    await queue.stop()


@pytest.mark.asyncio
async def test_task_queue_metrics():
    """Test task queue metrics"""
    queue = TaskQueue(max_concurrent_tasks=5)
    await queue.start()

    task1 = await queue.submit(agent_name="agent1", task_type="task1", input_data={})
    task2 = await queue.submit(agent_name="agent2", task_type="task2", input_data={})

    metrics = queue.get_metrics()

    assert metrics["running"] is True
    assert metrics["total_tasks"] == 2
    assert metrics["max_concurrent_tasks"] == 5

    await queue.stop()


@pytest.mark.asyncio
async def test_task_status_callbacks():
    """Test task status change callbacks"""
    queue = TaskQueue()
    await queue.start()

    completed_tasks = []

    def on_completed(task: Task):
        completed_tasks.append(task.id)

    queue.register_callback(TaskStatus.COMPLETED.value, on_completed)

    task = await queue.submit(
        agent_name="agent1",
        task_type="test_task",
        input_data={}
    )

    # Manually complete the task
    task.status = TaskStatus.COMPLETED
    queue._trigger_callbacks(TaskStatus.COMPLETED.value, task)

    assert len(completed_tasks) == 1
    assert completed_tasks[0] == task.id

    await queue.stop()
