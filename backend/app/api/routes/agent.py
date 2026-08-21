"""
Agent API routes - simple chat and cover letter generation.

Uses RAG retrieval + Gemini LLM. No complex tools or agent loops.
"""

from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, Job, GeneratedDraft
from app.agent.cover_letter import generate_cover_letter
from app.agent.simple_agent import chat_with_agent
from sqlalchemy import select

router = APIRouter(prefix="/agent", tags=["agent"])


# Request/Response schemas
class DraftRequest(BaseModel):
    job_id: str


class DraftResponse(BaseModel):
    draft_id: str
    content: str
    retrieved_chunks: int
    chunk_ids: List[str]


class StreamProgress(BaseModel):
    step: str
    message: str
    data: Optional[dict] = None


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[dict]] = None
    job_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    retrieved_chunks: int
    context_used: List[str]


@router.post("/draft", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    request: DraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a cover letter draft for a job.

    Simple RAG flow:
    1. Retrieve relevant experience via hybrid search
    2. Generate cover letter with that context

    Returns the draft with traceability info.
    """
    try:
        job_uuid = UUID(request.job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job_id format"
        )

    # Verify job exists
    result = await db.execute(
        select(Job).where(Job.id == job_uuid, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    try:
        draft_result = await generate_cover_letter(
            db=db,
            job_id=job_uuid,
            user_id=current_user.id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating draft: {str(e)}"
        )

    return DraftResponse(
        draft_id=draft_result["draft_id"],
        content=draft_result["content"],
        retrieved_chunks=draft_result["retrieved_chunks"],
        chunk_ids=draft_result["chunk_ids"]
    )


@router.post("/draft/stream")
async def stream_draft(
    request: DraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Stream the draft generation process with progress updates.

    Uses Server-Sent Events (SSE) format.
    """
    try:
        job_uuid = UUID(request.job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job_id format"
        )

    # Verify job exists
    result = await db.execute(
        select(Job).where(Job.id == job_uuid, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    async def generate_stream():
        """Generator that yields SSE-formatted progress updates."""
        try:
            yield f"data: {json.dumps({'step': 'retrieve', 'message': 'Searching your experience...'})}\n\n"

            draft_result = await generate_cover_letter(
                db=db,
                job_id=job_uuid,
                user_id=current_user.id
            )

            yield f"data: {json.dumps({'step': 'generate', 'message': 'Generating cover letter...'})}\n\n"

            final_data = {
                'draft_id': draft_result['draft_id'],
                'content': draft_result['content'],
                'retrieved_chunk_ids': draft_result['chunk_ids']
            }
            yield f"data: {json.dumps({'step': 'complete', 'message': 'Done!', 'data': final_data})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/drafts/{draft_id}")
async def get_draft(
    draft_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a previously generated draft by ID."""
    result = await db.execute(
        select(GeneratedDraft).where(GeneratedDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found"
        )

    return {
        "id": str(draft.id),
        "draft_type": draft.draft_type,
        "content": draft.content,
        "retrieved_chunk_ids": draft.retrieved_chunk_ids,
        "user_edited_content": draft.user_edited_content,
        "created_at": draft.created_at.isoformat()
    }


@router.patch("/drafts/{draft_id}")
async def update_draft(
    draft_id: UUID,
    edited_content: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a draft with user edits.
    """
    result = await db.execute(
        select(GeneratedDraft).where(GeneratedDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found"
        )

    draft.user_edited_content = edited_content
    await db.flush()

    return {
        "id": str(draft.id),
        "message": "Draft updated."
    }


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Chat with the AI agent (simple RAG chat).

    Retrieves relevant experience from your documents and generates a response.
    """
    job_uuid = None
    if request.job_id:
        try:
            job_uuid = UUID(request.job_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job_id format"
            )

    try:
        result = await chat_with_agent(
            db=db,
            user_id=current_user.id,
            message=request.message,
            conversation_history=request.conversation_history,
            job_id=job_uuid
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in chat: {str(e)}"
        )

    return ChatResponse(
        response=result["response"],
        retrieved_chunks=result["retrieved_chunks"],
        context_used=result["context_used"]
    )