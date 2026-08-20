"""
Ingestion pipeline - orchestrates the full document ingestion flow.

Flow:
1. Parse document (extract text)
2. Chunk text (semantic chunking)
3. Generate embeddings
4. Store in database

This is the main entry point for document ingestion, called by the upload endpoint.
"""

from typing import List, Optional
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.user import SourceDocument, Chunk, DocType
from app.ingestion.parser import parse_uploaded_file
from app.ingestion.chunker import chunk_document, Chunk as ChunkResult
from app.ingestion.embeddings import get_embedding_service

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Orchestrates document ingestion: parse → chunk → embed → store.

    Each step is separated for testability and clarity.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = get_embedding_service()

    async def ingest(
        self,
        user_id: UUID,
        file_content: bytes,
        filename: str,
        doc_type: str,
        s3_url: Optional[str] = None
    ) -> SourceDocument:
        """
        Full ingestion pipeline for an uploaded document.

        Args:
            user_id: UUID of the user uploading
            file_content: Raw bytes of the uploaded file
            filename: Original filename
            doc_type: Type of document (resume, project, cover_letter, etc.)
            s3_url: Optional URL if file was stored in S3

        Returns:
            SourceDocument with chunks populated
        """
        logger.info(f"Starting ingestion for {filename} (type: {doc_type})")

        # Step 1: Parse document
        raw_text = parse_uploaded_file(file_content, filename)
        logger.info(f"Parsed {len(raw_text)} characters from {filename}")

        # Step 2: Create source document record
        source_doc = SourceDocument(
            user_id=user_id,
            doc_type=doc_type,
            filename=filename,
            s3_url=s3_url,
            raw_text=raw_text
        )
        self.db.add(source_doc)
        await self.db.flush()  # Get the ID

        # Step 3: Chunk the text
        chunk_results = chunk_document(raw_text, doc_type)
        logger.info(f"Created {len(chunk_results)} chunks")

        # Step 4: Generate embeddings for all chunks
        chunk_texts = [c.content for c in chunk_results]
        embeddings = await self.embedding_service.embed_batch(chunk_texts)

        # Step 5: Store chunks in database
        chunks_to_create = []
        for chunk_result, embedding in zip(chunk_results, embeddings):
            chunk = Chunk(
                source_document_id=source_doc.id,
                user_id=user_id,
                content=chunk_result.content,
                embedding=embedding,
                chunk_metadata=chunk_result.metadata
            )
            chunks_to_create.append(chunk)

        self.db.add_all(chunks_to_create)

        logger.info(f"Ingestion complete for {filename}")
        return source_doc

    async def deduplicate_chunks(self, user_id: UUID, similarity_threshold: float = 0.95) -> int:
        """
        Remove near-duplicate chunks for a user.

        This handles cases where the same content appears in multiple documents
        (e.g., a project described in both resume and a project writeup).

        Uses cosine similarity to detect duplicates.

        Args:
            user_id: User to deduplicate for
            similarity_threshold: Chunks above this similarity are considered duplicates

        Returns:
            Number of chunks removed
        """
        # This would require a more complex query with vector operations
        # For now, we'll skip this in the initial implementation
        # TODO: Implement using pgvector similarity search
        logger.warning("Deduplication not yet implemented")
        return 0


async def ingest_document(
    db: AsyncSession,
    user_id: UUID,
    file_content: bytes,
    filename: str,
    doc_type: str,
    s3_url: Optional[str] = None
) -> SourceDocument:
    """
    Convenience function to run the ingestion pipeline.

    This is the main entry point called from API routes.
    """
    pipeline = IngestionPipeline(db)
    return await pipeline.ingest(
        user_id=user_id,
        file_content=file_content,
        filename=filename,
        doc_type=doc_type,
        s3_url=s3_url
    )
