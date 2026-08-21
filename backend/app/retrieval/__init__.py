"""
Retrieval package - RAG hybrid search (vector + keyword).

This is the core of the RAG system:
1. Hybrid search (vector + keyword)
2. Reciprocal Rank Fusion to merge results

Interview talking points:
- Why hybrid: embedding models miss exact terminology
- Why RRF: no score normalization needed, simple and robust
"""

from app.retrieval.search import (
    HybridSearch,
    SearchResult,
    hybrid_search,
)

__all__ = [
    "HybridSearch",
    "SearchResult",
    "hybrid_search",
]
