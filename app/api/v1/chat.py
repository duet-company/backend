"""
Chat API - Natural language interface endpoints

Handles chat messages, conversation history, and streaming responses.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.core.database import get_db
from app.models.chat import Chat
from app.agents.query_agent import create_query_agent
from app.agents import registry

router = APIRouter()
logger = logging.getLogger(__name__)

# Global agent instances (will be initialized on startup)
_query_agent = None
_design_agent = None
_support_agent = None


async def get_query_agent():
    """Get or create the query agent instance."""
    global _query_agent
    if _query_agent is None:
        _query_agent = create_query_agent()
        await _query_agent.initialize()
    return _query_agent


async def get_design_agent():
    """Get or create the design agent instance."""
    global _design_agent
    if _design_agent is None:
        _design_agent = registry.get("design_agent")
        if _design_agent and hasattr(_design_agent, 'initialize'):
            await _design_agent.initialize()
    return _design_agent


async def get_support_agent():
    """Get or create the support agent instance."""
    global _support_agent
    if _support_agent is None:
        _support_agent = registry.get("support_agent")
        if _support_agent and hasattr(_support_agent, 'initialize'):
            await _support_agent.initialize()
    return _support_agent


async def detect_agent_intent(message: str) -> str:
    """
    Detect which agent should handle the message based on intent.

    Returns: 'query', 'design', 'support', or 'query' (default)
    """
    message_lower = message.lower()

    # Platform design intent keywords
    design_keywords = [
        'create platform', 'setup platform', 'design infrastructure',
        'deploy platform', 'kubernetes', 'database setup', 'infrastructure',
        'design agent', 'platform designer', 'setup data platform'
    ]

    # Support intent keywords
    support_keywords = [
        'help', 'support', 'how do i', 'how to', 'troubleshoot',
        'error', 'problem', 'issue', 'bug', 'not working'
    ]

    # Check design intent
    if any(keyword in message_lower for keyword in design_keywords):
        return 'design'

    # Check support intent
    if any(keyword in message_lower for keyword in support_keywords):
        return 'support'

    # Default to query agent
    return 'query'


# Pydantic models for request/response
class SendMessageRequest(BaseModel):
    """Request to send a message"""
    message: str = Field(..., description="User message", min_length=1)
    chat_id: Optional[int] = Field(None, description="Chat ID (null for new chat)")
    title: Optional[str] = Field(None, description="Title for new chat")
    agent_type: Optional[str] = Field(None, description="Agent type: 'query', 'design', 'support', or 'auto' (default)")


class SendMessageResponse(BaseModel):
    """Response to message send (non-streaming)"""
    chat_id: int
    message_id: str
    response: str
    timestamp: str
    query_result: Optional[Dict[str, Any]] = None


class ChatHistoryResponse(BaseModel):
    """Chat history response"""
    chats: List[Dict[str, Any]]
    total: int


class ChatDetailResponse(BaseModel):
    """Single chat detail response"""
    chat: Dict[str, Any]


class MessageSuggestion(BaseModel):
    """Message suggestion"""
    text: str
    icon: Optional[str] = None
    category: Optional[str] = None


class SuggestionsResponse(BaseModel):
    """Suggestions response"""
    suggestions: List[MessageSuggestion]


@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Send a message and get a response (non-streaming).

    **Authentication required**

    For streaming responses, use the /send-stream endpoint.
    """
    logger.info(f"User {current_user['id']} sending message: {request.message[:50]}...")

    user_id = current_user["id"]

    # Get or create chat
    if request.chat_id:
        chat = db.query(Chat).filter(
            Chat.id == request.chat_id,
            Chat.user_id == user_id,
            Chat.status == "active"
        ).first()

        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
    else:
        # Create new chat
        chat = Chat(
            user_id=user_id,
            title=request.title or request.message[:50] + "...",
            messages=[],
            context={},
            status="active"
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)

    # Add user message
    message_id = f"msg_{datetime.utcnow().timestamp()}"
    chat.add_message(
        role="user",
        content=request.message,
        metadata={"message_id": message_id}
    )

    try:
        # Determine which agent to use
        agent_type = request.agent_type or 'auto'
        if agent_type == 'auto':
            agent_type = await detect_agent_intent(request.message)

        logger.info(f"Routing to agent: {agent_type}")

        # Get the appropriate agent
        if agent_type == 'design':
            agent = await get_design_agent()
            if not agent:
                logger.warning("Design agent not available, falling back to query agent")
                agent = await get_query_agent()
                agent_type = 'query'
        elif agent_type == 'support':
            agent = await get_support_agent()
            if not agent:
                logger.warning("Support agent not available, falling back to query agent")
                agent = await get_query_agent()
                agent_type = 'query'
        else:
            agent = await get_query_agent()
            agent_type = 'query'

        response_text = ""
        query_result = None
        is_data_query = (agent_type == 'query')

        if agent_type == 'query':
            # Check if this looks like a data query
            is_data_query_check = any(keyword in request.message.lower() for keyword in [
                "show", "get", "what", "how many", "count", "list", "find", "search",
                "average", "sum", "total", "top", "bottom"
            ])

            if is_data_query_check:
                # Process as data query
                try:
                    result = await agent._on_process({
                        "query": request.message,
                        "user_id": user_id
                    })

                    # Format result as natural language
                    if result["rows"]:
                        response_text = f"Query executed successfully.\n\n{result['formatted_output']}\n\nGenerated SQL:\n```sql\n{result['generated_sql']}\n```"
                    else:
                        response_text = "No results found for your query."

                    query_result = result

                except Exception as e:
                    logger.error(f"Query failed: {e}")
                    response_text = f"I encountered an error while processing your query: {str(e)}"
            else:
                # General conversational response
                response_text = "I'm your AI Data Assistant! I can help you query your data using natural language. Try asking me to show, count, or analyze your data."

        elif agent_type == 'design':
            # Process with Platform Designer Agent
            try:
                result = await agent.process({
                    "action": "design",
                    "query": request.message,
                    "user_id": user_id
                })

                if result.get("success"):
                    response_text = f"Platform design processed successfully.\n\n{result.get('message', '')}"
                    query_result = result
                else:
                    response_text = f"Design agent response: {result.get('message', 'No specific message')}"

            except Exception as e:
                logger.error(f"Design agent error: {e}")
                response_text = f"I encountered an error with the design agent: {str(e)}"

        elif agent_type == 'support':
            # Process with Support Agent
            try:
                result = await agent.process({
                    "action": "support",
                    "query": request.message,
                    "user_id": user_id
                })

                response_text = result.get("response", "Support agent response received.")
                query_result = result

            except Exception as e:
                logger.error(f"Support agent error: {e}")
                response_text = f"I encountered an error with the support agent: {str(e)}"

        # Add assistant response
        chat.add_message(
            role="assistant",
            content=response_text,
            metadata={
                "query_result": query_result,
                "is_data_query": is_data_query,
                "agent_type": agent_type
            }
        )

        # Update context
        if query_result:
            chat.update_context("last_query", request.message)
            chat.update_context("last_sql", query_result.get("generated_sql"))

        db.commit()

        return SendMessageResponse(
            chat_id=chat.id,
            message_id=message_id,
            response=response_text,
            timestamp=datetime.utcnow().isoformat(),
            query_result=query_result
        )

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )


