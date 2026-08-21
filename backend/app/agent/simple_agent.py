"""
Simple chat agent with RAG retrieval - no complex tool loops.

This replaces the complex agent system with a simple, single-call approach:
1. User asks a question
2. We retrieve relevant experience chunks from their documents
3. We generate a response with context

No web search, no calendar, no email drafting, no complex state machine.
Just RAG + LLM - simple and free.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import Job
from app.retrieval.search import hybrid_search
from app.agent.llm import get_llm_client


SIMPLE_CHAT_SYSTEM = """You are JobPilot, a helpful AI assistant for job applications.

You help users by:
- Answering questions about their experience based on their uploaded documents
- Helping them think through job requirements
- Providing general job search advice

You have access to the user's resume and project history through RAG retrieval.
Use this context to give specific, personalized answers.

Be helpful, concise, and encouraging. If you don't have enough context from their
documents, say so and ask clarifying questions."""


class SimpleAgent:
    """
    Simple chat agent with RAG retrieval.

    Single call: retrieve relevant context -> generate response.
    No tool loops, no complex state machines.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_client()

    async def chat(
        self,
        message: str,
        user_id: UUID,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        job_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Process a user message with RAG retrieval.

        Args:
            message: User's question/message
            user_id: User ID for document retrieval
            conversation_history: Previous messages for context
            job_id: Optional job ID to focus retrieval

        Returns:
            Dict with response and retrieval info
        """
        # Retrieve relevant experience
        retrieved = await self._retrieve_context(message, user_id, job_id)

        # Build context from retrieved chunks
        context_text = self._format_context(retrieved)

        # Build messages for LLM
        messages = self._build_messages(message, conversation_history, context_text)

        # Generate response
        try:
            response = await self.llm.generate(
                system=SIMPLE_CHAT_SYSTEM,
                messages=messages,
                max_tokens=1500,
                temperature=0.7
            )
        except Exception as e:
            response = f"I'm having trouble connecting to the AI service. Please check your GEMINI_API_KEY. Error: {str(e)}"

        return {
            "response": response,
            "retrieved_chunks": len(retrieved),
            "context_used": [r.get("chunk_id") for r in retrieved[:5]]
        }

    async def _retrieve_context(
        self,
        query: str,
        user_id: UUID,
        job_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant experience chunks."""
        # If job_id provided, use job description as query for better relevance
        if job_id:
            job_result = await self.db.execute(
                select(Job).where(Job.id == job_id, Job.user_id == user_id)
            )
            job = job_result.scalar_one_or_none()
            if job:
                query = f"{query} - Job: {job.company_name} {job.role_title}\n{job.job_description}"

        # Run hybrid search
        results = await hybrid_search(
            db=self.db,
            query=query,
            user_id=str(user_id),
            limit=10
        )

        return [
            {
                "chunk_id": r.chunk_id,
                "content": r.content,
                "metadata": r.metadata,
                "score": r.combined_score
            }
            for r in results
        ]

    def _format_context(self, retrieved: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks into context string."""
        if not retrieved:
            return "No relevant experience found in your documents."

        parts = []
        for i, chunk in enumerate(retrieved[:5], 1):
            section = chunk.get("metadata", {}).get("section", "Experience")
            parts.append(f"[{i}] {section}: {chunk['content'][:500]}")

        return "Relevant experience from your documents:\n\n" + "\n\n".join(parts)

    def _build_messages(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        context_text: str
    ) -> List[Dict[str, str]]:
        """Build messages array for LLM."""
        messages = []

        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # Add context + current message
        user_message = f"{context_text}\n\nUser: {message}"
        messages.append({"role": "user", "content": user_message})

        return messages


async def chat_with_agent(
    db: AsyncSession,
    user_id: UUID,
    message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    job_id: Optional[UUID] = None
) -> Dict[str, Any]:
    """Convenience function for simple chat with RAG."""
    agent = SimpleAgent(db)
    return await agent.chat(message, user_id, conversation_history, job_id)