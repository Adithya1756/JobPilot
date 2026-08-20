"""
SQLAlchemy models for JobPilot.
Mirrors the schema from the project specification.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Enum, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.core.database import Base
import enum


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """User account - supports multi-tenant data isolation."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255))
    role = Column(String(50), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    documents = relationship("SourceDocument", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    style_memories = relationship("StyleMemory", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


class DocType(str, enum.Enum):
    RESUME = "resume"
    PROJECT = "project"
    COVER_LETTER = "cover_letter"
    REVIEW = "review"
    OTHER = "other"


class SourceDocument(Base):
    """Raw uploaded files (resumes, project writeups, past cover letters)."""
    __tablename__ = "source_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    doc_type = Column(String(50), nullable=False)  # resume, project, cover_letter, review, other
    filename = Column(String(255), nullable=False)
    s3_url = Column(String(500))  # URL to file in S3/Supabase Storage
    raw_text = Column(Text)  # Extracted text content
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="documents")
    chunks = relationship("Chunk", back_populates="source_document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SourceDocument {self.filename}>"


class Chunk(Base):
    """
    The RAG unit - each chunk is one retrievable piece of the user's career history.
    Includes both embedding vector and tsvector for hybrid search.
    """
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # OpenAI text-embedding-3-small dimensions
    tsv = Column(Text)  # tsvector for full-text search (populated via trigger)
    chunk_metadata = Column("metadata", JSONB)  # {section: "experience", company: "X", dates: "..."}
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    source_document = relationship("SourceDocument", back_populates="chunks")

    # Note: We'll create the GIN index on tsv via Alembic migration
    # Note: We'll create the vector index via Alembic migration

    def __repr__(self):
        return f"<Chunk {self.id} from {self.source_document_id}>"


class Job(Base):
    """Job descriptions the user has saved."""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    role_title = Column(String(255), nullable=False)
    job_description = Column(Text, nullable=False)
    source_url = Column(String(500))  # Link to original posting
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="jobs")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job {self.role_title} at {self.company_name}>"


class ApplicationStatus(str, enum.Enum):
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"


class Application(Base):
    """Application tracker entity - Kanban-style status tracking."""
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="saved")  # saved, applied, interview, offer, rejected
    applied_at = Column(DateTime)
    follow_up_date = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    drafts = relationship("GeneratedDraft", back_populates="application", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Application {self.job_id} - {self.status}>"


class DraftType(str, enum.Enum):
    COVER_LETTER = "cover_letter"
    QA_ANSWER = "qa_answer"
    FOLLOW_UP_EMAIL = "follow_up_email"


class GeneratedDraft(Base):
    """Cover letters, answers, and emails produced by the agent."""
    __tablename__ = "generated_drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    draft_type = Column(String(50), nullable=False)  # cover_letter, qa_answer, follow_up_email
    content = Column(Text, nullable=False)
    prompt_version = Column(String(50))  # Track which prompt template was used
    retrieved_chunk_ids = Column(JSONB)  # List of chunk UUIDs used - for traceability/eval
    user_edited_content = Column(Text)  # User's final edit - feeds long-term memory
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    application = relationship("Application", back_populates="drafts")

    def __repr__(self):
        return f"<GeneratedDraft {self.draft_type} for {self.application_id}>"


class ChatMessage(Base):
    """Short-term conversational memory per drafting session."""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, tool
    content = Column(Text, nullable=False)
    tool_calls = Column(JSONB)  # Store tool call details if role=assistant
    tool_call_id = Column(String(100))  # For tool role messages
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChatMessage {self.role} in session {self.session_id}>"


class StyleMemory(Base):
    """
    Long-term memory - learned preferences distilled from user edits.
    Retrieved during future drafts to maintain consistent style.
    """
    __tablename__ = "style_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    preference_text = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # Embedding of the preference
    source_draft_id = Column(UUID(as_uuid=True), ForeignKey("generated_drafts.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="style_memories")

    def __repr__(self):
        return f"<StyleMemory {self.id} for user {self.user_id}>"
