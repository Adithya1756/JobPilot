# JobPilot — AI Job Application Assistant

A simplified AI system that ingests a user's resume and career history, retrieves relevant experience via hybrid RAG (vector + keyword search) when given a job description, and drafts tailored cover letters — all running on a single **Google Gemini free-tier API key**.

## Project Structure

```
/
├── backend/          # FastAPI (Python)
├── frontend/         # Next.js 14 (App Router)
├── eval/             # Evaluation scripts
├── docker-compose.yml
├── ARCHITECTURE.md
└── DECISIONS.md
```

## Tech Stack (Gemini Free Tier Only)

| Layer | Choice |
|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind + shadcn/ui |
| Backend | FastAPI (Python) |
| Agent | Simple single-turn LLM calls (no complex ReAct loop) |
| LLM | **Google Gemini API** (`gemini-3.5-flash` via `google-genai` — free tier) |
| Embeddings | **Google Gemini API** (`gemini-embedding-001` — 768 dims via MRL, free tier) |
| Vector DB | Postgres + pgvector (local or Neon) |
| Auth | JWT (python-jose + passlib/bcrypt) |
| File Storage | Local filesystem (`uploads/`) — no S3 needed for dev |

**Removed paid dependencies:** Anthropic Claude, OpenAI, Voyage AI, Cohere, Tavily/Serper, Google Calendar/Email APIs, NextAuth.js, S3/Supabase Storage.

## Key Features

1. **Document Ingestion** — Upload resumes, project writeups → semantic chunking → Gemini embeddings (768-dim)
2. **Hybrid RAG** — Vector similarity (pgvector HNSW) + PostgreSQL full-text search (tsvector) + Reciprocal Rank Fusion (RRF)
3. **Simple RAG Chat** — Single-turn LLM with retrieved context
4. **Cover Letter Generation** — One-shot draft using job description + retrieved experience
5. **Application Tracker** — Kanban-style status tracking (saved/applied/interview/offer/rejected)

**Removed complex features:** Multi-step agent loops, web search, calendar integration, email drafting, reranking, long-term style memory, streaming responses.

## Build Milestones (Simplified)

- [x] Week 1: DB schema, auth, file upload + ingestion pipeline
- [x] Week 2: Basic RAG — vector search only
- [x] Week 3: Hybrid search (vector + keyword) + RRF fusion
- [x] Week 4: Simple agent — chat + cover letter draft
- [x] Week 5: Short-term chat history memory only
- [x] Week 6: Frontend UI (existing)
- [x] Week 7: Local dev deployment (Docker Compose)
- [x] Week 8: Test suite (9 backend tests passing), verify endpoints

## Environment Setup

Required environment variables (see `.env.example` files):

- `DATABASE_URL` — Postgres connection string (e.g., `postgresql+asyncpg://jobpilot:jobpilot_dev_password@localhost:5432/jobpilot`)
- `JWT_SECRET_KEY` — JWT signing key (min 32 chars)
- `JWT_ALGORITHM` — `HS256`
- `GEMINI_API_KEY` — **Single Google Gemini API key** (get free at https://aistudio.google.com)
- `UPLOAD_DIR` — Local upload directory (default: `uploads`)

**No longer needed:** `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `REDIS_URL`, S3 credentials.

## Quick Start

```bash
# Start Postgres locally (for dev without Neon)
docker-compose up -d

# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Key Files (Simplified)

- `backend/app/models/` — SQLAlchemy models (User, SourceDocument, Chunk, Job, Application, GeneratedDraft, ChatMessage)
- `backend/app/ingestion/` — Document parsing, chunking, Gemini embeddings
- `backend/app/retrieval/` — Hybrid search (vector + keyword + RRF)
- `backend/app/agent/` — SimpleAgent (chat), SimpleCoverLetterGenerator (draft)
- `backend/app/api/routes/` — REST endpoints (auth, documents, jobs, agent, memory)
- `frontend/src/app/` — Next.js App Router pages
- `frontend/src/components/` — UI components (shadcn/ui)

## Database Schema Highlights

- **chunks.embedding**: `Vector(768)` for Gemini `gemini-embedding-001` (768 dims via MRL)
- **chunks.tsv**: `tsvector` for full-text search (auto-populated via trigger)
- **HNSW index** on `chunks.embedding` for fast cosine similarity
- **GIN index** on `to_tsvector('english', content)` for keyword search
- **generated_drafts.application_id**: nullable (drafts can exist before application)

## Graceful Degradation

If `GEMINI_API_KEY` is not set or invalid:
- Embeddings return `None` → vector search skipped, keyword search still works
- LLM calls return error message string → endpoints return 200/201 with informative responses
- All API endpoints remain functional for testing/development