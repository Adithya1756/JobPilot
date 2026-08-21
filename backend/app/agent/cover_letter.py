"""
Simple cover letter generator - RAG + LLM, no complex tools.

This replaces the complex DraftingAgent with a simple two-step process:
1. Retrieve relevant experience for the job
2. Generate cover letter with that context
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import Job, GeneratedDraft
from app.retrieval.search import hybrid_search
from app.agent.llm import get_llm_client


COVER_LETTER_SYSTEM = """You are an expert at writing tailored cover letters for job applications.

Your cover letters are:
- Specific to the company and role (not generic)
- Highlight relevant experience from the user's background
- Professional but conversational tone
- 3-4 paragraphs, ~250-350 words
- Address specific requirements from the job description

Use the provided experience chunks to show how the user's background matches the job.
Reference specific projects, skills, and achievements - don't be vague."""

COVER_LETTER_USER = """Write a tailored cover letter for this job application.

**Company:** {company_name}
**Role:** {role_title}

**Job Description:**
{job_description}

**Relevant Experience from User's Background:**
{retrieved_experience}

Write a compelling cover letter that connects the user's experience to this specific role.
Mention the company by name. Reference 2-3 specific experiences that match the requirements.
Keep it to 3-4 paragraphs."""


class SimpleCoverLetterGenerator:
    """
    Simple cover letter generator using RAG.

    No complex multi-step agent, no web search, no self-critique.
    Just: retrieve -> generate.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_client()

    async def generate(
        self,
        job_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Generate a cover letter for a job.

        Args:
            job_id: Job to generate for
            user_id: User's experience to retrieve

        Returns:
            Dict with draft content and metadata
        """
        # Get job
        job_result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.user_id == user_id)
        )
        job = job_result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Job {job_id} not found for user {user_id}")

        # Retrieve relevant experience
        retrieved = await self._retrieve_experience(job, user_id)

        # Format experience for prompt
        experience_text = self._format_experience(retrieved)

        # Generate cover letter
        user_prompt = COVER_LETTER_USER.format(
            company_name=job.company_name,
            role_title=job.role_title,
            job_description=job.job_description,
            retrieved_experience=experience_text
        )

        try:
            content = await self.llm.generate(
                system=COVER_LETTER_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=2048,
                temperature=0.7
            )
        except Exception as e:
            content = f"Error generating cover letter: {str(e)}"

        # Store draft in database
        draft_record = GeneratedDraft(
            application_id=None,
            draft_type="cover_letter",
            content=content,
            retrieved_chunk_ids=[r["chunk_id"] for r in retrieved]
        )
        self.db.add(draft_record)
        await self.db.flush()

        return {
            "draft_id": str(draft_record.id),
            "content": content,
            "retrieved_chunks": len(retrieved),
            "chunk_ids": [r["chunk_id"] for r in retrieved]
        }

    async def _retrieve_experience(
        self,
        job: Job,
        user_id: UUID,
        top_k: int = 8
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant experience for the job."""
        results = await hybrid_search(
            db=self.db,
            query=job.job_description,
            user_id=str(user_id),
            limit=top_k
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

    def _format_experience(self, retrieved: List[Dict[str, Any]]) -> str:
        """Format retrieved experience for prompt."""
        if not retrieved:
            return "No relevant experience found in your documents. Write a general cover letter based on the job description."

        parts = []
        for i, chunk in enumerate(retrieved, 1):
            section = chunk.get("metadata", {}).get("section", "Experience")
            parts.append(f"[{i}] {section}: {chunk['content'][:800]}")

        return "\n\n".join(parts)


async def generate_cover_letter(
    db: AsyncSession,
    job_id: UUID,
    user_id: UUID
) -> Dict[str, Any]:
    """Convenience function for cover letter generation."""
    generator = SimpleCoverLetterGenerator(db)
    return await generator.generate(job_id, user_id)