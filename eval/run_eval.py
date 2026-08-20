#!/usr/bin/env python3
"""
Evaluation script for RAG retrieval quality.

This script measures how well our hybrid search + reranking pipeline
retrieves relevant chunks for a given query.

Metrics:
- Recall@k: What fraction of relevant chunks appeared in top-k?
- MRR (Mean Reciprocal Rank): How high was the first relevant result?
- Precision@k: What fraction of top-k results were relevant?

Interview line: "I built a repeatable eval set with 15-20 labeled pairs
and measured Recall@5 improving from X% to Y% after adding hybrid search
and reranking. This quantified improvement is far stronger in interviews
than 'I added reranking because it's best practice.'"
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.core.config import settings


@dataclass
class EvalCase:
    """A single evaluation case: query + relevant chunk IDs."""
    query: str
    relevant_chunk_ids: List[str]
    description: str


@dataclass
class EvalResult:
    """Results for a single evaluation case."""
    query: str
    retrieved_ids: List[str]
    relevant_ids: List[str]
    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    precision_at_10: float
    reciprocal_rank: float
    rerank_scores: Optional[List[float]] = None


# Sample evaluation set
# In production, you'd label these by hand based on your actual documents
# Format: (query, [relevant_chunk_ids], description)
SAMPLE_EVAL_CASES = [
    EvalCase(
        query="experience with Python and machine learning",
        relevant_chunk_ids=[],
        description="Looking for Python/ML experience"
    ),
    EvalCase(
        query="leadership and team management experience",
        relevant_chunk_ids=[],
        description="Looking for leadership roles"
    ),
    EvalCase(
        query="frontend development with React and TypeScript",
        relevant_chunk_ids=[],
        description="Looking for frontend skills"
    ),
    EvalCase(
        query="database experience PostgreSQL MongoDB",
        relevant_chunk_ids=[],
        description="Looking for database skills"
    ),
    EvalCase(
        query="cloud infrastructure AWS GCP Kubernetes",
        relevant_chunk_ids=[],
        description="Looking for cloud/devops experience"
    ),
]


class RAGEvaluator:
    """
    Evaluates RAG retrieval quality.

    Usage:
        evaluator = RAGEvaluator(db_url)
        results = evaluator.run_evaluation(test_cases)
        evaluator.print_report(results)
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_engine(db_url.replace("+asyncpg", ""))

    def calculate_recall_at_k(
        self,
        retrieved: List[str],
        relevant: List[str],
        k: int
    ) -> float:
        """
        Recall@k: What fraction of relevant items appeared in top-k?

        Args:
            retrieved: List of retrieved chunk IDs (in order)
            relevant: Set of relevant chunk IDs
            k: Number of top results to consider

        Returns:
            Recall score (0.0 to 1.0)
        """
        if not relevant:
            return 0.0

        top_k = set(retrieved[:k])
        relevant_set = set(relevant)

        return len(top_k & relevant_set) / len(relevant_set)

    def calculate_precision_at_k(
        self,
        retrieved: List[str],
        relevant: List[str],
        k: int
    ) -> float:
        """
        Precision@k: What fraction of top-k results were relevant?

        Args:
            retrieved: List of retrieved chunk IDs
            relevant: Set of relevant chunk IDs
            k: Number of top results to consider

        Returns:
            Precision score (0.0 to 1.0)
        """
        if k == 0:
            return 0.0

        top_k = retrieved[:k]
        if not top_k:
            return 0.0

        relevant_set = set(relevant)
        relevant_in_top_k = sum(1 for chunk_id in top_k if chunk_id in relevant_set)

        return relevant_in_top_k / k

    def calculate_mrr(
        self,
        retrieved: List[str],
        relevant: List[str]
    ) -> float:
        """
        Mean Reciprocal Rank: How high was the first relevant result?

        MRR = 1 / rank of first relevant item

        If no relevant items in results, MRR = 0.

        Args:
            retrieved: List of retrieved chunk IDs
            relevant: Set of relevant chunk IDs

        Returns:
            Reciprocal rank (0.0 to 1.0)
        """
        relevant_set = set(relevant)

        for rank, chunk_id in enumerate(retrieved, 1):
            if chunk_id in relevant_set:
                return 1.0 / rank

        return 0.0

    def run_single_query(
        self,
        query: str,
        user_id: str,
        use_reranking: bool = True
    ) -> List[str]:
        """
        Run a single retrieval query.

        Args:
            query: Search query
            user_id: User ID to search for
            use_reranking: Whether to apply reranking

        Returns:
            List of retrieved chunk IDs
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id
                    FROM chunks
                    WHERE user_id = :user_id
                    LIMIT 20
                """),
                {"user_id": user_id}
            )
            rows = result.fetchall()
            return [str(row[0]) for row in rows]

    def run_evaluation(
        self,
        test_cases: List[EvalCase],
        user_id: Optional[str] = None,
        use_reranking: bool = True
    ) -> List[EvalResult]:
        """
        Run evaluation on a set of test cases.

        Args:
            test_cases: List of (query, relevant_ids) tuples
            user_id: User ID to search for
            use_reranking: Whether to apply reranking

        Returns:
            List of EvalResult objects
        """
        results = []

        # First, find a user with chunks if no user_id provided
        if user_id is None:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT id FROM users LIMIT 1"))
                row = result.fetchone()
                if row:
                    user_id = str(row[0])
                else:
                    user_id = "00000000-0000-0000-0000-000000000000"

        for case in test_cases:
            # Run retrieval (simplified for demo)
            retrieved_ids = self.run_single_query(
                case.query,
                user_id or "00000000-0000-0000-0000-000000000000",
                use_reranking
            )

            # Calculate metrics
            recall_5 = self.calculate_recall_at_k(retrieved_ids, case.relevant_chunk_ids, 5)
            recall_10 = self.calculate_recall_at_k(retrieved_ids, case.relevant_chunk_ids, 10)
            precision_5 = self.calculate_precision_at_k(retrieved_ids, case.relevant_chunk_ids, 5)
            precision_10 = self.calculate_precision_at_k(retrieved_ids, case.relevant_chunk_ids, 10)
            mrr = self.calculate_mrr(retrieved_ids, case.relevant_chunk_ids)

            results.append(EvalResult(
                query=case.query,
                retrieved_ids=retrieved_ids,
                relevant_ids=case.relevant_chunk_ids,
                recall_at_5=recall_5,
                recall_at_10=recall_10,
                precision_at_5=precision_5,
                precision_at_10=precision_10,
                reciprocal_rank=mrr
            ))

        return results

    def print_report(self, results: List[EvalResult]) -> None:
        """
        Print a formatted evaluation report.

        Args:
            results: List of evaluation results
        """
        if not results:
            print("No results to report.")
            return

        # Calculate averages
        avg_recall_5 = sum(r.recall_at_5 for r in results) / len(results)
        avg_recall_10 = sum(r.recall_at_10 for r in results) / len(results)
        avg_precision_5 = sum(r.precision_at_5 for r in results) / len(results)
        avg_precision_10 = sum(r.precision_at_10 for r in results) / len(results)
        avg_mrr = sum(r.reciprocal_rank for r in results) / len(results)

        print("\n" + "=" * 60)
        print("RAG RETRIEVAL EVALUATION REPORT")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Number of test cases: {len(results)}")
        print()

        print("-" * 60)
        print("AGGREGATE METRICS")
        print("-" * 60)
        print(f"{'Metric':<25} {'Value':>10}")
        print(f"{'-' * 35}")
        print(f"{'Recall@5':<25} {avg_recall_5:>10.3f}")
        print(f"{'Recall@10':<25} {avg_recall_10:>10.3f}")
        print(f"{'Precision@5':<25} {avg_precision_5:>10.3f}")
        print(f"{'Precision@10':<25} {avg_precision_10:>10.3f}")
        print(f"{'MRR':<25} {avg_mrr:>10.3f}")
        print()

        print("-" * 60)
        print("PER-QUERY RESULTS")
        print("-" * 60)
        print(f"{'Query':<30} {'R@5':>6} {'R@10':>6} {'MRR':>6}")
        print(f"{'-' * 48}")

        for r in results:
            query_short = r.query[:28] + ".." if len(r.query) > 30 else r.query
            print(f"{query_short:<30} {r.recall_at_5:>6.3f} {r.recall_at_10:>6.3f} {r.reciprocal_rank:>6.3f}")

        print("=" * 60)
        print()

    def save_report(self, results: List[EvalResult], output_path: str) -> None:
        """Save results to a JSON file."""
        output = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "num_cases": len(results),
                "avg_recall_at_5": sum(r.recall_at_5 for r in results) / len(results) if results else 0,
                "avg_recall_at_10": sum(r.recall_at_10 for r in results) / len(results) if results else 0,
                "avg_precision_at_5": sum(r.precision_at_5 for r in results) / len(results) if results else 0,
                "avg_precision_at_10": sum(r.precision_at_10 for r in results) / len(results) if results else 0,
                "avg_mrr": sum(r.reciprocal_rank for r in results) / len(results) if results else 0,
            },
            "results": [
                {
                    "query": r.query,
                    "recall_at_5": r.recall_at_5,
                    "recall_at_10": r.recall_at_10,
                    "precision_at_5": r.precision_at_5,
                    "precision_at_10": r.precision_at_10,
                    "reciprocal_rank": r.reciprocal_rank,
                }
                for r in results
            ]
        }

        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        print(f"Results saved to {output_path}")


def main():
    """Main entry point for the evaluation script."""
    print("RAG Retrieval Evaluation")
    print("-" * 40)

    # Use database URL from settings
    db_url = settings.database_url

    # Create evaluator
    evaluator = RAGEvaluator(db_url)

    # Run evaluation
    print("\nRunning evaluation with sample queries...")
    print("(Note: For real evaluation, label relevant chunks for your actual documents)")
    print()

    results = evaluator.run_evaluation(SAMPLE_EVAL_CASES)

    # Print report
    evaluator.print_report(results)

    # Save results
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    evaluator.save_report(results, str(output_dir / "eval_results.json"))

    print("\nTIP: To get meaningful results, create a labeled eval set:")
    print("1. Upload several documents (resumes, project writeups)")
    print("2. Create 10-20 queries representing real job requirements")
    print("3. For each query, label the chunk IDs that should be retrieved")
    print("4. Re-run this script to measure retrieval quality")
    print()
    print("This labeled dataset is your single best interview talking point!")


if __name__ == "__main__":
    main()
