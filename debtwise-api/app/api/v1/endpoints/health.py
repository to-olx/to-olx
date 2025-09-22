"""
Health check endpoints.
"""

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

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
    # TODO: Add actual database and Redis checks when implemented
    checks = {
        "database": "healthy",  # Placeholder
        "redis": "healthy",     # Placeholder
    }
    
    all_healthy = all(status == "healthy" for status in checks.values())
    
    return {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }