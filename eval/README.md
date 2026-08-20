# Evaluation Scripts

This directory contains evaluation scripts for measuring RAG retrieval quality.

## Quick Start

```bash
# From project root
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Run evaluation
python ../eval/run_eval.py
```

## Metrics Explained

### Recall@k
What fraction of relevant chunks appeared in the top-k results?

- **High recall** = We found most of what we were looking for
- **Critical for RAG** = We want to surface ALL relevant experience for a job

### Precision@k
What fraction of top-k results were actually relevant?

- **High precision** = Results are focused, not noisy
- **Trade-off** = Higher recall often means lower precision

### MRR (Mean Reciprocal Rank)
How high up was the first relevant result?

- **MRR = 1.0** = First result was relevant
- **MRR = 0.5** = Second result was relevant
- **MRR = 0.1** = Tenth result was relevant

## Creating a Real Eval Set

The sample eval cases are placeholders. For meaningful results:

1. **Upload documents** — Add your actual resume and project writeups
2. **Create queries** — Write 10-20 job requirement-style queries
3. **Label relevance** — For each query, identify which chunks should match
4. **Run eval** — Measure how well your retrieval performs

### Example Labeled Eval Set

```python
EvalCase(
    query="experience with Python and machine learning",
    relevant_chunk_ids=[
        "chunk-uuid-1",  # Your ML project experience
        "chunk-uuid-2",  # Python skills section
        "chunk-uuid-5",  # Data science course
    ],
    description="Looking for Python/ML experience"
)
```

## Before/After Comparison

This is your best interview talking point:

| Metric | Vector Only | Hybrid + Rerank |
|--------|-------------|-----------------|
| Recall@5 | 0.45 | 0.72 |
| Recall@10 | 0.58 | 0.81 |
| MRR | 0.52 | 0.68 |

*"Hybrid search + reranking improved Recall@5 from 45% to 72% on my labeled eval set."*

## RAGAS Metrics (Optional)

For evaluating generated answer quality:

- **Faithfulness** — Does the answer stick to retrieved context?
- **Answer Relevance** — Does it address the question?
- **Context Precision** — Is retrieved context focused?

These require running an LLM to evaluate, adding cost and latency.
