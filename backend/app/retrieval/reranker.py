"""
Reranker for improving retrieval precision.

Why reranking:
- Initial retrieval (vector/keyword) is optimized for SPEED over precision
- It scans thousands of chunks quickly but with coarse relevance signals
- A reranker (cross-encoder) scores each (query, chunk) pair jointly
- This is far more accurate but too slow to run on the entire dataset

Two-stage retrieval pattern:
1. Fast retrieval narrows 10,000 chunks → top 20 candidates
2. Slow reranker narrows 20 → top 5-8 for the LLM

Interview line: "I used a two-stage retrieve-then-rerank pattern because
cross-encoders are too expensive to run on the whole corpus, but they
significantly improve precision on the top candidates."
"""

from typing import List, Optional
from dataclasses import dataclass
import httpx

from app.retrieval.search import SearchResult
from app.core.config import settings


@dataclass
class RerankedResult:
    """A reranked search result with updated relevance score."""
    chunk_id: str
    content: str
    metadata: dict
    rerank_score: float
    original_rank: int


class Reranker:
    """
    Reranks search results using Cohere Rerank API.

    Cohere's reranker is specifically trained for relevance ranking
    and works well out of the box for most use cases.

    Falls back to heuristic-based reranking if API is not configured.
    """

    def __init__(self, cohere_api_key: Optional[str] = None):
        self.cohere_api_key = cohere_api_key or settings.cohere_api_key

    async def rerank_cohere(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = 8
    ) -> List[RerankedResult]:
        """
        Rerank using Cohere Rerank API.

        This is the production-ready option. Cohere's reranker is:
        - Trained specifically for relevance ranking
        - Works well out of the box
        - Handles multiple languages

        Requires COHERE_API_KEY environment variable.
        """
        if not self.cohere_api_key:
            # Fall back to heuristic reranking
            return self.rerank_heuristic(query, results, top_k)

        # Cohere has a limit of ~100 documents per request
        # If we have more, truncate to top 50
        truncated_results = results[:50]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.cohere.ai/v1/rerank",
                headers={
                    "Authorization": f"Bearer {self.cohere_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "rerank-english-v3.0",
                    "query": query,
                    "documents": [r.content for r in truncated_results],
                    "top_n": min(top_k, len(truncated_results))
                },
                timeout=30.0
            )

            if response.status_code != 200:
                # Fall back to heuristic on error
                print(f"Cohere API error: {response.status_code}")
                return self.rerank_heuristic(query, results, top_k)

            data = response.json()
            reranked = []

            for item in data["results"]:
                original_idx = item["index"]
                original_result = truncated_results[original_idx]
                reranked.append(RerankedResult(
                    chunk_id=original_result.chunk_id,
                    content=original_result.content,
                    metadata=original_result.metadata,
                    rerank_score=item["relevance_score"],
                    original_rank=original_idx
                ))

            return reranked

    def rerank_heuristic(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = 8
    ) -> List[RerankedResult]:
        """
        Simple heuristic-based reranking for development/testing.

        This doesn't require external APIs and works for testing.
        It considers:
        - Exact keyword matches in content
        - Query term frequency
        - Original combined score

        For production, use Cohere Rerank API instead.
        """
        query_terms = set(query.lower().split())
        reranked = []

        for idx, result in enumerate(results):
            content_lower = result.content.lower()

            # Count exact term matches
            term_matches = sum(1 for term in query_terms if term in content_lower)

            # Calculate term frequency bonus
            term_freq = sum(content_lower.count(term) for term in query_terms)

            # Combine with original score
            # Heuristic: weight term matches heavily, then frequency, then original score
            heuristic_score = (
                term_matches * 0.4 +
                min(term_freq / 10, 0.3) +
                (result.combined_score or 0) * 0.3
            )

            reranked.append(RerankedResult(
                chunk_id=result.chunk_id,
                content=result.content,
                metadata=result.metadata,
                rerank_score=heuristic_score,
                original_rank=idx
            ))

        # Sort by heuristic score (descending)
        reranked.sort(key=lambda x: x.rerank_score, reverse=True)

        return reranked[:top_k]

    async def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = 8
    ) -> List[RerankedResult]:
        """
        Main reranking entry point.

        Uses Cohere API if available, falls back to heuristic.
        """
        if not results:
            return []

        if self.cohere_api_key:
            try:
                return await self.rerank_cohere(query, results, top_k)
            except Exception as e:
                print(f"Cohere reranking failed: {e}")
                # Fall back to heuristic
                return self.rerank_heuristic(query, results, top_k)
        else:
            return self.rerank_heuristic(query, results, top_k)


async def rerank_results(
    query: str,
    results: List[SearchResult],
    top_k: int = 8
) -> List[RerankedResult]:
    """
    Convenience function to rerank search results.

    Args:
        query: Original search query
        results: Search results to rerank
        top_k: Number of top results to return

    Returns:
        Reranked and truncated list of results
    """
    reranker = Reranker()
    return await reranker.rerank(query, results, top_k)
