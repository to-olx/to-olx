"""
Custom middleware for the application.
"""

import time
import uuid
from typing import Callable, Dict, Optional

import redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger, log_request, LogContext
from app.services import analytics_service, EventType

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add a unique request ID to each request."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID to request state and response headers."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        with LogContext(request_id=request_id):
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request details and response status."""
        start_time = time.time()
        
        # Log request
        logger.debug(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            log_request(
                logger,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_host=request.client.host if request.client else None,
            )
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=str(e),
                exc_info=True,
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to implement rate limiting using Redis."""
    
    def __init__(self, app):
        super().__init__(app)
        self.redis_client: Optional[redis.Redis] = None
        self.rate_limit = settings.rate_limit_per_minute
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit before processing request."""
        # Skip rate limiting for health check endpoints
        if request.url.path in ["/health", "/api/health", "/api/v1/health"]:
            return await call_next(request)
        
        # Get client identifier (IP address or user ID if authenticated)
        client_id = self._get_client_id(request)
        
        # Check rate limit
        if not await self._check_rate_limit(client_id):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "type": "rate_limit_exceeded",
                },
                headers={
                    "X-RateLimit-Limit": str(self.rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + 60),
                },
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = await self._get_remaining_requests(client_id)
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # TODO: Use user ID if authenticated
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        
        # Use IP address
        if request.client:
            return f"ip:{request.client.host}"
        
        return "anonymous"
    
    async def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit."""
        if not self.redis_client:
            try:
                self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            except Exception as e:
                logger.error("Failed to connect to Redis", error=str(e))
                # Allow request if Redis is not available
                return True
        
        try:
            key = f"rate_limit:{client_id}"
            current = self.redis_client.incr(key)
            
            if current == 1:
                # Set expiry for 1 minute
                self.redis_client.expire(key, 60)
            
            return current <= self.rate_limit
            
        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            # Allow request if rate limiting fails
            return True
    
    async def _get_remaining_requests(self, client_id: str) -> int:
        """Get remaining requests for client."""
        if not self.redis_client:
            return self.rate_limit
        
        try:
            key = f"rate_limit:{client_id}"
            current = self.redis_client.get(key)
            
            if current is None:
                return self.rate_limit
            
            remaining = max(0, self.rate_limit - int(current))
            return remaining
            
        except Exception:
            return self.rate_limit


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """Middleware to track analytics for API requests."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track API request analytics."""
        start_time = time.time()
        
        # Get user info if available
        user_id = None
        if hasattr(request.state, "user_id"):
            user_id = request.state.user_id
        
        # Get request metadata
        client_host = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        session_id = request.headers.get("x-session-id") or str(uuid.uuid4())
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Track successful request
            await analytics_service.track_event(
                event_type=EventType.API_REQUEST,
                user_id=user_id,
                properties={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "query_params": dict(request.query_params),
                },
                session_id=session_id,
                ip_address=client_host,
                user_agent=user_agent,
            )
            
            # Track rate limit hits
            if response.status_code == 429:
                await analytics_service.track_event(
                    event_type=EventType.RATE_LIMIT_HIT,
                    user_id=user_id,
                    properties={
                        "path": request.url.path,
                    },
                    session_id=session_id,
                    ip_address=client_host,
                )
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Track error
            await analytics_service.track_event(
                event_type=EventType.API_ERROR,
                user_id=user_id,
                properties={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": duration_ms,
                },
                session_id=session_id,
                ip_address=client_host,
                user_agent=user_agent,
            )
            
            raise