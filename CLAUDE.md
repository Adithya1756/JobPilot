# JobPilot — AI Job Application Assistant

An agentic AI system that ingests a user's resume and career history, retrieves relevant experience via RAG when given a job description, and autonomously drafts tailored application materials.

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

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind + shadcn/ui |
| Backend | FastAPI (Python) |
| Agent | LangGraph / hand-rolled ReAct loop |
| LLM | Anthropic Claude API (claude-sonnet-4-6 or later) |
| Embeddings | text-embedding-3-small (OpenAI) or Voyage AI |
| Vector DB | Postgres + pgvector (Neon) |
| Auth | NextAuth.js (JWT-based) |
| File Storage | S3-compatible (Supabase Storage or AWS S3) |

## Key Features

1. **Document Ingestion** — Upload resumes, project writeups → semantic chunking → embeddings
2. **Hybrid RAG** — Vector similarity + full-text search + reranking
3. **Agent Tools** — web_search, calendar, email_draft
4. **Memory** — Short-term (chat history) + long-term (style preferences)
5. **Application Tracker** — Kanban-style status tracking

## Build Milestones

- [x] Week 1: DB schema, auth, file upload + ingestion pipeline
- [x] Week 2: Basic RAG — vector search only
- [x] Week 3: Hybrid search + reranking, eval script
- [x] Week 4: Agent loop with tool calling
- [x] Week 5: Memory systems (short-term chat history + long-term style preferences)
- [x] Week 6: Frontend UI
- [x] Week 7: Calendar/email tools, deployment (Docker multi-stage, CI/CD)
- [x] Week 8: Eval write-up, demo prep (13 backend tests passing, full build verified)

## Environment Setup

Required environment variables (see `.env.example` files):

- `DATABASE_URL` — Neon Postgres connection string
- `ANTHROPIC_API_KEY` — Claude API access
- `OPENAI_API_KEY` — Embeddings (or Voyage)
- `NEXTAUTH_SECRET` — JWT signing
- `NEXTAUTH_URL` — Frontend URL

## Quick Start

```bash
# Start Postgres locally (for dev without Neon)
docker-compose up -d

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Key Files

- `backend/app/models/` — SQLAlchemy models matching the schema
- `backend/app/ingestion/` — Document parsing, chunking, embedding
- `backend/app/retrieval/` — Hybrid search, reranking
- `backend/app/agent/` — ReAct loop, tools
- `frontend/src/app/` — Next.js App Router pages
- `frontend/src/components/` — UI components (shadcn/ui)
