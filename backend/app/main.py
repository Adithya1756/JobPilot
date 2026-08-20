"""
JobPilot Backend - FastAPI Application

Main entry point for the API server.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.api.routes import auth_router, documents_router, health_router, jobs_router, agent_router, agent_tools_router, memory_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events.

    Handles:
    - Database initialization on startup
    - Connection cleanup on shutdown
    """
    # Startup
    print("🚀 Starting JobPilot API...")
    await init_db()
    print("✅ Database initialized")

    yield

    # Shutdown
    print("🛑 Shutting down JobPilot API...")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
JobPilot API - AI-powered job application assistant.

## Features

- **Document Ingestion**: Upload resumes and career documents → automatic chunking and embedding
- **RAG Retrieval**: Hybrid search (vector + keyword) with reranking
- **Agent Tools**: Web search, calendar, email drafting
- **Application Tracking**: Kanban-style job application management

## Authentication

All endpoints (except /health) require a Bearer token in the Authorization header.
Get your token from /auth/login or /auth/signup.
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware - allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(jobs_router)
app.include_router(agent_router)
app.include_router(agent_tools_router)
app.include_router(memory_router)


@app.get("/")
async def root():
    """Root endpoint - basic API info."""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }
