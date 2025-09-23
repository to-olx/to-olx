"""
Main FastAPI application module.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.router import api_router
from app.core.middleware import (
    RequestIDMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    AnalyticsMiddleware,
)
from app.services import analytics_service
from app.core.db_init import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle application startup and shutdown events.
    """
    # Startup
    setup_logging()
    await analytics_service.initialize()
    # Initialize database tables
    await init_db()
    # TODO: Initialize Redis connection
    
    yield
    
    # Shutdown
    await analytics_service.shutdown()
    # TODO: Close database connections
    # TODO: Close Redis connections


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*.debtwise.com", "debtwise.com"]
        )
    
    # Add custom middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(AnalyticsMiddleware)
    
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1")
    
    return app


# Create the application instance
app = create_application()