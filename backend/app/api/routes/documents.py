"""
Document upload routes.

Handles file uploads and triggers the ingestion pipeline.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, SourceDocument
from app.ingestion.pipeline import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


# Response schemas
class DocumentResponse(BaseModel):
    id: str
    doc_type: str
    filename: str
    uploaded_at: str

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]


# Allowed document types
ALLOWED_DOC_TYPES = ["resume", "project", "cover_letter", "review", "other"]
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document (resume, project writeup, etc.) and trigger ingestion.

    The file is parsed, chunked, and embedded for later retrieval.

    Args:
        file: Uploaded file (PDF, DOCX, or TXT)
        doc_type: Type of document (resume, project, cover_letter, review, other)

    Returns:
        Document metadata including ID
    """
    # Validate doc_type
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid doc_type. Must be one of: {', '.join(ALLOWED_DOC_TYPES)}"
        )

    # Validate file extension
    filename = file.filename or "unknown"
    from pathlib import Path
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    file_content = await file.read()

    # Validate file size
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)} MB"
        )

    # Run ingestion pipeline
    try:
        source_doc = await ingest_document(
            db=db,
            user_id=current_user.id,
            file_content=file_content,
            filename=filename,
            doc_type=doc_type
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )

    return DocumentResponse(
        id=str(source_doc.id),
        doc_type=source_doc.doc_type,
        filename=source_doc.filename,
        uploaded_at=source_doc.uploaded_at.isoformat()
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    doc_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all documents for the current user.

    Optionally filter by document type.
    """
    query = select(SourceDocument).where(
        SourceDocument.user_id == current_user.id
    ).order_by(SourceDocument.uploaded_at.desc())

    if doc_type:
        query = query.where(SourceDocument.doc_type == doc_type)

    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=str(doc.id),
                doc_type=doc.doc_type,
                filename=doc.filename,
                uploaded_at=doc.uploaded_at.isoformat()
            )
            for doc in documents
        ]
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a document and all its chunks.

    Ensures the document belongs to the current user.
    """
    result = await db.execute(
        select(SourceDocument).where(
            SourceDocument.id == document_id,
            SourceDocument.user_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    await db.delete(document)
    # Cascade deletes will remove chunks automatically
