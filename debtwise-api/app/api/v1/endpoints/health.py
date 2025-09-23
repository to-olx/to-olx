"""
Health check endpoints.
"""

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import is_database_healthy
from app.core.redis import is_redis_healthy

router = APIRouter()


@router.get("")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.
    
    Returns:
        Dict[str, str]: Health status and timestamp.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/ready")
async def readiness_check() -> Dict[str, str]:
    """
    Readiness check endpoint that verifies all services are ready.
    
    Returns:
        Dict[str, str]: Readiness status.
    """
    # Check database health
    db_healthy = await is_database_healthy()
    
    # Check Redis health
    redis_healthy = await is_redis_healthy()
    
    checks = {
        "database": "healthy" if db_healthy else "unhealthy",
        "redis": "healthy" if redis_healthy else "unhealthy",
    }
    
    all_healthy = all(status == "healthy" for status in checks.values())
    
    return {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }