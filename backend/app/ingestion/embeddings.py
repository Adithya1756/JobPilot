"""
Embedding service using Google Gemini's gemini-embedding-001 model.

Why gemini-embedding-001:
- FREE tier available (no credit card required)
- 768 dimensions via Matryoshka Representation Learning (MRL)
  (default is 3072, but we request 768 to match our DB schema)
- Multilingual support (100+ languages)
- Replaced deprecated text-embedding-004

This is the only embedding provider we use - keeps the project simple
and free to run.
"""

from typing import List, Optional
from google import genai
from google.genai import types

from app.core.config import settings


class EmbeddingService:
    """
    Generates embeddings for text content using Google Gemini.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.embedding_model
        self.dimensions = settings.embedding_dimensions

        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.

        Returns:
            List of floats (the embedding vector), or None if API not configured
        """
        if not self.client:
            return None

        try:
            response = self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=self.dimensions
                )
            )
            return response.embeddings[0].values
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None

    async def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of embeddings (same order as input texts)
        """
        if not self.client:
            return [None] * len(texts)

        embeddings = []

        for text in texts:
            try:
                embedding = await self.embed_text(text)
                embeddings.append(embedding)
            except Exception as e:
                print(f"Error embedding text: {e}")
                embeddings.append(None)

        return embeddings


# Global instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def embed_texts(texts: List[str]) -> List[Optional[List[float]]]:
    """Convenience function to embed multiple texts."""
    service = get_embedding_service()
    return await service.embed_batch(texts)


async def embed_text(text: str) -> Optional[List[float]]:
    """Convenience function to embed a single text."""
    service = get_embedding_service()
    return await service.embed_text(text)