"""
Enhanced security implementations for DebtWise API.
Addresses OWASP Top 10 and financial app-specific security concerns.
"""

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, SecretStr, validator

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis_client

logger = get_logger(__name__)

# Enhanced password context with stronger hashing
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__rounds=4,
    argon2__memory_cost=65536,
    argon2__parallelism=2,
    bcrypt__rounds=14,
)

# OAuth2 scheme with auto_error disabled for better error handling
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


class SecurityHeaders:
    """Security headers to be added to all responses."""
    
    HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
    }
    
    CSP_POLICY = {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src": "'self' 'unsafe-inline'",
        "img-src": "'self' data: https:",
        "font-src": "'self' data:",
        "connect-src": "'self'",
        "frame-ancestors": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'",
    }
    
    @classmethod
    def get_csp_header(cls) -> str:
        """Generate Content-Security-Policy header."""
        return "; ".join(f"{key} {value}" for key, value in cls.CSP_POLICY.items())
    
    @classmethod
    def apply_headers(cls, response: Response) -> Response:
        """Apply security headers to response."""
        for header, value in cls.HEADERS.items():
            response.headers[header] = value
        response.headers["Content-Security-Policy"] = cls.get_csp_header()
        
        # Add HSTS header for production
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        return response


class TokenBlacklist:
    """Manage blacklisted tokens for logout and revocation."""
    
    @staticmethod
    async def add_token(token: str, expires_at: datetime) -> None:
        """Add token to blacklist."""
        redis_client = await get_redis_client()
        if not redis_client:
            logger.error("Redis not available for token blacklist")
            return
        
        key = f"token_blacklist:{token}"
        ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        
        if ttl > 0:
            await redis_client.setex(key, ttl, "1")
    
    @staticmethod
    async def is_blacklisted(token: str) -> bool:
        """Check if token is blacklisted."""
        redis_client = await get_redis_client()
        if not redis_client:
            # If Redis is unavailable, consider tokens valid to prevent DOS
            return False
        
        key = f"token_blacklist:{token}"
        return await redis_client.exists(key) > 0


class SessionManager:
    """Manage user sessions with enhanced security."""
    
    @staticmethod
    async def create_session(
        user_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Create a new session for user."""
        session_id = secrets.token_urlsafe(32)
        redis_client = await get_redis_client()
        
        if redis_client:
            session_data = {
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ip_address": ip_address,
                "user_agent": user_agent,
                "last_activity": datetime.now(timezone.utc).isoformat(),
            }
            
            key = f"session:{user_id}:{session_id}"
            await redis_client.hset(key, mapping=session_data)
            await redis_client.expire(key, 86400)  # 24 hours
            
            # Track active sessions per user
            user_sessions_key = f"user_sessions:{user_id}"
            await redis_client.sadd(user_sessions_key, session_id)
            await redis_client.expire(user_sessions_key, 86400)
        
        return session_id
    
    @staticmethod
    async def validate_session(
        user_id: int,
        session_id: str,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Validate session and check for anomalies."""
        redis_client = await get_redis_client()
        if not redis_client:
            return True  # Graceful degradation
        
        key = f"session:{user_id}:{session_id}"
        session_data = await redis_client.hgetall(key)
        
        if not session_data:
            return False
        
        # Check IP address consistency
        if ip_address and session_data.get(b"ip_address"):
            if session_data[b"ip_address"].decode() != ip_address:
                logger.warning(
                    f"Session IP mismatch for user {user_id}: "
                    f"expected {session_data[b'ip_address'].decode()}, got {ip_address}"
                )
                # Could implement IP change notification here
        
        # Update last activity
        await redis_client.hset(key, b"last_activity", datetime.now(timezone.utc).isoformat())
        await redis_client.expire(key, 86400)
        
        return True
    
    @staticmethod
    async def revoke_all_sessions(user_id: int) -> None:
        """Revoke all sessions for a user."""
        redis_client = await get_redis_client()
        if not redis_client:
            return
        
        user_sessions_key = f"user_sessions:{user_id}"
        session_ids = await redis_client.smembers(user_sessions_key)
        
        for session_id in session_ids:
            key = f"session:{user_id}:{session_id.decode()}"
            await redis_client.delete(key)
        
        await redis_client.delete(user_sessions_key)


class RateLimiter:
    """Enhanced rate limiter with different tiers and actions."""
    
    TIERS = {
        "auth": {"limit": 5, "window": 300},  # 5 attempts per 5 minutes
        "api": {"limit": 60, "window": 60},    # 60 requests per minute
        "write": {"limit": 30, "window": 60},  # 30 write operations per minute
        "sensitive": {"limit": 10, "window": 60},  # 10 sensitive operations per minute
    }
    
    @classmethod
    async def check_rate_limit(
        cls,
        key: str,
        tier: str = "api",
        increment: bool = True,
    ) -> Dict[str, Any]:
        """Check and optionally increment rate limit."""
        redis_client = await get_redis_client()
        if not redis_client:
            return {"allowed": True, "remaining": -1, "reset": 0}
        
        config = cls.TIERS.get(tier, cls.TIERS["api"])
        redis_key = f"rate_limit:{tier}:{key}"
        
        try:
            if increment:
                current = await redis_client.incr(redis_key)
                if current == 1:
                    await redis_client.expire(redis_key, config["window"])
            else:
                current_bytes = await redis_client.get(redis_key)
                current = int(current_bytes) if current_bytes else 0
            
            ttl = await redis_client.ttl(redis_key)
            reset_time = int(time.time()) + (ttl if ttl > 0 else config["window"])
            
            return {
                "allowed": current <= config["limit"],
                "remaining": max(0, config["limit"] - current),
                "reset": reset_time,
                "limit": config["limit"],
            }
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return {"allowed": True, "remaining": -1, "reset": 0}


class InputSanitizer:
    """Input validation and sanitization utilities."""
    
    # Common SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
        r"(--|#|\/\*|\*\/)",
        r"(\bor\b\s*\d+\s*=\s*\d+)",
        r"(\band\b\s*\d+\s*=\s*\d+)",
        r"(;|'|\")",
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
        r"<object[^>]*>",
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 1000) -> str:
        """Sanitize string input."""
        if not value:
            return ""
        
        # Truncate to max length
        value = value[:max_length]
        
        # Remove null bytes
        value = value.replace("\x00", "")
        
        # Normalize whitespace
        value = " ".join(value.split())
        
        return value
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))
    
    @classmethod
    def validate_password_strength(cls, password: str) -> Dict[str, Any]:
        """Validate password strength."""
        issues = []
        
        if len(password) < 8:
            issues.append("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            issues.append("Password must contain at least one number")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            issues.append("Password must contain at least one special character")
        
        # Check for common passwords
        common_passwords = ["password", "12345678", "qwerty", "abc123", "password123"]
        if password.lower() in common_passwords:
            issues.append("Password is too common")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "score": max(0, 5 - len(issues)),
        }


