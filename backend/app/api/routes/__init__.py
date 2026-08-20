"""
Routes package - exports all API routers.
"""

from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.agent import router as agent_router
from app.api.routes.agent_tools import router as agent_tools_router
from app.api.routes.memory import router as memory_router

__all__ = ["auth_router", "documents_router", "health_router", "jobs_router", "agent_router", "agent_tools_router", "memory_router"]
