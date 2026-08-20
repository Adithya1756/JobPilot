"""
LLM client wrapper for Anthropic Claude.

Provides a clean interface for making LLM calls with:
- Structured output support (JSON mode)
- Streaming support
- Error handling
- Token counting (for observability)
"""

from typing import Optional, List, Dict, Any, AsyncIterator
import json
import anthropic

from app.core.config import settings


class LLMClient:
    """
    Wrapper for Anthropic Claude API.

    Uses claude-sonnet for drafting (good balance of quality and speed).
    For evaluation or simpler tasks, could use claude-haiku.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or "claude-sonnet-4-20250514"  # Latest Sonnet
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key) if self.api_key else None

    async def generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
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
            raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable.")

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages
        )

        return response.content[0].text

    async def generate_json(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        Generate a JSON completion from the LLM.

        Lower temperature for more deterministic structured output.
        Parses the response as JSON.

        Returns:
            Parsed JSON object
        """
        text = await self.generate(system, messages, max_tokens, temperature)

        # Try to extract JSON from the response
        # Sometimes the model wraps it in markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Return raw text in a fallback structure
            return {"raw_response": text, "parse_error": True}

    async def stream(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """
        Stream the completion token by token.

        Yields:
            Individual text chunks
        """
        if not self.client:
            raise ValueError("Anthropic API key not configured.")

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages
        ) as stream:
            async for text in stream.text_stream:
                yield text


# Global instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
