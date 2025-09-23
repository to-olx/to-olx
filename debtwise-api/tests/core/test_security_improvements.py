"""
Tests for enhanced security implementations.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.security_improvements import (
    CSRFProtection,
    DataEncryption,
    InputSanitizer,
    RateLimiter,
    SecurityHeaders,
    SecurityMonitor,
    SessionManager,
    TokenBlacklist,
    create_secure_token,
    hash_password_secure,
    verify_password_secure,
    verify_secure_token,
)


class TestSecurityHeaders:
    """Test security headers functionality."""
    
    def test_get_csp_header(self):
        """Test CSP header generation."""
        csp = SecurityHeaders.get_csp_header()
        
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
    
    def test_apply_headers(self):
        """Test applying security headers to response."""
        # Mock response
        response = MagicMock()
        response.headers = {}
        
        # Apply headers
        SecurityHeaders.apply_headers(response)
        
        # Check headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Content-Security-Policy" in response.headers
    
    def test_apply_headers_production(self):
        """Test HSTS header in production."""
        with patch("app.core.security_improvements.settings.is_production", True):
            response = MagicMock()
            response.headers = {}
            
            SecurityHeaders.apply_headers(response)
            
            assert "Strict-Transport-Security" in response.headers
            assert "max-age=31536000" in response.headers["Strict-Transport-Security"]


class TestTokenBlacklist:
    """Test token blacklist functionality."""
    
    @pytest.mark.asyncio
    async def test_add_token(self, mock_redis_client):
        """Test adding token to blacklist."""
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            await TokenBlacklist.add_token("test-token", expires_at)
            
            # Check Redis call
            mock_redis_client.setex.assert_called_once()
            call_args = mock_redis_client.setex.call_args
            assert call_args[0][0] == "token_blacklist:test-token"
            assert call_args[0][2] == "1"
    
    @pytest.mark.asyncio
    async def test_is_blacklisted_true(self, mock_redis_client):
        """Test checking blacklisted token."""
        mock_redis_client.exists.return_value = 1
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            result = await TokenBlacklist.is_blacklisted("test-token")
            
            assert result is True
            mock_redis_client.exists.assert_called_once_with("token_blacklist:test-token")
    
    @pytest.mark.asyncio
    async def test_is_blacklisted_false(self, mock_redis_client):
        """Test checking non-blacklisted token."""
        mock_redis_client.exists.return_value = 0
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            result = await TokenBlacklist.is_blacklisted("test-token")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_is_blacklisted_no_redis(self):
        """Test blacklist check when Redis is unavailable."""
        with patch("app.core.security_improvements.get_redis_client", return_value=None):
            result = await TokenBlacklist.is_blacklisted("test-token")
            
            # Should return False for graceful degradation
            assert result is False


class TestSessionManager:
    """Test session management functionality."""
    
    @pytest.mark.asyncio
    async def test_create_session(self, mock_redis_client):
        """Test creating a new session."""
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            session_id = await SessionManager.create_session(
                user_id=1,
                ip_address="127.0.0.1",
                user_agent="TestAgent",
            )
            
            assert session_id
            assert len(session_id) > 20
            
            # Check Redis calls
            mock_redis_client.hset.assert_called_once()
            mock_redis_client.expire.assert_called()
            mock_redis_client.sadd.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_session_valid(self, mock_redis_client):
        """Test validating a valid session."""
        mock_redis_client.hgetall.return_value = {
            b"user_id": b"1",
            b"ip_address": b"127.0.0.1",
            b"created_at": datetime.now(timezone.utc).isoformat().encode(),
        }
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            result = await SessionManager.validate_session(
                user_id=1,
                session_id="test-session",
                ip_address="127.0.0.1",
            )
            
            assert result is True
            mock_redis_client.hset.assert_called()  # Updates last_activity
    
    @pytest.mark.asyncio
    async def test_validate_session_ip_mismatch(self, mock_redis_client):
        """Test session validation with IP mismatch."""
        mock_redis_client.hgetall.return_value = {
            b"user_id": b"1",
            b"ip_address": b"127.0.0.1",
        }
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            with patch("app.core.security_improvements.logger") as mock_logger:
                result = await SessionManager.validate_session(
                    user_id=1,
                    session_id="test-session",
                    ip_address="192.168.1.1",  # Different IP
                )
                
                assert result is True  # Still valid but logs warning
                mock_logger.warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_revoke_all_sessions(self, mock_redis_client):
        """Test revoking all user sessions."""
        mock_redis_client.smembers.return_value = {b"session1", b"session2"}
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            await SessionManager.revoke_all_sessions(user_id=1)
            
            # Check Redis calls
            mock_redis_client.smembers.assert_called_once_with("user_sessions:1")
            assert mock_redis_client.delete.call_count == 3  # 2 sessions + user_sessions key


class TestRateLimiter:
    """Test enhanced rate limiter functionality."""
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, mock_redis_client):
        """Test rate limit check when allowed."""
        mock_redis_client.incr.return_value = 1
        mock_redis_client.ttl.return_value = 30
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            result = await RateLimiter.check_rate_limit("test-key", tier="api")
            
            assert result["allowed"] is True
            assert result["remaining"] == 59  # 60 - 1
            assert result["limit"] == 60
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, mock_redis_client):
        """Test rate limit check when exceeded."""
        mock_redis_client.incr.return_value = 61  # Over limit
        mock_redis_client.ttl.return_value = 30
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            result = await RateLimiter.check_rate_limit("test-key", tier="api")
            
            assert result["allowed"] is False
            assert result["remaining"] == 0
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_auth_tier(self, mock_redis_client):
        """Test rate limit with auth tier."""
        mock_redis_client.incr.return_value = 3
        mock_redis_client.ttl.return_value = 200
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            result = await RateLimiter.check_rate_limit("test-key", tier="auth")
            
            assert result["allowed"] is True
            assert result["remaining"] == 2  # 5 - 3
            assert result["limit"] == 5
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_no_increment(self, mock_redis_client):
        """Test rate limit check without incrementing."""
        mock_redis_client.get.return_value = b"10"
        mock_redis_client.ttl.return_value = 30
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            result = await RateLimiter.check_rate_limit(
                "test-key",
                tier="api",
                increment=False
            )
            
            assert result["allowed"] is True
            assert result["remaining"] == 50  # 60 - 10
            mock_redis_client.incr.assert_not_called()


class TestInputSanitizer:
    """Test input validation and sanitization."""
    
    def test_sanitize_string(self):
        """Test string sanitization."""
        # Test null byte removal
        result = InputSanitizer.sanitize_string("test\x00string")
        assert result == "test string"
        
        # Test whitespace normalization
        result = InputSanitizer.sanitize_string("test   \n\t  string")
        assert result == "test string"
        
        # Test max length
        long_string = "a" * 2000
        result = InputSanitizer.sanitize_string(long_string, max_length=100)
        assert len(result) == 100
    
    def test_validate_email(self):
        """Test email validation."""
        # Valid emails
        assert InputSanitizer.validate_email("user@example.com") is True
        assert InputSanitizer.validate_email("test.user+tag@domain.co.uk") is True
        
        # Invalid emails
        assert InputSanitizer.validate_email("invalid") is False
        assert InputSanitizer.validate_email("@example.com") is False
        assert InputSanitizer.validate_email("user@") is False
        assert InputSanitizer.validate_email("user@.com") is False
    
    def test_validate_password_strength(self):
        """Test password strength validation."""
        # Strong password
        result = InputSanitizer.validate_password_strength("StrongP@ssw0rd!")
        assert result["is_valid"] is True
        assert result["score"] == 5
        
        # Weak passwords
        result = InputSanitizer.validate_password_strength("password")
        assert result["is_valid"] is False
        assert "uppercase" in str(result["issues"])
        assert "number" in str(result["issues"])
        assert "special" in str(result["issues"])
        
        # Common password
        result = InputSanitizer.validate_password_strength("Password123!")
        assert result["is_valid"] is False  # Contains "password"


class TestCSRFProtection:
    """Test CSRF protection utilities."""
    
    def test_generate_csrf_token(self):
        """Test CSRF token generation."""
        token = CSRFProtection.generate_csrf_token("test-session")
        
        assert token
        assert ":" in token
        
        # Token should be different each time due to timestamp
        token2 = CSRFProtection.generate_csrf_token("test-session")
        assert token != token2
    
    def test_validate_csrf_token_valid(self):
        """Test valid CSRF token validation."""
        token = CSRFProtection.generate_csrf_token("test-session")
        
        # Should be valid immediately
        assert CSRFProtection.validate_csrf_token("test-session", token) is True
    
    def test_validate_csrf_token_invalid_session(self):
        """Test CSRF token with wrong session."""
        token = CSRFProtection.generate_csrf_token("session1")
        
        # Should fail with different session
        assert CSRFProtection.validate_csrf_token("session2", token) is False
    
    def test_validate_csrf_token_expired(self):
        """Test expired CSRF token."""
        # Mock time to create old token
        with patch("time.time", return_value=1000):
            token = CSRFProtection.generate_csrf_token("test-session")
        
        # Mock current time to be 2 hours later
        with patch("time.time", return_value=8200):  # 1000 + 7200
            assert CSRFProtection.validate_csrf_token("test-session", token) is False
    
    def test_validate_csrf_token_malformed(self):
        """Test malformed CSRF token."""
        assert CSRFProtection.validate_csrf_token("session", "invalid") is False
        assert CSRFProtection.validate_csrf_token("session", "") is False


class TestDataEncryption:
    """Test data encryption utilities."""
    
    def test_encrypt_decrypt_field(self):
        """Test field encryption and decryption."""
        original_value = "sensitive data"
        user_id = 123
        
        # Encrypt
        encrypted = DataEncryption.encrypt_field(original_value, user_id)
        assert encrypted.startswith("enc:")
        assert encrypted != original_value
        
        # Decrypt
        decrypted = DataEncryption.decrypt_field(encrypted, user_id)
        assert decrypted == original_value
    
    def test_decrypt_field_wrong_user(self):
        """Test decryption with wrong user ID."""
        encrypted = DataEncryption.encrypt_field("data", user_id=123)
        
        with pytest.raises(ValueError, match="User ID mismatch"):
            DataEncryption.decrypt_field(encrypted, user_id=456)
    
    def test_decrypt_field_not_encrypted(self):
        """Test decryption of non-encrypted value."""
        plain_value = "not encrypted"
        result = DataEncryption.decrypt_field(plain_value, user_id=123)
        assert result == plain_value


class TestSecurityMonitor:
    """Test security monitoring functionality."""
    
    @pytest.mark.asyncio
    async def test_log_security_event(self, mock_redis_client):
        """Test logging security events."""
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            with patch("app.core.security_improvements.logger") as mock_logger:
                await SecurityMonitor.log_security_event(
                    event_type="test_event",
                    user_id=1,
                    ip_address="127.0.0.1",
                    details={"test": "data"},
                )
                
                # Check logger call
                mock_logger.warning.assert_called_once()
                
                # Check Redis call
                mock_redis_client.lpush.assert_called_once()
                mock_redis_client.ltrim.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_suspicious_activity_below_threshold(self, mock_redis_client):
        """Test suspicious activity check below threshold."""
        mock_redis_client.incr.return_value = 5
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            result = await SecurityMonitor.check_suspicious_activity(
                user_id=1,
                action="test_action",
                threshold=10,
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_check_suspicious_activity_threshold_reached(self, mock_redis_client):
        """Test suspicious activity check at threshold."""
        mock_redis_client.incr.return_value = 10
        
        with patch("app.core.security_improvements.get_redis_client", return_value=mock_redis_client):
            with patch.object(SecurityMonitor, "log_security_event") as mock_log:
                result = await SecurityMonitor.check_suspicious_activity(
                    user_id=1,
                    action="test_action",
                    threshold=10,
                )
                
                assert result is True
                mock_log.assert_called_once()


class TestSecureTokenFunctions:
    """Test secure token creation and verification."""
    
    @pytest.mark.asyncio
    async def test_create_secure_token(self):
        """Test creating secure JWT token."""
        token = await create_secure_token(
            subject=123,
            token_type="access",
            additional_claims={"role": "user"},
        )
        
        # Decode to verify
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        assert payload["sub"] == "123"
        assert payload["type"] == "access"
        assert payload["role"] == "user"
        assert "jti" in payload  # Unique token ID
        assert "iat" in payload  # Issued at
        assert "exp" in payload  # Expiration
    
    @pytest.mark.asyncio
    async def test_verify_secure_token_valid(self):
        """Test verifying valid secure token."""
        token = await create_secure_token(subject=123, token_type="access")
        
        with patch("app.core.security_improvements.TokenBlacklist.is_blacklisted", return_value=False):
            payload = await verify_secure_token(token, expected_type="access")
            
            assert payload["sub"] == "123"
            assert payload["type"] == "access"
    
    @pytest.mark.asyncio
    async def test_verify_secure_token_blacklisted(self):
        """Test verifying blacklisted token."""
        token = await create_secure_token(subject=123)
        
        with patch("app.core.security_improvements.TokenBlacklist.is_blacklisted", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await verify_secure_token(token)
            
            assert exc_info.value.status_code == 401
            assert "revoked" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_verify_secure_token_wrong_type(self):
        """Test verifying token with wrong type."""
        token = await create_secure_token(subject=123, token_type="refresh")
        
        with patch("app.core.security_improvements.TokenBlacklist.is_blacklisted", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await verify_secure_token(token, expected_type="access")
            
            assert exc_info.value.status_code == 401
            assert "Invalid token type" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_verify_secure_token_missing_claims(self):
        """Test verifying token with missing claims."""
        # Create token without required claims
        payload = {"sub": "123", "exp": time.time() + 3600}
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        
        with patch("app.core.security_improvements.TokenBlacklist.is_blacklisted", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await verify_secure_token(token)
            
            assert exc_info.value.status_code == 401
            assert "missing required claim" in exc_info.value.detail


class TestPasswordFunctions:
    """Test secure password functions."""
    
    def test_hash_password_secure_valid(self):
        """Test hashing valid password."""
        password = "StrongP@ssw0rd123!"
        hashed = hash_password_secure(password)
        
        assert hashed
        assert hashed != password
        assert hashed.startswith("$argon2") or hashed.startswith("$2")  # Argon2 or bcrypt
    
    def test_hash_password_secure_weak(self):
        """Test hashing weak password."""
        with pytest.raises(ValueError, match="Weak password"):
            hash_password_secure("weak")
    
    def test_verify_password_secure_correct(self):
        """Test verifying correct password."""
        password = "StrongP@ssw0rd123!"
        hashed = hash_password_secure(password)
        
        assert verify_password_secure(password, hashed) is True
    
    def test_verify_password_secure_incorrect(self):
        """Test verifying incorrect password."""
        password = "StrongP@ssw0rd123!"
        hashed = hash_password_secure(password)
        
        assert verify_password_secure("WrongPassword123!", hashed) is False


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    client = AsyncMock()
    client.setex = AsyncMock()
    client.exists = AsyncMock(return_value=0)
    client.get = AsyncMock(return_value=None)
    client.hset = AsyncMock()
    client.hgetall = AsyncMock(return_value={})
    client.expire = AsyncMock()
    client.sadd = AsyncMock()
    client.smembers = AsyncMock(return_value=set())
    client.delete = AsyncMock()
    client.incr = AsyncMock(return_value=1)
    client.ttl = AsyncMock(return_value=60)
    client.lpush = AsyncMock()
    client.ltrim = AsyncMock()
    return client