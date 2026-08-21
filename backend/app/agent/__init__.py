"""
Simple agent package - RAG-based chat and cover letter generation.

Uses Google Gemini (free tier) for both embeddings and LLM.
No complex tool loops, no external paid APIs.
"""

from app.agent.llm import LLMClient, get_llm_client
from app.agent.simple_agent import SimpleAgent, chat_with_agent
from app.agent.cover_letter import SimpleCoverLetterGenerator, generate_cover_letter

__all__ = [
    "LLMClient",
    "get_llm_client",
    "SimpleAgent",
    "chat_with_agent",
    "SimpleCoverLetterGenerator",
    "generate_cover_letter",
]