class CSRFProtection:
    """CSRF protection utilities."""
    
    @staticmethod
    def generate_csrf_token(session_id: str) -> str:
        """Generate CSRF token for session."""
        timestamp = str(int(time.time()))
        message = f"{session_id}:{timestamp}".encode()
        signature = hmac.new(
            settings.secret_key.encode(),
            message,
            hashlib.sha256
        ).hexdigest()
        return f"{timestamp}:{signature}"
    
    @staticmethod
    def validate_csrf_token(session_id: str, token: str) -> bool:
        """Validate CSRF token."""
        try:
            timestamp, signature = token.split(":")
            
            # Check token age (1 hour max)
            token_age = int(time.time()) - int(timestamp)
            if token_age > 3600:
                return False
            
            # Verify signature
            message = f"{session_id}:{timestamp}".encode()
            expected_signature = hmac.new(
                settings.secret_key.encode(),
                message,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception:
            return False


class DataEncryption:
    """Utilities for encrypting sensitive data at rest."""
    
    @staticmethod
    def encrypt_field(value: str, user_id: int) -> str:
        """Encrypt a field value for storage."""
        # This is a placeholder - in production, use proper encryption like Fernet
        # from cryptography.fernet import Fernet
        # For demo purposes, we'll just base64 encode with a prefix
        import base64
        encoded = base64.b64encode(f"{user_id}:{value}".encode()).decode()
        return f"enc:{encoded}"
    
    @staticmethod
    def decrypt_field(encrypted_value: str, user_id: int) -> str:
        """Decrypt a field value from storage."""
        if not encrypted_value.startswith("enc:"):
            return encrypted_value
        
        import base64
        try:
            decoded = base64.b64decode(encrypted_value[4:]).decode()
            stored_user_id, value = decoded.split(":", 1)
            
            if str(user_id) != stored_user_id:
                raise ValueError("User ID mismatch")
            
            return value
        except Exception:
            raise ValueError("Failed to decrypt value")


class SecurityMonitor:
    """Monitor and alert on security events."""
    
    SUSPICIOUS_PATTERNS = {
        "sql_injection_attempt": r"(\b(union|select|drop)\b.*\b(from|table)\b)",
        "path_traversal": r"\.\./|\.\.\\",
        "command_injection": r"[;&|`]|\$\(",
        "xxe_attempt": r"<!ENTITY|SYSTEM|PUBLIC",
    }
    
    @classmethod
    async def log_security_event(
        cls,
        event_type: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log security event for monitoring."""
        logger.warning(
            f"SECURITY_EVENT: {event_type}",
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        # Could also send to external monitoring service
        redis_client = await get_redis_client()
        if redis_client:
            event = {
                "type": event_type,
                "user_id": user_id,
                "ip_address": ip_address,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # Store in Redis for real-time monitoring
            await redis_client.lpush("security_events", str(event))
            await redis_client.ltrim("security_events", 0, 9999)  # Keep last 10k events
    
    @classmethod
    async def check_suspicious_activity(
        cls,
        user_id: int,
        action: str,
        threshold: int = 10,
    ) -> bool:
        """Check if user has suspicious activity patterns."""
        redis_client = await get_redis_client()
        if not redis_client:
            return False
        
        key = f"suspicious_activity:{user_id}:{action}"
        count = await redis_client.incr(key)
        
        if count == 1:
            await redis_client.expire(key, 3600)  # 1 hour window
        
        if count >= threshold:
            await cls.log_security_event(
                "suspicious_activity_threshold",
                user_id=user_id,
                details={"action": action, "count": count},
            )
            return True
        
        return False


# Export enhanced security functions
async def create_secure_token(
    subject: Union[str, int],
    token_type: str = "access",
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a secure JWT token with additional security features."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        if token_type == "access":
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.access_token_expire_minutes
            )
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=settings.refresh_token_expire_days
            )
    
    # Add security claims
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": token_type,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16),  # Unique token ID
    }
    
    if additional_claims:
        to_encode.update(additional_claims)
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


async def verify_secure_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """Verify token with additional security checks."""
    try:
        # Check if token is blacklisted
        if await TokenBlacklist.is_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )
        
        # Decode token
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Verify token type
        if payload.get("type") != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {expected_type}",
            )
        
        # Check if token has required claims
        required_claims = ["exp", "sub", "type", "iat", "jti"]
        for claim in required_claims:
            if claim not in payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token missing required claim: {claim}",
                )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
        )


def hash_password_secure(password: str) -> str:
    """Hash password with secure algorithm."""
    # Validate password strength
    validation = InputSanitizer.validate_password_strength(password)
    if not validation["is_valid"]:
        raise ValueError(f"Weak password: {', '.join(validation['issues'])}")
    
    return pwd_context.hash(password)


def verify_password_secure(plain_password: str, hashed_password: str) -> bool:
    """Verify password with timing attack protection."""
    return pwd_context.verify(plain_password, hashed_password)