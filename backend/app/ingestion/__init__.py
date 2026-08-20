"""
Ingestion package - document parsing, chunking, embedding, storage.
"""

from app.ingestion.parser import DocumentParser, parse_uploaded_file
from app.ingestion.chunker import ResumeChunker, chunk_document
from app.ingestion.embeddings import EmbeddingService, get_embedding_service
from app.ingestion.pipeline import IngestionPipeline, ingest_document

__all__ = [
    "DocumentParser",
    "parse_uploaded_file",
    "ResumeChunker",
    "chunk_document",
    "EmbeddingService",
    "get_embedding_service",
    "IngestionPipeline",
    "ingest_document",
]