@router.post("/send-stream")
async def send_message_stream(
    request: SendMessageRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Send a message and get a streaming response.

    **Authentication required**

    Returns a Server-Sent Events (SSE) stream.
    """
    logger.info(f"User {current_user['id']} sending streaming message")

    user_id = current_user["id"]

    # Get or create chat
    if request.chat_id:
        chat = db.query(Chat).filter(
            Chat.id == request.chat_id,
            Chat.user_id == user_id,
            Chat.status == "active"
        ).first()

        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
    else:
        chat = Chat(
            user_id=user_id,
            title=request.title or request.message[:50] + "...",
            messages=[],
            context={},
            status="active"
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)

    # Add user message
    message_id = f"msg_{datetime.utcnow().timestamp()}"
    chat.add_message(
        role="user",
        content=request.message,
        metadata={"message_id": message_id}
    )
    db.commit()

    async def event_generator():
        """Generate SSE events for streaming response."""
        try:
            # Send chat ID first
            yield f"event: chat_id\ndata: {json.dumps({'chat_id': chat.id})}\n\n"

            # Send message ID
            yield f"event: message_id\ndata: {json.dumps({'message_id': message_id})}\n\n"

            # Determine which agent to use
            agent_type = request.agent_type or 'auto'
            if agent_type == 'auto':
                agent_type = await detect_agent_intent(request.message)

            logger.info(f"Streaming: Routing to agent: {agent_type}")

            # Get the appropriate agent
            if agent_type == 'design':
                agent = await get_design_agent()
                if not agent:
                    logger.warning("Design agent not available, falling back to query agent")
                    agent = await get_query_agent()
                    agent_type = 'query'
            elif agent_type == 'support':
                agent = await get_support_agent()
                if not agent:
                    logger.warning("Support agent not available, falling back to query agent")
                    agent = await get_query_agent()
                    agent_type = 'query'
            else:
                agent = await get_query_agent()
                agent_type = 'query'

            # Check if this is a data query (only for query agent)
            is_data_query = (agent_type == 'query') and any(
                keyword in request.message.lower() for keyword in [
                    "show", "get", "what", "how many", "count", "list", "find", "search",
                    "average", "sum", "total", "top", "bottom"
                ]
            )

            if agent_type == 'query' and is_data_query:
                # Send thinking status
                yield "event: status\ndata: {\"status\": \"thinking\", \"message\": \"Processing your query...\"}\n\n"

                # Process query
                try:
                    result = await agent._on_process({
                        "query": request.message,
                        "user_id": user_id
                    })

                    # Stream the response
                    response_parts = []
                    if result["rows"]:
                        response_parts.append("Query executed successfully.\n\n")
                        response_parts.append(result["formatted_output"])
                        response_parts.append("\n\nGenerated SQL:\n```sql\n")
                        response_parts.append(result["generated_sql"])
                        response_parts.append("\n```")
                    else:
                        response_parts.append("No results found for your query.")

                    # Stream each part
                    full_response = ""
                    for part in response_parts:
                        for char in part:
                            full_response += char
                            yield f"event: message\ndata: {json.dumps({'content': char})}\n\n"
                            await asyncio.sleep(0.01)  # Simulate typing

                    # Send final result
                    yield f"event: query_result\ndata: {json.dumps(result)}\n\n"

                    # Save assistant response
                    chat.add_message(
                        role="assistant",
                        content=full_response,
                        metadata={
                            "query_result": result,
                            "is_data_query": True,
                            "agent_type": "query"
                        }
                    )

                    # Update context
                    chat.update_context("last_query", request.message)
                    chat.update_context("last_sql", result.get("generated_sql"))

            elif agent_type == 'design':
                # Process with Platform Designer Agent
                yield "event: status\ndata: {\"status\": \"thinking\", \"message\": \"Processing platform design...\"}\n\n"

                try:
                    result = await agent.process({
                        "action": "design",
                        "query": request.message,
                        "user_id": user_id
                    })

                    # Format response
                    if result.get("success"):
                        response_parts = [
                            "Platform design processed successfully.\n\n",
                            result.get('message', ''),
                            "\n\n",
                            str(result.get('details', ''))
                        ]
                    else:
                        response_parts = [result.get('message', 'Design agent response received.')]

                    # Stream each part
                    full_response = ""
                    for part in response_parts:
                        for char in part:
                            full_response += char
                            yield f"event: message\ndata: {json.dumps({'content': char})}\n\n"
                            await asyncio.sleep(0.01)

                    # Save assistant response
                    chat.add_message(
                        role="assistant",
                        content=full_response,
                        metadata={
                            "query_result": result,
                            "is_data_query": False,
                            "agent_type": "design"
                        }
                    )

                    chat.update_context("last_design", request.message)

                except Exception as e:
                    error_msg = f"I encountered an error with the design agent: {str(e)}"
                    for char in error_msg:
                        yield f"event: message\ndata: {json.dumps({'content': char})}\n\n"
                        await asyncio.sleep(0.01)

                    chat.add_message(
                        role="assistant",
                        content=error_msg,
                        metadata={"error": True, "agent_type": "design"}
                    )

            elif agent_type == 'support':
                # Process with Support Agent
                yield "event: status\ndata: {\"status\": \"thinking\", \"message\": \"Getting support...\"}\n\n"

                try:
                    result = await agent.process({
                        "action": "support",
                        "query": request.message,
                        "user_id": user_id
                    })

                    response = result.get("response", "Support agent response received.")

                    # Stream response
                    full_response = ""
                    for char in response:
                        full_response += char
                        yield f"event: message\ndata: {json.dumps({'content': char})}\n\n"
                        await asyncio.sleep(0.01)

                    # Save assistant response
                    chat.add_message(
                        role="assistant",
                        content=full_response,
                        metadata={
                            "query_result": result,
                            "is_data_query": False,
                            "agent_type": "support"
                        }
                    )

                    chat.update_context("last_support", request.message)

                except Exception as e:
                    error_msg = f"I encountered an error with the support agent: {str(e)}"
                    for char in error_msg:
                        yield f"event: message\ndata: {json.dumps({'content': char})}\n\n"
                        await asyncio.sleep(0.01)

                    chat.add_message(
                        role="assistant",
                        content=error_msg,
                        metadata={"error": True, "agent_type": "support"}
                    )

            else:
                # General conversational response (query agent without data query)
                response = "I'm your AI Data Assistant! I can help you query your data using natural language. Try asking me to show, count, or analyze your data."
                for char in response:
                    yield f"event: message\ndata: {json.dumps({'content': char})}\n\n"
                    await asyncio.sleep(0.01)

                chat.add_message(
                    role="assistant",
                    content=response,
                    metadata={"is_data_query": False, "agent_type": "query"}
                )

                except Exception as e:
                    error_msg = f"I encountered an error: {str(e)}"
                    for char in error_msg:
                        yield f"event: message\ndata: {json.dumps({'content': char})}\n\n"
                        await asyncio.sleep(0.01)

                    chat.add_message(
                        role="assistant",
                        content=error_msg,
                        metadata={"error": True}
                    )
            else:
                # General conversational response
                response = "I'm your AI Data Assistant! I can help you query your data using natural language. Try asking me to show, count, or analyze your data."
                for char in response:
                    yield f"event: message\ndata: {json.dumps({'content': char})}\n\n"
                    await asyncio.sleep(0.01)

                chat.add_message(
                    role="assistant",
                    content=response,
                    metadata={"is_data_query": False}
                )

            # Save to database
            db.commit()

            # Send completion event
            yield "event: done\ndata: {}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get chat history for the current user.

    **Authentication required**

    Returns a list of active chats for the user.
    """
    logger.info(f"Fetching chat history for user {current_user['id']}")

    user_id = current_user["id"]

    # Get chats
    chats = db.query(Chat).filter(
        Chat.user_id == user_id,
        Chat.status == "active"
    ).order_by(Chat.updated_at.desc()).offset(skip).limit(limit).all()

    total = db.query(Chat).filter(
        Chat.user_id == user_id,
        Chat.status == "active"
    ).count()

    return ChatHistoryResponse(
        chats=[chat.to_dict() for chat in chats],
        total=total
    )


@router.get("/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: int,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific chat.

    **Authentication required**
    """
    logger.info(f"Fetching chat {chat_id} for user {current_user['id']}")

    user_id = current_user["id"]

    chat = db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == user_id,
        Chat.status == "active"
    ).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    return ChatDetailResponse(chat=chat.to_dict())


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: int,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a chat (soft delete).

    **Authentication required**
    """
    logger.info(f"Deleting chat {chat_id} for user {current_user['id']}")

    user_id = current_user["id"]

    chat = db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == user_id,
        Chat.status == "active"
    ).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Soft delete
    chat.status = "deleted"
    chat.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "success", "message": "Chat deleted"}


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions():
    """
    Get suggested prompts for the user.

    No authentication required for suggestions.
    """
    suggestions = [
        # Query Agent suggestions
        MessageSuggestion(
            text="Show me the top 10 records",
            icon="📊",
            category="query"
        ),
        MessageSuggestion(
            text="How many rows are in the data?",
            icon="🔢",
            category="query"
        ),
        MessageSuggestion(
            text="What's the average value of the numeric columns?",
            icon="📈",
            category="query"
        ),
        MessageSuggestion(
            text="Find records with missing values",
            icon="🔍",
            category="query"
        ),
        # Design Agent suggestions
        MessageSuggestion(
            text="Create a new data platform for analytics",
            icon="🏗️",
            category="design"
        ),
        MessageSuggestion(
            text="Setup ClickHouse database cluster",
            icon="🗄️",
            category="design"
        ),
        MessageSuggestion(
            text="Design a Kubernetes infrastructure for data pipeline",
            icon="☸️",
            category="design"
        ),
        # Support Agent suggestions
        MessageSuggestion(
            text="How do I connect to my database?",
            icon="❓",
            category="support"
        ),
        MessageSuggestion(
            text="Troubleshoot query performance issues",
            icon="🔧",
            category="support"
        ),
        # General
        MessageSuggestion(
            text="Show me data from the last 7 days",
            icon="📅",
            category="query"
        ),
        MessageSuggestion(
            text="Group and count by category",
            icon="📋",
            category="query"
        )
    ]

    return SuggestionsResponse(suggestions=suggestions)


@router.post("/{chat_id}/feedback")
async def submit_feedback(
    chat_id: int,
    feedback: Dict[str, Any],
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback on a chat response.

    **Authentication required**

    Request body should include:
        - message_id: ID of the message
        - rating: 1-5 rating
        - comment: Optional comment
    """
    logger.info(f"Submitting feedback for chat {chat_id}")

    user_id = current_user["id"]

    chat = db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == user_id,
        Chat.status == "active"
    ).first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Find the message and add feedback
    message_id = feedback.get("message_id")
    rating = feedback.get("rating")
    comment = feedback.get("comment")

    if not message_id or not rating:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message_id and rating are required"
        )

    # Add feedback to message metadata
    for msg in chat.messages:
        if msg.get("metadata", {}).get("message_id") == message_id:
            msg["metadata"]["feedback"] = {
                "rating": rating,
                "comment": comment,
                "timestamp": datetime.utcnow().isoformat()
            }
            break

    chat.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "success", "message": "Feedback recorded"}
