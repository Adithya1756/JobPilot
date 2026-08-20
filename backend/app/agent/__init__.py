"""
Agent package - LLM agent with tools.

The agent is the core of JobPilot's intelligence:
- Takes a job description as input
- Retrieves relevant experience via RAG
- Generates tailored application materials
- Uses tools (web search, calendar, email)

Week 2: Basic drafting with RAG retrieval
Week 4: Full agent loop with tool calling
"""

from app.agent.llm import LLMClient, get_llm_client
from app.agent.drafting import DraftingAgent, generate_cover_letter, DraftResult
from app.agent.prompts import (
    COVER_LETTER_SYSTEM,
    COVER_LETTER_USER,
    EXTRACT_REQUIREMENTS_SYSTEM,
    CRITIQUE_SYSTEM,
)

__all__ = [
    "LLMClient",
    "get_llm_client",
    "DraftingAgent",
    "generate_cover_letter",
    "DraftResult",
    "COVER_LETTER_SYSTEM",
    "COVER_LETTER_USER",
    "EXTRACT_REQUIREMENTS_SYSTEM",
    "CRITIQUE_SYSTEM",
]
