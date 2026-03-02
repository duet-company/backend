"""
Agent Communication Channel

Provides messaging and communication between agents.
"""

import logging
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
import json

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Message types for agent communication"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class Message(BaseModel):
    """Message between agents"""
    id: str = Field(default_factory=lambda: f"msg_{datetime.utcnow().timestamp()}")
    type: MessageType = Field(..., description="Message type")
    sender: str = Field(..., description="Sender agent name")
    recipient: Optional[str] = Field(None, description="Recipient agent name (None for broadcast)")
    topic: str = Field(..., description="Message topic")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Message payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for request-response")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "request",
                "sender": "query_agent",
                "recipient": "design_agent",
                "topic": "validate_schema",
                "payload": {"schema": "SELECT * FROM users"},
                "correlation_id": "req_123456"
            }
        }


class CommunicationChannel:
    """
    Communication channel for agent messaging.

    Supports point-to-point messaging, broadcasting, and pub/sub patterns.
    """

    def __init__(self):
        self.logger = logging.getLogger("agents.communication")
        self._subscribers: Dict[str, List[Callable]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._response_handlers: Dict[str, asyncio.Future] = {}
        self._running: bool = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._message_history: List[Message] = []
        self._max_history: int = 1000

    async def start(self) -> None:
        """Start the communication channel consumer"""
        if self._running:
            self.logger.warning("Communication channel already running")
            return

        self.logger.info("Starting communication channel")
        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_messages())

    async def stop(self) -> None:
        """Stop the communication channel consumer"""
        if not self._running:
            return

        self.logger.info("Stopping communication channel")
        self._running = False

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending response handlers
        for correlation_id, future in self._response_handlers.items():
            if not future.done():
                future.set_exception(RuntimeError("Communication channel stopped"))

    async def _consume_messages(self) -> None:
        """Consume messages from the queue and deliver to subscribers"""
        self.logger.debug("Message consumer started")

        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )

                await self._deliver_message(message)

                # Store in history
                self._message_history.append(message)
                if len(self._message_history) > self._max_history:
                    self._message_history.pop(0)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error consuming message: {e}")

        self.logger.debug("Message consumer stopped")

    async def _deliver_message(self, message: Message) -> None:
        """
        Deliver a message to subscribers.

        Args:
            message: Message to deliver
        """
        topic = message.topic

        # Deliver to topic subscribers
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    self.logger.error(
                        f"Error delivering message to subscriber for topic '{topic}': {e}"
                    )

        # Deliver to wildcard subscribers (topic="*")
        if "*" in self._subscribers:
            for callback in self._subscribers["*"]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    self.logger.error(f"Error delivering message to wildcard subscriber: {e}")

    def subscribe(self, topic: str, callback: Callable[[Message], Awaitable[None]]) -> None:
        """
        Subscribe to a topic.

        Args:
            topic: Topic to subscribe to (use "*" for all messages)
            callback: Callback function to handle messages
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []

        self._subscribers[topic].append(callback)
        self.logger.info(f"Subscribed to topic: {topic}")

    def unsubscribe(self, topic: str, callback: Callable[[Message], Awaitable[None]]) -> bool:
        """
        Unsubscribe from a topic.

        Args:
            topic: Topic to unsubscribe from
            callback: Callback function to remove

        Returns:
            True if callback was removed, False if not found
        """
        if topic not in self._subscribers:
            return False

        try:
            self._subscribers[topic].remove(callback)
            self.logger.info(f"Unsubscribed from topic: {topic}")

            if not self._subscribers[topic]:
                del self._subscribers[topic]

            return True
        except ValueError:
            return False

    async def publish(self, message: Message) -> None:
        """
        Publish a message to the channel.

        Args:
            message: Message to publish
        """
        self.logger.debug(f"Publishing message: {message.id} ({message.type})")
        await self._message_queue.put(message)

    async def send_request(
        self,
        recipient: str,
        topic: str,
        payload: Dict[str, Any],
        sender: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Send a request message and wait for response.

        Args:
            recipient: Recipient agent name
            topic: Message topic
            payload: Message payload
            sender: Sender agent name
            timeout: Timeout in seconds

        Returns:
            Response payload

        Raises:
            TimeoutError: If no response received within timeout
        """
        correlation_id = f"req_{datetime.utcnow().timestamp()}_{sender}"

        # Create request message
        message = Message(
            type=MessageType.REQUEST,
            sender=sender,
            recipient=recipient,
            topic=topic,
            payload=payload,
            correlation_id=correlation_id
        )

        # Create future for response
        future = asyncio.Future()
        self._response_handlers[correlation_id] = future

        # Publish request
        await self.publish(message)

        try:
            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self.logger.warning(
                f"Request timeout: {topic} -> {recipient} (correlation_id={correlation_id})"
            )
            raise TimeoutError(f"Request to {recipient} timed out after {timeout}s")
        finally:
            # Clean up response handler
            self._response_handlers.pop(correlation_id, None)

    async def send_response(
        self,
        recipient: str,
        topic: str,
        payload: Dict[str, Any],
        sender: str,
        correlation_id: str
    ) -> None:
        """
        Send a response message.

        Args:
            recipient: Recipient agent name
            topic: Message topic
            payload: Message payload
            sender: Sender agent name
            correlation_id: Correlation ID from original request
        """
        message = Message(
            type=MessageType.RESPONSE,
            sender=sender,
            recipient=recipient,
            topic=topic,
            payload=payload,
            correlation_id=correlation_id
        )

        await self.publish(message)

    def handle_response(self, message: Message) -> bool:
        """
        Handle a response message.

        Args:
            message: Response message

        Returns:
            True if response was handled, False if no handler found
        """
        if message.type != MessageType.RESPONSE or not message.correlation_id:
            return False

        correlation_id = message.correlation_id

        if correlation_id not in self._response_handlers:
            self.logger.warning(
                f"No handler for correlation_id: {correlation_id}"
            )
            return False

        future = self._response_handlers[correlation_id]

        if future.done():
            return False

        # Check if response contains an error
        if message.payload.get("error"):
            future.set_exception(RuntimeError(message.payload["error"]))
        else:
            future.set_result(message.payload)

        return True

    def get_message_history(
        self,
        limit: Optional[int] = None,
        topic: Optional[str] = None,
        sender: Optional[str] = None
    ) -> List[Message]:
        """
        Get message history with optional filtering.

        Args:
            limit: Maximum number of messages to return
            topic: Filter by topic
            sender: Filter by sender

        Returns:
            List of messages
        """
        messages = self._message_history

        if topic:
            messages = [m for m in messages if m.topic == topic]

        if sender:
            messages = [m for m in messages if m.sender == sender]

        messages = list(reversed(messages))  # Most recent first

        if limit:
            messages = messages[:limit]

        return messages

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get communication channel metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "running": self._running,
            "queue_size": self._message_queue.qsize(),
            "subscribers": {
                topic: len(callbacks)
                for topic, callbacks in self._subscribers.items()
            },
            "pending_response_handlers": len(self._response_handlers),
            "message_history_size": len(self._message_history),
        }

    def __repr__(self) -> str:
        return (
            f"CommunicationChannel("
            f"running={self._running}, "
            f"subscribers={len(self._subscribers)}, "
            f"queue_size={self._message_queue.qsize()}"
            f")"
        )
