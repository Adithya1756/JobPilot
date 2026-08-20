# JobPilot Architecture

## System Overview

```
┌─────────────────┐      ┌──────────────────────────────────────────────┐
│   Next.js UI     │◄────►│                FastAPI Backend                │
│ (chat, tracker,  │ REST/│  ┌────────────┐  ┌───────────────────────┐  │
│  upload, auth)   │ SSE  │  │ Ingestion  │  │      Agent Layer       │  │
└─────────────────┘      │  │ Pipeline   │  │  (LangGraph state      │  │
                          │  │ (chunk →   │  │   machine / ReAct loop)│  │
                          │  │  embed →   │  │  Tools:                │  │
                          │  │  store)    │  │  - retrieve_experience │  │
                          │  └─────┬──────┘  │  - web_search          │  │
                          │        │         │  - schedule_followup   │  │
                          │        ▼         │  - draft_email         │  │
                          │  ┌────────────┐  └──────────┬─────────────┘  │
                          │  │ pgvector   │             │                │
                          │  │ (embeddings│◄────────────┘                │
                          │  │  + hybrid  │                              │
                          │  │  search)   │        ┌──────────────┐      │
                          │  └────────────┘        │  Postgres    │      │
                          │                         │  (users,     │      │
                          │                         │  applications│      │
                          │                         │  chat_history│      │
                          │                         │  memory)     │      │
                          │                         └──────────────┘      │
                          └──────────────────────────────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │  Anthropic Claude API  │
                              └───────────────────────┘
```

## Data Flow

### 1. Document Ingestion Flow

```
User uploads PDF/DOCX
       ↓
FastAPI receives file → stores in S3
       ↓
Text extraction (pdfplumber / python-docx)
       ↓
Semantic chunking (by resume sections)
       ↓
Embedding generation (text-embedding-3-small)
       ↓
Store chunks in Postgres with:
  - embedding (VECTOR)
  - tsv (TSVECTOR for keyword search)
  - metadata (JSONB)
```

### 2. RAG Query Flow

```
User pastes job description
       ↓
Agent extracts key requirements (LLM call)
       ↓
For each requirement:
  - Embed requirement
  - Hybrid search (vector + full-text)
  - Reciprocal Rank Fusion merge
       ↓
Rerank top-20 candidates → top-8
       ↓
Inject retrieved chunks into LLM prompt
       ↓
Generate tailored cover letter / answers
```

### 3. Agent Tool-Calling Flow

```
[Start]
  ↓
Parse JD → Retrieve experience (RAG)
  ↓
Need company info? ──Yes──→ web_search tool
  ↓ No
Draft cover letter
  ↓
Self-critique (LLM reviews draft vs JD)
  ↓
Present to user
  ↓
User applies? ──Yes──→ schedule_followup tool
                           ↓
                       draft_email tool
                           ↓
                       Store user edits → style_memory
[End]
```

## Key Design Decisions

See `DECISIONS.md` for rationale on tech choices.
