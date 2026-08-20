"""
Memory system for the agent.

Two types of memory:
1. Short-term (ChatMessage): Conversation history per session
2. Long-term (StyleMemory): Learned preferences from user edits

Interview line: "I built a dual memory system - short-term chat history
for conversation context, and long-term style memory that learns from
user edits. The style memory uses embeddings so we can retrieve
relevant preferences for each specific drafting task."
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.user import ChatMessage, StyleMemory, GeneratedDraft
from app.ingestion.embeddings import embed_texts
from app.core.config import settings


@dataclass
class ChatHistoryEntry:
    """A single chat history entry for LLM context."""
    role: str  # user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ShortTermMemory:
    """
    Manages chat history per conversation session.

    Uses the ChatMessage table to persist messages.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_message(
        self,
        session_id: UUID,
        user_id: UUID,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None
    ) -> ChatMessage:
        """
        Add a message to the conversation history.

        Args:
            session_id: Conversation session ID
            user_id: User ID
            role: Message role (user, assistant, tool)
            content: Message content
            tool_calls: Tool calls made (for assistant messages)
            tool_call_id: Tool call ID (for tool messages)

        Returns:
            Created ChatMessage
        """
        message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def get_history(
        self,
        session_id: UUID,
        user_id: UUID,
        limit: int = 20
    ) -> List[ChatHistoryEntry]:
        """
        Get conversation history for a session.

        Returns messages in chronological order (oldest first).

        Args:
            session_id: Session to get history for
            user_id: User ID (for security)
            limit: Maximum number of messages to return

        Returns:
            List of chat history entries
        """
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()

        # Reverse to get chronological order
        messages = list(reversed(messages))

        return [
            ChatHistoryEntry(
                role=m.role,
                content=m.content,
                tool_calls=m.tool_calls,
                tool_call_id=m.tool_call_id
            )
            for m in messages
        ]

    async def clear_history(self, session_id: UUID, user_id: UUID) -> int:
        """
        Clear all messages for a session.

        Returns number of deleted messages.
        """
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.user_id == user_id)
        )
        messages = result.scalars().all()

        for msg in messages:
            await self.db.delete(msg)

        return len(messages)


class LongTermMemory:
    """
    Manages learned style preferences from user edits.

    When a user edits a generated draft, we extract the style differences
    and store them as preferences with embeddings. These are retrieved
    for future similar drafting tasks.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def extract_and_store_preference(
        self,
        user_id: UUID,
        draft_id: UUID,
        original_content: str,
        edited_content: str
    ) -> Optional[StyleMemory]:
        """
        Extract style preference from user edit and store it.

        Uses LLM to analyze the difference and generate a preference description.

        Args:
            user_id: User who made the edit
            draft_id: Draft that was edited
            original_content: Original generated content
            edited_content: User's edited version

        Returns:
            Created StyleMemory or None if no significant difference
        """
        # Skip if content is essentially the same
        if original_content.strip() == edited_content.strip():
            return None

        # Use LLM to extract style preference
        from app.agent.llm import get_llm_client
        llm = get_llm_client()

        prompt = f"""Compare the original generated draft with the user's edited version.
Extract the key style preferences the user is demonstrating.

Original:
{original_content}

Edited:
{edited_content}

Write a concise style preference description (2-3 sentences) that captures:
- Tone changes (more formal, more casual, more confident, etc.)
- Length preferences (shorter, longer, more concise)
- Structural preferences (more bullet points, more paragraphs, specific sections)
- Any specific wording or phrasing preferences

If the changes are minimal or just typo fixes, respond with "NO_SIGNIFICANT_CHANGE"."""

        try:
            preference_text = await llm.generate(
                system="You are a writing style analyst. Extract actionable style preferences from user edits.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3
            )

            if "NO_SIGNIFICANT_CHANGE" in preference_text:
                return None

            # Embed the preference
            embeddings = await embed_texts([preference_text])
            embedding = embeddings[0] if embeddings else None

            if not embedding:
                return None

            # Store
            memory = StyleMemory(
                user_id=user_id,
                preference_text=preference_text,
                embedding=embedding,
                source_draft_id=draft_id
            )
            self.db.add(memory)
            await self.db.flush()

            return memory

        except Exception as e:
            print(f"Failed to extract style preference: {e}")
            return None

    async def get_relevant_preferences(
        self,
        user_id: UUID,
        query: str,
        limit: int = 5
    ) -> List[str]:
        """
        Retrieve relevant style preferences for a drafting task.

        Uses vector similarity search on the preference embeddings.

        Args:
            user_id: User ID
            query: Query to match against (e.g., job description)
            limit: Maximum preferences to return

        Returns:
            List of preference text descriptions
        """
        # Embed the query
        embeddings = await embed_texts([query])
        if not embeddings:
            return []

        query_embedding = embeddings[0]

        # Vector similarity search
        result = await self.db.execute(
            select(StyleMemory.preference_text)
            .where(StyleMemory.user_id == user_id)
            .order_by(StyleMemory.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        preferences = result.scalars().all()

        return list(preferences)

    async def get_all_preferences(
        self,
        user_id: UUID,
        limit: int = 20
    ) -> List[str]:
        """
        Get all style preferences for a user (most recent first).

        Args:
            user_id: User ID
            limit: Maximum to return

        Returns:
            List of preference text descriptions
        """
        result = await self.db.execute(
            select(StyleMemory.preference_text)
            .where(StyleMemory.user_id == user_id)
            .order_by(StyleMemory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def build_style_context(
    db: AsyncSession,
    user_id: UUID,
    job_description: str
) -> str:
    """
    Build style context string from long-term memory for a job.

    Args:
        db: Database session
        user_id: User ID
        job_description: Job description to match preferences against

    Returns:
        Formatted style context string or empty string
    """
    memory = LongTermMemory(db)
    preferences = await memory.get_relevant_preferences(user_id, job_description)

    if not preferences:
        return ""

    context = "USER STYLE PREFERENCES (from past edits):\n"
    for i, pref in enumerate(preferences, 1):
        context += f"{i}. {pref}\n"

    context += "\nApply these preferences when generating the cover letter."
    return context


async def update_style_from_edit(
    db: AsyncSession,
    user_id: UUID,
    draft_id: UUID,
    original_content: str,
    edited_content: str
) -> bool:
    """
    Update long-term memory from a user edit.

    Called when user saves an edited draft.

    Args:
        db: Database session
        user_id: User ID
        draft_id: Draft that was edited
        original_content: Original generated content
        edited_content: User's edited version

    Returns:
        True if preference was extracted and stored
    """
    memory = LongTermMemory(db)
    result = await memory.extract_and_store_preference(
        user_id=user_id,
        draft_id=draft_id,
        original_content=original_content,
        edited_content=edited_content
    )
    return result is not None