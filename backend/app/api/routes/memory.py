"""
Simple memory API routes - chat history only.

Removes complex long-term memory with embeddings - just basic chat history.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, ChatMessage

router = APIRouter(prefix="/memory", tags=["memory"])


# Request/Response models
class ChatMessageResponse(BaseModel):
    """Chat message response."""
    id: str
    role: str
    content: str
    created_at: str


class ChatHistoryResponse(BaseModel):
    """Chat history response."""
    session_id: str
    messages: List[ChatMessageResponse]


class SaveMessageRequest(BaseModel):
    """Request to save a chat message."""
    session_id: UUID
    role: str
    content: str


class SaveMessageResponse(BaseModel):
    """Response from saving a message."""
    id: str
    message: str


# Routes

@router.get("/chat/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: UUID,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat history for a session.

    Returns messages in chronological order.
    """
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .where(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()

    return ChatHistoryResponse(
        session_id=str(session_id),
        messages=[
            ChatMessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat()
            )
            for m in messages
        ]
    )


@router.post("/chat", response_model=SaveMessageResponse)
async def save_chat_message(
    request: SaveMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Save a chat message to history."""
    message = ChatMessage(
        session_id=request.session_id,
        user_id=current_user.id,
        role=request.role,
        content=request.content
    )
    db.add(message)
    await db.flush()

    return SaveMessageResponse(
        id=str(message.id),
        message="Saved"
    )


@router.delete("/chat/{session_id}")
async def clear_chat_history(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Clear chat history for a session."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .where(ChatMessage.user_id == current_user.id)
    )
    messages = result.scalars().all()
    count = len(messages)

    for m in messages:
        await db.delete(m)
    await db.flush()

    return {"deleted": count}