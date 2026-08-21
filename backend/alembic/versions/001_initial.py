"""Initial schema with pgvector - simplified for Gemini free tier

Revision ID: 001_initial
Revises:
Create Date: 2026-08-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector


revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('role', sa.String(50), default='user'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # Source documents table
    op.create_table(
        'source_documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doc_type', sa.String(50), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('s3_url', sa.String(500)),
        sa.Column('raw_text', sa.Text),
        sa.Column('uploaded_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_source_documents_user_id', 'source_documents', ['user_id'])

    # Chunks table with vector column (768 dims for Gemini text-embedding-004)
    op.create_table(
        'chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('source_document_id', UUID(as_uuid=True), sa.ForeignKey('source_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', Vector(768)),
        sa.Column('tsv', sa.Text),
        sa.Column('metadata', JSONB),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_chunks_user_id', 'chunks', ['user_id'])

    # Create vector index for similarity search (HNSW)
    op.execute("""
        CREATE INDEX IF NOT EXISTS chunks_embedding_idx
        ON chunks
        USING hnsw (embedding vector_cosine_ops)
    """)

    # Create GIN index for full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS chunks_tsv_idx
        ON chunks
        USING gin (to_tsvector('english', content))
    """)

    # Trigger to auto-populate tsv column on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION chunks_tsv_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.tsv := to_tsvector('english', COALESCE(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER chunks_tsv_update
        BEFORE INSERT OR UPDATE ON chunks
        FOR EACH ROW EXECUTE FUNCTION chunks_tsv_trigger()
    """)

    # Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('role_title', sa.String(255), nullable=False),
        sa.Column('job_description', sa.Text, nullable=False),
        sa.Column('source_url', sa.String(500)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_jobs_user_id', 'jobs', ['user_id'])

    # Applications table
    op.create_table(
        'applications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(50), default='saved'),
        sa.Column('applied_at', sa.DateTime),
        sa.Column('follow_up_date', sa.DateTime),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_applications_user_id', 'applications', ['user_id'])

    # Generated drafts table
    op.create_table(
        'generated_drafts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('application_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=True),
        sa.Column('draft_type', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('prompt_version', sa.String(50)),
        sa.Column('retrieved_chunk_ids', JSONB),
        sa.Column('user_edited_content', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Chat messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])


def downgrade() -> None:
    op.drop_table('chat_messages')
    op.drop_table('generated_drafts')
    op.drop_table('applications')
    op.drop_table('jobs')
    op.execute("DROP TRIGGER IF EXISTS chunks_tsv_update ON chunks")
    op.execute("DROP FUNCTION IF EXISTS chunks_tsv_trigger")
    op.drop_table('chunks')
    op.drop_table('source_documents')
    op.drop_table('users')
    op.execute("DROP EXTENSION IF EXISTS vector")