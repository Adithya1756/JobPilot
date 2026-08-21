"""
LLM client wrapper for Google Gemini.

Uses gemini-3.5-flash (free tier available via Google AI Studio).
Simple, no complex streaming or structured output needed for v1.
"""

from typing import Optional, List, Dict, Any
from google import genai
from google.genai import types

from app.core.config import settings


class LLMClient:
    """
    Wrapper for Google Gemini API using the google-genai SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.llm_model

        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    async def generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> str:
        """
        Generate a completion from the LLM.

        Args:
            system: System prompt
            messages: List of {role, content} messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Returns:
            Generated text

        Raises:
            ValueError: If API key not configured
        """
        if not self.client:
            raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY environment variable.")

        # Build contents from messages
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            # Gemini uses "user" and "model" roles
            if role == "assistant":
                role = "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            ))

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                    temperature=temperature
                )
            )
            return response.text
        except Exception as e:
            print(f"LLM generation error: {e}")
            return f"Error: {str(e)}"


# Global instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client