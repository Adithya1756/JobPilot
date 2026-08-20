"""
Health check routes for monitoring and deployment.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Basic health check endpoint.

    Returns 200 if the service is running and can connect to the database.
    """
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": f"error: {str(e)}"}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness check for Kubernetes/deployment systems.

    Verifies all critical dependencies are available.
    """
    checks = {}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ready"
    except Exception as e:
        checks["database"] = f"not ready: {str(e)}"

    # pgvector extension check
    try:
        result = await db.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
        row = result.scalar_one_or_none()
        if row:
            checks["pgvector"] = f"ready (v{row})"
        else:
            checks["pgvector"] = "not installed"
    except Exception as e:
        checks["pgvector"] = f"error: {str(e)}"

    all_ready = all(v == "ready" or v.startswith("ready") for v in checks.values())

    if all_ready:
        return {"status": "ready", "checks": checks}
    else:
        return {"status": "not ready", "checks": checks}
