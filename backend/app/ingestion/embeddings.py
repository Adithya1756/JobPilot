"""
Embedding service - generates embeddings using OpenAI's API.

Why text-embedding-3-small:
- Cost-effective ($0.02/1M tokens vs $0.13 for large)
- 1536 dimensions - good balance of quality and storage
- Solid performance on semantic similarity tasks

For production at scale, consider:
- Voyage AI embeddings (often better for code/technical content)
- Local embedding models (no API cost, but requires GPU)
"""

from typing import List, Optional
import httpx
from openai import AsyncOpenAI

from app.core.config import settings


class EmbeddingService:
    """
    Generates embeddings for text content.

    The embedding model converts text into a dense vector (list of floats)
    where semantically similar texts have similar vectors (measured by cosine similarity).
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.embedding_model
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats (the embedding vector), or None if API not configured
        """
        if not self.client:
            # Return None if API key not configured (for local dev without embeddings)
            return None

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None

    async def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.

        OpenAI API allows up to ~2048 inputs per request, but we batch
        smaller to be safe and track progress.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of embeddings (same order as input texts)
        """
        if not self.client:
            return [None] * len(texts)

        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )

                # Sort by index to ensure correct order
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [item.embedding for item in sorted_data]
                embeddings.extend(batch_embeddings)

            except Exception as e:
                print(f"Error in batch {i // batch_size}: {e}")
                # Add None placeholders for failed batch
                embeddings.extend([None] * len(batch))

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
    """
    Convenience function to embed multiple texts.

    Args:
        texts: List of texts to embed

    Returns:
        List of embeddings (same order as input texts)
    """
    service = get_embedding_service()
    return await service.embed_batch(texts)


async def embed_text(text: str) -> Optional[List[float]]:
    """
    Convenience function to embed a single text.

    Args:
        text: Text to embed

    Returns:
        Embedding vector or None if not configured
    """
    service = get_embedding_service()
    return await service.embed_text(text)
