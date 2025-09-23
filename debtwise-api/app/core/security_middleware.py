"""
Enhanced security middleware for DebtWise API.
"""

import json
import re
from typing import Callable, Set

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security_improvements import (
    CSRFProtection,
    InputSanitizer,
    RateLimiter,
    SecurityHeaders,
    SecurityMonitor,
    SessionManager,
)

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add comprehensive security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Apply security headers
        SecurityHeaders.apply_headers(response)
        
        return response


class EnhancedRateLimitMiddleware(BaseHTTPMiddleware):
    """Enhanced rate limiting with different tiers for different operations."""
    
    # Endpoints that require stricter rate limiting
    AUTH_ENDPOINTS = {"/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"}
    WRITE_ENDPOINTS = {"POST", "PUT", "DELETE", "PATCH"}
    SENSITIVE_ENDPOINTS = {"/api/v1/users/profile", "/api/v1/debts", "/api/v1/insights"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply tiered rate limiting based on endpoint type."""
        # Skip rate limiting for health checks
        if request.url.path.startswith("/api/v1/health"):
            return await call_next(request)
        
        # Determine rate limit tier
        tier = self._determine_tier(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        rate_limit_status = await RateLimiter.check_rate_limit(
            key=client_id,
            tier=tier,
            increment=True,
        )
        
        if not rate_limit_status["allowed"]:
            # Log rate limit violation
            await SecurityMonitor.log_security_event(
                event_type="rate_limit_exceeded",
                user_id=getattr(request.state, "user_id", None),
                ip_address=request.client.host if request.client else None,
                details={
                    "tier": tier,
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "type": "rate_limit_exceeded",
                    "tier": tier,
                },
                headers={
                    "X-RateLimit-Limit": str(rate_limit_status["limit"]),
                    "X-RateLimit-Remaining": str(rate_limit_status["remaining"]),
                    "X-RateLimit-Reset": str(rate_limit_status["reset"]),
                    "Retry-After": str(rate_limit_status["reset"] - int(request.headers.get("X-Request-Time", "0"))),
                },
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_limit_status["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_status["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_limit_status["reset"])
        
        return response
    
    def _determine_tier(self, request: Request) -> str:
        """Determine rate limit tier based on request."""
        # Auth endpoints get strictest limits
        if request.url.path in self.AUTH_ENDPOINTS:
            return "auth"
        
        # Write operations
        if request.method in self.WRITE_ENDPOINTS:
            return "write"
        
        # Sensitive data endpoints
        for endpoint in self.SENSITIVE_ENDPOINTS:
            if request.url.path.startswith(endpoint):
                return "sensitive"
        
        # Default tier
        return "api"
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Prefer user ID if authenticated
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        
        # Fall back to IP address
        if request.client:
            return f"ip:{request.client.host}"
        
        # Last resort
        return "anonymous"


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate and sanitize input data."""
    
    # Paths to exclude from validation
    EXCLUDED_PATHS = {"/docs", "/redoc", "/openapi.json", "/api/v1/health"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate request data for security issues."""
        # Skip validation for excluded paths
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)
        
        # Check request headers for suspicious patterns
        suspicious_headers = self._check_headers(request.headers)
        if suspicious_headers:
            await SecurityMonitor.log_security_event(
                event_type="suspicious_headers",
                ip_address=request.client.host if request.client else None,
                details={"headers": suspicious_headers},
            )
        
        # Check URL parameters
        if request.query_params:
            validation_result = self._validate_query_params(dict(request.query_params))
            if not validation_result["is_valid"]:
                await SecurityMonitor.log_security_event(
                    event_type="invalid_query_params",
                    ip_address=request.client.host if request.client else None,
                    details=validation_result,
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "detail": "Invalid query parameters",
                        "type": "validation_error",
                        "issues": validation_result["issues"],
                    },
                )
        
        # For requests with body, validate content
        if request.method in {"POST", "PUT", "PATCH"}:
            try:
                # Store original body for later use
                body = await request.body()
                
                # Validate JSON body if content-type is JSON
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type and body:
                    try:
                        json_body = json.loads(body)
                        validation_result = self._validate_json_body(json_body)
                        if not validation_result["is_valid"]:
                            await SecurityMonitor.log_security_event(
                                event_type="invalid_request_body",
                                user_id=getattr(request.state, "user_id", None),
                                ip_address=request.client.host if request.client else None,
                                details=validation_result,
                            )
                            return JSONResponse(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                content={
                                    "detail": "Invalid request body",
                                    "type": "validation_error",
                                    "issues": validation_result["issues"],
                                },
                            )
                    except json.JSONDecodeError:
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={
                                "detail": "Invalid JSON in request body",
                                "type": "json_parse_error",
                            },
                        )
                
                # Reconstruct request with validated body
                async def receive():
                    return {"type": "http.request", "body": body}
                
                request._receive = receive
                
            except Exception as e:
                logger.error(f"Error validating request body: {e}")
        
        return await call_next(request)
    
    def _check_headers(self, headers: dict) -> list:
        """Check headers for suspicious patterns."""
        suspicious = []
        
        # Check for SQL injection in headers
        for header_name, header_value in headers.items():
            if self._contains_sql_injection(header_value):
                suspicious.append({
                    "header": header_name,
                    "pattern": "sql_injection",
                    "value": header_value[:100],  # Truncate for logging
                })
        
        # Check for oversized headers
        for header_name, header_value in headers.items():
            if len(header_value) > 8192:  # 8KB limit
                suspicious.append({
                    "header": header_name,
                    "pattern": "oversized",
                    "size": len(header_value),
                })
        
        return suspicious
    
    def _validate_query_params(self, params: dict) -> dict:
        """Validate query parameters."""
        issues = []
        
        for key, value in params.items():
            # Check parameter name
            if not re.match(r"^[a-zA-Z0-9_-]{1,100}$", key):
                issues.append(f"Invalid parameter name: {key}")
            
            # Check for SQL injection
            if self._contains_sql_injection(value):
                issues.append(f"Potential SQL injection in parameter: {key}")
            
            # Check for path traversal
            if "../" in value or "..\\"""" in value:
                issues.append(f"Path traversal attempt in parameter: {key}")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
        }
    
    def _validate_json_body(self, body: dict) -> dict:
        """Validate JSON request body."""
        issues = []
        
        def check_value(value: any, path: str = "") -> None:
            """Recursively check values for security issues."""
            if isinstance(value, str):
                # Check for SQL injection
                if self._contains_sql_injection(value):
                    issues.append(f"Potential SQL injection at {path}")
                
                # Check for XSS
                if self._contains_xss(value):
                    issues.append(f"Potential XSS at {path}")
                
                # Check for oversized strings
                if len(value) > 10000:  # 10KB limit for string fields
                    issues.append(f"Oversized string at {path}: {len(value)} chars")
            
            elif isinstance(value, dict):
                for k, v in value.items():
                    check_value(v, f"{path}.{k}" if path else k)
            
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    check_value(item, f"{path}[{i}]")
        
        check_value(body)
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
        }
    
    def _contains_sql_injection(self, value: str) -> bool:
        """Check if value contains SQL injection patterns."""
        for pattern in InputSanitizer.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    def _contains_xss(self, value: str) -> bool:
        """Check if value contains XSS patterns."""
        for pattern in InputSanitizer.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware for state-changing requests."""
    
    # Methods that require CSRF protection
    PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
    
    # Paths to exclude from CSRF protection
    EXCLUDED_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply CSRF protection to state-changing requests."""
        # Skip CSRF for excluded paths
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)
        
        # Skip CSRF for safe methods
        if request.method not in self.PROTECTED_METHODS:
            return await call_next(request)
        
        # Skip if user not authenticated
        if not hasattr(request.state, "user_id"):
            return await call_next(request)
        
        # Get CSRF token from header or form data
        csrf_token = request.headers.get("X-CSRF-Token")
        
        if not csrf_token and request.method == "POST":
            # Check form data for CSRF token
            if "multipart/form-data" in request.headers.get("content-type", ""):
                form = await request.form()
                csrf_token = form.get("csrf_token")
        
        if not csrf_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "CSRF token missing",
                    "type": "csrf_validation_failed",
                },
            )
        
        # Get session ID from request
        session_id = request.headers.get("X-Session-ID", "")
        
        # Validate CSRF token
        if not CSRFProtection.validate_csrf_token(session_id, csrf_token):
            await SecurityMonitor.log_security_event(
                event_type="csrf_validation_failed",
                user_id=request.state.user_id,
                ip_address=request.client.host if request.client else None,
                details={
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "Invalid CSRF token",
                    "type": "csrf_validation_failed",
                },
            )
        
        return await call_next(request)


class SessionValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate user sessions."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate session if user is authenticated."""
        # Only validate if user is authenticated
        if hasattr(request.state, "user_id"):
            session_id = request.headers.get("X-Session-ID")
            
            if session_id:
                # Validate session
                is_valid = await SessionManager.validate_session(
                    user_id=request.state.user_id,
                    session_id=session_id,
                    ip_address=request.client.host if request.client else None,
                )
                
                if not is_valid:
                    await SecurityMonitor.log_security_event(
                        event_type="invalid_session",
                        user_id=request.state.user_id,
                        ip_address=request.client.host if request.client else None,
                        details={"session_id": session_id},
                    )
                    
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={
                            "detail": "Invalid session",
                            "type": "session_validation_failed",
                        },
                    )
        
        return await call_next(request)


class AnomalyDetectionMiddleware(BaseHTTPMiddleware):
    """Middleware to detect anomalous behavior patterns."""
    
    # Suspicious patterns to track
    TRACKED_ACTIONS = {
        "failed_login": 5,  # Max 5 failed logins
        "password_reset": 3,  # Max 3 password resets
        "api_error_4xx": 20,  # Max 20 client errors
        "api_error_5xx": 10,  # Max 10 server errors
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor for anomalous behavior patterns."""
        response = await call_next(request)
        
        # Track failed authentication attempts
        if request.url.path == "/api/v1/auth/login" and response.status_code == 401:
            if hasattr(request.state, "user_id"):
                await self._track_suspicious_action(
                    request.state.user_id,
                    "failed_login",
                    request,
                )
        
        # Track client errors
        if 400 <= response.status_code < 500:
            if hasattr(request.state, "user_id"):
                await self._track_suspicious_action(
                    request.state.user_id,
                    "api_error_4xx",
                    request,
                )
        
        # Track server errors (might indicate attack attempts)
        if response.status_code >= 500:
            if hasattr(request.state, "user_id"):
                await self._track_suspicious_action(
                    request.state.user_id,
                    "api_error_5xx",
                    request,
                )
        
        return response
    
    async def _track_suspicious_action(
        self,
        user_id: int,
        action: str,
        request: Request,
    ) -> None:
        """Track suspicious action and check threshold."""
        threshold = self.TRACKED_ACTIONS.get(action, 10)
        
        is_suspicious = await SecurityMonitor.check_suspicious_activity(
            user_id=user_id,
            action=action,
            threshold=threshold,
        )
        
        if is_suspicious:
            # Could implement automatic account lockout here
            logger.warning(
                f"Suspicious activity threshold reached for user {user_id}: {action}",
                user_id=user_id,
                action=action,
                ip_address=request.client.host if request.client else None,
            )