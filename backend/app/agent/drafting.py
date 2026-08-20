"""
Agent drafting service - orchestrates cover letter generation.

Flow:
1. Extract key requirements from job description
2. Retrieve relevant experience via hybrid search
3. Generate cover letter using LLM
4. Optional: self-critique step
5. Return draft with traceability info

This is the core agent logic, implemented as an explicit state machine
rather than a black-box framework call.

Interview line: "I modeled the agent as an explicit state graph so I could
add a self-critique step and trace exactly which tool was called and why,
which matters a lot for debugging non-deterministic LLM behavior."
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from dataclasses import dataclass
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import Job, GeneratedDraft
from app.retrieval.search import hybrid_search
from app.retrieval.reranker import rerank_results
from app.agent.llm import get_llm_client
from app.agent.prompts import (
    COVER_LETTER_SYSTEM,
    COVER_LETTER_USER,
    EXTRACT_REQUIREMENTS_SYSTEM,
    CRITIQUE_SYSTEM,
)
from app.agent.tools import research_company
from app.agent.memory import build_style_context, update_style_from_edit


@dataclass
class DraftResult:
    """Result of a cover letter drafting operation."""
    draft_id: Optional[str]
    content: str
    retrieved_chunk_ids: List[str]
    requirements: Dict[str, Any]
    critique: Optional[Dict[str, Any]] = None


class DraftingAgent:
    """
    Agent for generating tailored application materials.

    This is NOT a single LLM call - it's a multi-step process:
    1. Parse job description for key requirements
    2. Retrieve relevant experience chunks
    3. Generate draft
    4. (Optional) Self-critique

    Each step is visible and debuggable.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_client()

    async def extract_requirements(self, job_description: str) -> Dict[str, Any]:
        """
        Step 1: Extract key requirements from job description.

        This is a small LLM call that parses the JD into structured data.
        We use this to guide retrieval and verify the draft.

        Why extract requirements instead of just embedding the whole JD:
        - Retrieving per-requirement covers breadth
        - Single embedding would miss details
        - Structured requirements enable verification
        """
        messages = [{"role": "user", "content": f"Extract requirements from this job description:\n\n{job_description}"}]

        try:
            requirements = await self.llm.generate_json(
                system=EXTRACT_REQUIREMENTS_SYSTEM,
                messages=messages,
                temperature=0.2  # Low temperature for consistency
            )
            return requirements
        except Exception as e:
            # Fallback: return empty structure
            print(f"Error extracting requirements: {e}")
            return {
                "required_skills": [],
                "preferred_skills": [],
                "experience_requirements": [],
                "key_responsibilities": [],
                "parse_error": str(e)
            }

    async def retrieve_experience(
        self,
        job_description: str,
        user_id: UUID,
        top_k: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Step 2: Retrieve relevant experience using hybrid search.

        Uses the full job description as the query (could also query
        per-requirement for more thorough coverage).

        Returns top-k chunks after reranking.
        """
        # Hybrid search (vector + keyword)
        results = await hybrid_search(
            db=self.db,
            query=job_description,
            user_id=str(user_id),
            limit=20  # Get more candidates for reranking
        )

        # Rerank to get most relevant
        reranked = await rerank_results(
            query=job_description,
            results=results,
            top_k=top_k
        )

        return [
            {
                "chunk_id": r.chunk_id,
                "content": r.content,
                "metadata": r.metadata,
                "rerank_score": r.rerank_score
            }
            for r in reranked
        ]

    async def generate_cover_letter(
        self,
        job: Job,
        retrieved_experience: List[Dict[str, Any]],
        company_info: Optional[str] = None,
        style_context: Optional[str] = None
    ) -> str:
        """
        Step 3: Generate the cover letter using retrieved context.

        This is where the RAG magic happens - the LLM gets the specific
        chunks that are relevant to THIS job.
        """
        # Format retrieved experience
        experience_text = "\n\n---\n\n".join([
            f"[{exp.get('metadata', {}).get('section', 'Experience')}]\n{exp['content']}"
            for exp in retrieved_experience
        ])

        # Format company info
        company_info_text = company_info or "No specific company information available. Write a generally professional cover letter."

        # Add style context if available
        style_section = f"\n\n{style_context}" if style_context else ""

        # Build the prompt
        user_prompt = COVER_LETTER_USER.format(
            company_name=job.company_name,
            role_title=job.role_title,
            job_description=job.job_description,
            retrieved_experience=experience_text,
            company_info=company_info_text
        ) + style_section

        # Generate
        messages = [{"role": "user", "content": user_prompt}]

        try:
            content = await self.llm.generate(
                system=COVER_LETTER_SYSTEM,
                messages=messages,
                max_tokens=2048,
                temperature=0.7
            )
            return content
        except Exception as e:
            return f"Error generating cover letter: {str(e)}"

    async def critique_draft(
        self,
        draft: str,
        job_description: str,
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 4 (Optional): Self-critique the draft.

        This is a lightweight form of the "reflection" pattern common
        in agentic systems - the model reviews its own output.

        Returns structured feedback that could be used to:
        - Auto-revise the draft
        - Show the user areas for improvement
        - Track quality metrics
        """
        messages = [{
            "role": "user",
            "content": f"""# Job Description
{job_description}

# Key Requirements
{json.dumps(requirements, indent=2)}

# Draft Cover Letter
{draft}

Evaluate this cover letter against the job requirements."""
        }]

        try:
            critique = await self.llm.generate_json(
                system=CRITIQUE_SYSTEM,
                messages=messages,
                temperature=0.3
            )
            return critique
        except Exception as e:
            return {"error": str(e)}

    async def draft_cover_letter(
        self,
        job_id: UUID,
        user_id: UUID,
        include_critique: bool = False,
        use_web_search: bool = True
    ) -> DraftResult:
        """
        Main entry point - generate a cover letter for a job.

        Orchestrates all steps in sequence.

        Args:
            job_id: Job to generate for
            user_id: User's experience to retrieve
            include_critique: Whether to run self-critique
            use_web_search: Whether to research company via web search

        Returns:
            DraftResult with content and traceability info
        """
        # Get job
        result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.user_id == user_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Job {job_id} not found for user {user_id}")

        # Step 1: Extract requirements
        requirements = await self.extract_requirements(job.job_description)

        # Step 2: Retrieve relevant experience
        retrieved = await self.retrieve_experience(
            job_description=job.job_description,
            user_id=user_id,
            top_k=8
        )

        # Step 2.5: Research company via web search (optional)
        company_info = None
        if use_web_search and job.company_name:
            try:
                company_research = await research_company(job.company_name)
                if company_research and company_research.get("summary"):
                    company_info = f"Company Research for {job.company_name}:\n{company_research['summary']}"
            except Exception as e:
                print(f"Web search for company info failed: {e}")
                # Continue without company info - this is non-critical

        # Step 2.6: Retrieve style preferences from long-term memory
        style_context = await build_style_context(
            self.db, user_id, job.job_description
        )

        # Step 3: Generate cover letter
        content = await self.generate_cover_letter(
            job=job,
            retrieved_experience=retrieved,
            company_info=company_info,
            style_context=style_context
        )

        # Step 4: Optional critique
        critique = None
        if include_critique:
            critique = await self.critique_draft(
                draft=content,
                job_description=job.job_description,
                requirements=requirements
            )

        # Store draft in database
        draft_record = GeneratedDraft(
            application_id=None,  # Will be linked when application is created
            draft_type="cover_letter",
            content=content,
            retrieved_chunk_ids=[r["chunk_id"] for r in retrieved]
        )
        self.db.add(draft_record)
        await self.db.flush()

        return DraftResult(
            draft_id=str(draft_record.id),
            content=content,
            retrieved_chunk_ids=[r["chunk_id"] for r in retrieved],
            requirements=requirements,
            critique=critique
        )


async def generate_cover_letter(
    db: AsyncSession,
    job_id: UUID,
    user_id: UUID,
    include_critique: bool = False,
    use_web_search: bool = True
) -> DraftResult:
    """
    Convenience function for cover letter generation.

    Args:
        db: Database session
        job_id: Job to generate for
        user_id: User's experience to retrieve
        include_critique: Whether to run self-critique
        use_web_search: Whether to research company via web search
    """
    agent = DraftingAgent(db)
    return await agent.draft_cover_letter(job_id, user_id, include_critique, use_web_search)
