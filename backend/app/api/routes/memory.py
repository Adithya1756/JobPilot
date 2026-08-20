"""
Memory API routes.

Endpoints for:
- Chat history (short-term memory)
- Style preferences (long-term memory)
- Updating style from user edits
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, ChatMessage, StyleMemory, GeneratedDraft
from app.agent.memory import (
    ShortTermMemory,
    LongTermMemory,
    update_style_from_edit,
    build_style_context
)


router = APIRouter(prefix="/memory", tags=["memory"])


# Request/Response models

class ChatMessageResponse(BaseModel):
    """Chat message response."""
    id: str
    role: str
    content: str
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    created_at: str


class ChatHistoryResponse(BaseModel):
    """Chat history response."""
    session_id: str
    messages: List[ChatMessageResponse]


class StylePreferenceResponse(BaseModel):
    """Style preference response."""
    id: str
    preference_text: str
    source_draft_id: Optional[str] = None
    created_at: str


class StylePreferencesResponse(BaseModel):
    """List of style preferences."""
    preferences: List[StylePreferenceResponse]


class UpdateStyleRequest(BaseModel):
    """Request to update style from edit."""
    draft_id: UUID
    original_content: str
    edited_content: str


class UpdateStyleResponse(BaseModel):
    """Response from style update."""
    updated: bool
    preference_text: Optional[str] = None


class StyleContextRequest(BaseModel):
    """Request to get style context for a job."""
    job_description: str


class StyleContextResponse(BaseModel):
    """Style context response."""
    context: str


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
    memory = ShortTermMemory(db)
    history = await memory.get_history(session_id, current_user.id, limit)

    return ChatHistoryResponse(
        session_id=str(session_id),
        messages=[
            ChatMessageResponse(
                id=str(m.id) if hasattr(m, 'id') else "",
                role=m.role,
                content=m.content,
                tool_calls=m.tool_calls,
                tool_call_id=m.tool_call_id,
                created_at=""  # Not available in ChatHistoryEntry
            )
            for m in history
        ]
    )


@router.delete("/chat/{session_id}")
async def clear_chat_history(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clear chat history for a session.
    """
    memory = ShortTermMemory(db)
    count = await memory.clear_history(session_id, current_user.id)
    return {"deleted": count}


@router.get("/style", response_model=StylePreferencesResponse)
async def get_style_preferences(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all style preferences for the current user.

    Returns most recent first.
    """
    memory = LongTermMemory(db)
    preferences_text = await memory.get_all_preferences(current_user.id, limit)

    # We need to get full records to include IDs and timestamps
    result = await db.execute(
        select(StyleMemory)
        .where(StyleMemory.user_id == current_user.id)
        .order_by(StyleMemory.created_at.desc())
        .limit(limit)
    )
    preferences = result.scalars().all()

    return StylePreferencesResponse(
        preferences=[
            StylePreferenceResponse(
                id=str(p.id),
                preference_text=p.preference_text,
                source_draft_id=str(p.source_draft_id) if p.source_draft_id else None,
                created_at=p.created_at.isoformat()
            )
            for p in preferences
        ]
    )


@router.post("/style/update", response_model=UpdateStyleResponse)
async def update_style_preference(
    request: UpdateStyleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update long-term memory from a user edit.

    Call this when the user saves an edited draft.
    """
    updated = await update_style_from_edit(
        db=db,
        user_id=current_user.id,
        draft_id=request.draft_id,
        original_content=request.original_content,
        edited_content=request.edited_content
    )

    if updated:
        # Get the preference that was created
        memory = LongTermMemory(db)
        prefs = await memory.get_all_preferences(current_user.id, 1)
        return UpdateStyleResponse(
            updated=True,
            preference_text=prefs[0] if prefs else None
        )

    return UpdateStyleResponse(updated=False)


@router.post("/style/context", response_model=StyleContextResponse)
async def get_style_context(
    request: StyleContextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get relevant style context for a job description.

    Returns formatted style preferences to include in prompts.
    """
    context = await build_style_context(db, current_user.id, request.job_description)
    return StyleContextResponse(context=context)