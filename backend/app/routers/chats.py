"""FastAPI router for chat/conversation endpoints.

Handles:
- Chat session CRUD (create, list, delete)
- Message retrieval
- Message sending with SSE streaming

All DynamoDB-backed endpoints are wrapped with error handling so that
ClientError / EndpointConnectionError return 503 with a user-friendly
message instead of unhandled 500s.
"""

import json
import logging
from uuid import UUID
from typing import Annotated, AsyncIterator

from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.repositories.chat_repo import ChatRepository
from app.repositories.project_repo import ProjectRepository
from app.services.chat_service import ChatService, ServiceUnavailableError
from app.db.base import get_db
from app.dependencies import get_chat_repo, get_chat_service
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.chat import (
    ChatCreate,
    ChatResponse,
    ChatListResponse,
    MessageListResponse,
    MessageResponse,
    MessageCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chats"])


def get_project_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> ProjectRepository:
    """Dependency for project repository."""
    return ProjectRepository(session)


# get_chat_repo and get_chat_service are imported from app.dependencies


@router.post(
    "/projects/{project_id}/chats",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
async def create_chat_session(
    project_id: UUID,
    chat_data: ChatCreate,
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repo)],
):
    """
    Create a new chat session within a project.
    
    - **project_id**: UUID of the parent project
    - **title**: Optional chat title (auto-generated from timestamp if omitted)
    
    Returns the created chat session.
    """
    # Verify project exists
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Create chat session
    try:
        chat = await chat_repo.create_chat_session(
            project_id=str(project_id),
            title=chat_data.title,
        )
    except (ClientError, EndpointConnectionError) as exc:
        logger.error("DynamoDB error creating chat session: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is temporarily unavailable. Please try again.",
        ) from exc

    return ChatResponse(**chat)


@router.get(
    "/projects/{project_id}/chats",
    response_model=ChatListResponse,
    summary="List chat sessions for a project",
)
async def list_chat_sessions(
    project_id: UUID,
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repo)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    last_updated_at: Annotated[str | None, Query()] = None,
):
    """
    List all chat sessions for a project, sorted by updated_at descending (newest first).
    
    - **project_id**: UUID of the project
    - **limit**: Maximum number of chats to return (default 50, max 100)
    - **last_updated_at**: For pagination - updated_at timestamp of last chat from previous page
    
    Returns paginated list of chat sessions.
    """
    # Verify project exists
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get chats
    try:
        chats = await chat_repo.list_chat_sessions(
            project_id=str(project_id),
            limit=limit,
            last_updated_at=last_updated_at,
        )
    except (ClientError, EndpointConnectionError) as exc:
        logger.error("DynamoDB error listing chats for project %s: %s", project_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is temporarily unavailable. Please try again.",
        ) from exc

    return ChatListResponse(
        items=[ChatResponse(**chat) for chat in chats],
        total=len(chats),
        limit=limit,
        offset=0,  # DynamoDB uses cursor pagination, not offset
    )


@router.get(
    "/chats/{chat_id}",
    response_model=ChatResponse,
    summary="Get a chat session",
)
async def get_chat_session(
    chat_id: str,
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
):
    """
    Get details of a specific chat session.
    
    - **chat_id**: UUID of the chat session
    
    Returns the chat session data.
    """
    chat = await chat_repo.get_chat_session(chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    return ChatResponse(**chat)


@router.delete(
    "/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
)
async def delete_chat_session(
    chat_id: str,
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
):
    """
    Delete a chat session and all its messages.
    
    - **chat_id**: UUID of the chat session to delete
    
    This is a cascade delete - all messages are removed from DynamoDB.
    """
    # Verify chat exists
    chat = await chat_repo.get_chat_session(chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Delete all messages first, then the session
    try:
        await chat_repo.delete_chat_messages(chat_id)
        await chat_repo.delete_chat_session(chat_id)
    except (ClientError, EndpointConnectionError) as exc:
        logger.error("DynamoDB error deleting chat %s: %s", chat_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is temporarily unavailable. Please try again.",
        ) from exc

    return None


@router.get(
    "/chats/{chat_id}/messages",
    response_model=MessageListResponse,
    summary="Get message history for a chat",
)
async def get_chat_messages(
    chat_id: str,
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    last_message_id: Annotated[str | None, Query()] = None,
):
    """
    Get message history for a chat session, sorted chronologically (oldest first).
    
    - **chat_id**: UUID of the chat session
    - **limit**: Maximum number of messages to return (default 100, max 200)
    - **last_message_id**: For pagination - message_id of last message from previous page
    
    Returns paginated list of messages.
    """
    # Verify chat exists
    chat = await chat_repo.get_chat_session(chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Get messages
    try:
        messages = await chat_repo.get_messages(
            chat_id=chat_id,
            limit=limit,
            last_message_id=last_message_id,
        )
    except (ClientError, EndpointConnectionError) as exc:
        logger.error("DynamoDB error fetching messages for chat %s: %s", chat_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is temporarily unavailable. Please try again.",
        ) from exc

    return MessageListResponse(
        items=[MessageResponse(**msg) for msg in messages],
        total=len(messages),
        limit=limit,
        offset=0,  # DynamoDB uses cursor pagination, not offset
    )

@router.post(
    "/chats/{chat_id}/messages",
    summary="Send a message and get streaming response",
)
async def send_message(
    chat_id: str,
    message_data: MessageCreate,
    request: Request,
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    """
    Send a message to a chat and receive streaming LLM response via SSE.
    
    - **chat_id**: UUID of the chat session
    - **message_data**: Message content and metadata
    
    Returns:
    - SSE stream with events: token, sources, done, error
    
    Event format:
    - `event: token\\ndata: {"content": "..."}\\n\\n`
    - `event: sources\\ndata: {"sources": [...]}\\n\\n`
    - `event: done\\ndata: {"message_id": "..."}\\n\\n`
    - `event: error\\ndata: {"error": "..."}\\n\\n`
    """
    # Verify chat exists
    chat = await chat_repo.get_chat_session(chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Get project_id from chat
    project_id = UUID(chat["project_id"])
    
    # SSE event generator
    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from chat service."""
        try:
            async for event in chat_service.process_user_message_stream(
                chat_id=chat_id,
                project_id=project_id,
                user_message=message_data.content,
            ):
                event_type = event.get("type", "message")

                # Format as SSE event
                if event_type == "token":
                    data = {"content": event["content"]}
                    yield f"event: token\ndata: {json.dumps(data)}\n\n"

                elif event_type == "sources":
                    data = {"sources": event["sources"]}
                    yield f"event: sources\ndata: {json.dumps(data)}\n\n"

                elif event_type == "done":
                    data = {"message_id": event["message_id"]}
                    yield f"event: done\ndata: {json.dumps(data)}\n\n"

                elif event_type == "error":
                    data = {"error": event["error"]}
                    yield f"event: error\ndata: {json.dumps(data)}\n\n"

        except Exception as exc:
            # The ChatService streaming path should never let exceptions
            # escape — this is a safety net that also logs the problem.
            logger.exception(
                "Unhandled error in SSE event_generator for chat %s", chat_id,
            )
            error_data = {"error": "An unexpected error occurred. Please try again."}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )