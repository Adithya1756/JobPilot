"""
Hybrid search implementation combining vector similarity and keyword search.

Why hybrid search:
- Vector search finds semantically similar content (meaning-based)
- Keyword search finds exact term matches (lexically identical)
- Combining both catches cases where embedding models miss exact terminology
  (e.g., "Kubernetes" vs "K8s", specific tool names, acronyms)

Interview line: "I combined vector and keyword search because embedding models
trained on general text can miss exact terminology matches that are critical
for technical resumes."
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from app.ingestion.embeddings import get_embedding_service


@dataclass
class SearchResult:
    """A single retrieved chunk with relevance scores."""
    chunk_id: str
    content: str
    metadata: dict
    vector_score: Optional[float] = None  # Cosine similarity (lower = more similar for pgvector)
    keyword_score: Optional[float] = None  # BM25-like rank
    combined_score: Optional[float] = None  # RRF score


class HybridSearch:
    """
    Combines vector similarity search with PostgreSQL full-text search.

    Uses Reciprocal Rank Fusion (RRF) to merge results from both methods.

    RRF Formula: score(d) = sum(1 / (k + rank(d))) for each ranking list

    Why RRF:
    - No score normalization needed (cosine similarity and BM25 have different scales)
    - Simple and robust
    - Widely used in production systems
    """

    def __init__(self, db: AsyncSession, k: int = 60):
        """
        Args:
            db: Database session
            k: RRF constant (default 60, common in literature)
        """
        self.db = db
        self.k = k
        self.embedding_service = get_embedding_service()

    async def vector_search(
        self,
        query_embedding: List[float],
        user_id: str,
        limit: int = 20
    ) -> List[Tuple[str, float, str, dict]]:
        """
        Perform vector similarity search using pgvector.

        Uses cosine distance (<=> operator) which returns 0 for identical
        vectors and 2 for opposite vectors.

        Returns:
            List of (chunk_id, distance, content, metadata)
        """
        # Convert embedding to string for SQL
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        query = text("""
            SELECT
                id,
                content,
                metadata,
                embedding <=> :embedding::vector as distance
            FROM chunks
            WHERE user_id = :user_id AND embedding IS NOT NULL
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """)

        result = await self.db.execute(
            query,
            {"embedding": embedding_str, "user_id": user_id, "limit": limit}
        )

        rows = result.fetchall()
        return [
            (str(row[0]), float(row[3]), row[1], row[2] or {})
            for row in rows
        ]

    async def keyword_search(
        self,
        query: str,
        user_id: str,
        limit: int = 20
    ) -> List[Tuple[str, float, str, dict]]:
        """
        Perform PostgreSQL full-text search using tsvector.

        Uses to_tsquery with web search syntax (supports quoted phrases, OR, etc.)

        Returns:
            List of (chunk_id, rank, content, metadata)
        """
        # Convert query to tsquery format
        # Replace spaces with & (AND), handle quotes for phrases
        ts_query = " & ".join(query.split())

        query_sql = text("""
            SELECT
                id,
                content,
                metadata,
                ts_rank(to_tsvector('english', content), to_tsquery('english', :query)) as rank
            FROM chunks
            WHERE user_id = :user_id
                AND to_tsvector('english', content) @@ to_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        result = await self.db.execute(
            query_sql,
            {"query": ts_query, "user_id": user_id, "limit": limit}
        )

        rows = result.fetchall()
        return [
            (str(row[0]), float(row[3]), row[1], row[2] or {})
            for row in rows
        ]

    def reciprocal_rank_fusion(
        self,
        vector_results: List[Tuple[str, float, str, dict]],
        keyword_results: List[Tuple[str, float, str, dict]]
    ) -> List[SearchResult]:
        """
        Merge results using Reciprocal Rank Fusion (RRF).

        RRF gives higher scores to documents that appear high in multiple lists.
        This is robust to different score scales and doesn't require normalization.

        Args:
            vector_results: List of (chunk_id, distance, content, metadata)
            keyword_results: List of (chunk_id, rank, content, metadata)

        Returns:
            Merged and sorted list of SearchResult objects
        """
        # Track scores and data for each chunk
        chunk_scores: dict = {}  # chunk_id -> {scores, content, metadata}

        # Process vector results (rank by position, lower distance = better)
        for rank, (chunk_id, distance, content, metadata) in enumerate(vector_results, 1):
            rrf_score = 1 / (self.k + rank)
            if chunk_id not in chunk_scores:
                chunk_scores[chunk_id] = {
                    "vector_score": distance,
                    "keyword_score": None,
                    "combined_score": 0,
                    "content": content,
                    "metadata": metadata
                }
            chunk_scores[chunk_id]["combined_score"] += rrf_score

        # Process keyword results (rank by position, higher rank = better)
        for rank, (chunk_id, rank_val, content, metadata) in enumerate(keyword_results, 1):
            rrf_score = 1 / (self.k + rank)
            if chunk_id not in chunk_scores:
                chunk_scores[chunk_id] = {
                    "vector_score": None,
                    "keyword_score": rank_val,
                    "combined_score": 0,
                    "content": content,
                    "metadata": metadata
                }
            chunk_scores[chunk_id]["keyword_score"] = rank_val
            chunk_scores[chunk_id]["combined_score"] += rrf_score

        # Sort by combined score (descending)
        sorted_chunks = sorted(
            chunk_scores.items(),
            key=lambda x: x[1]["combined_score"],
            reverse=True
        )

        # Convert to SearchResult objects
        results = []
        for chunk_id, data in sorted_chunks:
            results.append(SearchResult(
                chunk_id=chunk_id,
                content=data["content"],
                metadata=data["metadata"],
                vector_score=data["vector_score"],
                keyword_score=data["keyword_score"],
                combined_score=data["combined_score"]
            ))

        return results

    async def search(
        self,
        query: str,
        user_id: str,
        limit: int = 20
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining vector and keyword methods.

        This is the main entry point for retrieval.

        Args:
            query: Search query text
            user_id: User ID to filter results
            limit: Maximum number of results

        Returns:
            Merged and ranked list of SearchResult objects
        """
        # Generate embedding for query
        query_embedding = await self.embedding_service.embed_text(query)

        # Run both searches in parallel
        vector_results = []
        keyword_results = []

        if query_embedding:
            vector_results = await self.vector_search(
                query_embedding, user_id, limit
            )

        keyword_results = await self.keyword_search(query, user_id, limit)

        # Merge using RRF
        merged = self.reciprocal_rank_fusion(vector_results, keyword_results)

        return merged[:limit]


async def hybrid_search(
    db: AsyncSession,
    query: str,
    user_id: str,
    limit: int = 20
) -> List[SearchResult]:
    """
    Convenience function for hybrid search.

    Args:
        db: Database session
        query: Search query
        user_id: User ID
        limit: Max results

    Returns:
        List of SearchResult objects
    """
    searcher = HybridSearch(db)
    return await searcher.search(query, user_id, limit)
