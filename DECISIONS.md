# Technical Decisions Log

This document records the "why" behind major architectural choices. Each entry helps you explain the project in interviews.

---

## 2026-08-19: Project Initialization

### Backend Framework: FastAPI over Django/Flask

**Chosen:** FastAPI

**Why:**
- Async-first — critical for LLM API calls and streaming responses
- Automatic OpenAPI docs — useful for frontend integration and debugging
- Type hints via Pydantic — catches errors at dev time, not runtime
- Lightweight — easier to explain than Django's monolith, more structured than Flask

**Alternatives considered:**
- Django: Too heavy, ORM makes vector operations awkward
- Flask: Too minimal, would need to add too much ourselves

---

### Frontend Framework: Next.js 14 (App Router) over Create React App

**Chosen:** Next.js 14 App Router

**Why:**
- Server-side rendering — better SEO, faster initial load
- Streaming support — SSE for real-time agent progress display
- API routes — can proxy to backend, hide secrets
- Industry standard — most job postings mention Next.js

**Alternatives considered:**
- CRA: No SSR, would need separate setup for streaming
- Remix: Less common, smaller ecosystem

---

### Database: Postgres + pgvector over Pinecone/Weaviate

**Chosen:** Postgres with pgvector extension (hosted on Neon)

**Why:**
- One database for relational + vector data — simpler ops
- ACID transactions — can update user data and embeddings atomically
- Full-text search built-in — enables hybrid search without extra infra
- pgvector is mature enough for this scale (~10k-100k vectors per user max)

**Interview line:** "At this scale, keeping relational and vector data in one system simplified transactions and ops. I'd migrate to Qdrant or Weaviate if I needed to scale past millions of vectors or needed advanced sharding."

**Alternatives considered:**
- Pinecone: Managed, but separate DB for user/app data means sync complexity
- Qdrant: Great, but adds another service to manage for v1

---

### Auth: NextAuth.js over Clerk

**Chosen:** NextAuth.js (now Auth.js)

**Why:**
- Open-source, full control over auth flow
- JWT strategy — stateless, works well with FastAPI
- No vendor lock-in — can switch providers easily
- User wanted more control than SaaS providers offer

**Trade-off:** More setup code than Clerk, but ownership of the auth stack

---

### Vector DB Hosting: Neon over Supabase

**Chosen:** Neon

**Why:**
- Serverless Postgres with pgvector — auto-scaling
- Generous free tier — good for development
- Database branching — useful for testing schema changes
- Faster cold starts than Supabase for serverless use cases

---

### Chunking Strategy: Semantic over Fixed-Size

**Chosen:** Semantic chunking (by document sections)

**Why:**
- Resume sections (Experience, Education, Projects) are natural boundaries
- Fixed-size chunking can split a bullet point from its context (e.g., separating "Led team of 5" from "and shipped X")
- Metadata (section name, company) can be attached during chunking

**Interview line:** "I chunked by resume section rather than fixed token windows because splitting mid-bullet-point would separate an achievement from its metric, hurting retrieval precision."

---

## Future Decisions (to be added during build)

- [ ] Embedding model choice (OpenAI vs Voyage)
- [ ] Reranker choice (Cohere API vs local cross-encoder)
- [ ] Agent framework (LangGraph vs hand-rolled ReAct)
- [ ] File storage (S3 vs Supabase Storage)
- [ ] Background jobs (Celery vs FastAPI BackgroundTasks)
