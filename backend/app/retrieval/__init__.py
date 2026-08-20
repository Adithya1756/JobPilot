"""
Retrieval package - RAG search and reranking.

This is the core of the RAG system:
1. Hybrid search (vector + keyword)
2. Reciprocal Rank Fusion to merge results
3. Reranking for precision

Interview talking points:
- Why hybrid: embedding models miss exact terminology
- Why RRF: no score normalization needed, simple and robust
- Why reranking: cross-encoders are accurate but expensive
"""

from app.retrieval.search import (
    HybridSearch,
    SearchResult,
    hybrid_search,
)
from app.retrieval.reranker import (
    Reranker,
    RerankedResult,
    rerank_results,
)

__all__ = [
    "HybridSearch",
    "SearchResult",
    "hybrid_search",
    "Reranker",
    "RerankedResult",
    "rerank_results",
]
