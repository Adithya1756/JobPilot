"""
Agent API routes - cover letter generation and drafting.

These endpoints orchestrate the RAG retrieval + LLM generation flow.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, Job, GeneratedDraft
from app.agent.drafting import generate_cover_letter, DraftResult
from app.agent.llm import get_llm_client
from sqlalchemy import select

router = APIRouter(prefix="/agent", tags=["agent"])


# Request/Response schemas
class DraftRequest(BaseModel):
    job_id: str
    draft_type: str = "cover_letter"
    include_critique: bool = False


class DraftResponse(BaseModel):
    draft_id: str
    content: str
    retrieved_chunk_ids: list[str]
    requirements: dict
    critique: Optional[dict] = None


class StreamProgress(BaseModel):
    step: str
    message: str
    data: Optional[dict] = None


@router.post("/draft", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    request: DraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a cover letter draft for a job.

    This endpoint:
    1. Extracts requirements from the job description
    2. Retrieves relevant experience via hybrid RAG
    3. Generates a tailored cover letter
    4. Optionally runs self-critique

    Returns the draft with traceability info (which chunks were used).
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
            user_id=current_user.id,
            include_critique=request.include_critique
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating draft: {str(e)}"
        )

    return DraftResponse(
        draft_id=draft_result.draft_id or "",
        content=draft_result.content,
        retrieved_chunk_ids=draft_result.retrieved_chunk_ids,
        requirements=draft_result.requirements,
        critique=draft_result.critique
    )


@router.post("/draft/stream")
async def stream_draft(
    request: DraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Stream the draft generation process with progress updates.

    This is useful for showing real-time progress in the UI:
    - "Analyzing job description..."
    - "Retrieving relevant experience..."
    - "Generating cover letter..."

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
            # Step 1: Extract requirements
            yield f"data: {json.dumps({'step': 'parse', 'message': 'Analyzing job description...'})}\n\n"

            # Step 2: Retrieve experience
            yield f"data: {json.dumps({'step': 'retrieve', 'message': 'Searching your experience...'})}\n\n"

            # Generate the draft
            draft_result = await generate_cover_letter(
                db=db,
                job_id=job_uuid,
                user_id=current_user.id,
                include_critique=request.include_critique
            )

            # Step 3: Generation complete
            yield f"data: {json.dumps({'step': 'generate', 'message': 'Generating cover letter...'})}\n\n"

            # Final result
            final_data = {
                'draft_id': draft_result.draft_id,
                'content': draft_result.content,
                'retrieved_chunk_ids': draft_result.retrieved_chunk_ids
            }
            yield f"data: {json.dumps({'step': 'complete', 'message': 'Done!', 'data': final_data})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

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

    This is important for the long-term memory system:
    - User edits are stored in user_edited_content
    - A background process extracts style preferences from edits
    - Future drafts can reference these learned preferences
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
        "message": "Draft updated. Style preferences will be learned from your edits."
    }
