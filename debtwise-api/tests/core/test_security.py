"""
Tests for security utilities.
"""

from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


@pytest.mark.unit
class TestSecurity:
    """Test security utilities."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        # Hash should be different from plain password
        assert hashed != password
        
        # Should verify correctly
        assert verify_password(password, hashed) is True
        
        # Should not verify with wrong password
        assert verify_password("wrongpassword", hashed) is False
    
    def test_create_access_token(self):
        """Test access token creation."""
        subject = "123"
        token = create_access_token(subject)
        
        # Decode and verify token
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        assert payload["sub"] == subject
        assert payload["type"] == "access"
        assert "exp" in payload
        
        # Check expiration is in the future
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        assert exp_datetime > datetime.now(timezone.utc)
    
    def test_create_access_token_with_custom_expiry(self):
        """Test access token creation with custom expiry."""
        subject = "123"
        expires_delta = timedelta(minutes=5)
        token = create_access_token(subject, expires_delta)
        
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Check expiration is approximately 5 minutes from now
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        expected_exp = datetime.now(timezone.utc) + expires_delta
        
        # Allow 1 second tolerance for test execution time
        assert abs((exp_datetime - expected_exp).total_seconds()) < 1
    
    def test_create_access_token_with_additional_claims(self):
        """Test access token creation with additional claims."""
        subject = "123"
        additional_claims = {"role": "admin", "department": "IT"}
        token = create_access_token(subject, additional_claims=additional_claims)
        
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        assert payload["role"] == "admin"
        assert payload["department"] == "IT"
    
    def test_create_refresh_token(self):
        """Test refresh token creation."""
        subject = "123"
        token = create_refresh_token(subject)
        
        # Decode and verify token
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        assert payload["sub"] == subject
        assert payload["type"] == "refresh"
        assert "exp" in payload
        
        # Check expiration is in the future (should be days, not minutes)
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        time_until_expiry = exp_datetime - datetime.now(timezone.utc)
        
        # Should be close to the configured days (allow some tolerance)
        expected_days = settings.refresh_token_expire_days
        assert expected_days - 1 < time_until_expiry.days <= expected_days
    
    def test_decode_valid_token(self):
        """Test decoding a valid token."""
        subject = "123"
        token = create_access_token(subject)
        
        payload = decode_token(token)
        assert payload["sub"] == subject
        assert payload["type"] == "access"
    
    def test_decode_invalid_token(self):
        """Test decoding an invalid token."""
        with pytest.raises(JWTError):
            decode_token("invalid.token.here")
    
    def test_decode_expired_token(self):
        """Test decoding an expired token."""
        subject = "123"
        # Create token that expires immediately
        token = create_access_token(subject, timedelta(seconds=-1))
        
        with pytest.raises(JWTError):
            decode_token(token)
    
    def test_decode_token_with_wrong_algorithm(self):
        """Test decoding a token with wrong algorithm."""
        subject = "123"
        # Create token with different algorithm
        token = jwt.encode(
            {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            settings.jwt_secret_key,
            algorithm="HS512"  # Different from configured algorithm
        )
        
        with pytest.raises(JWTError):
            decode_token(token)
    
    def test_token_subject_as_integer(self):
        """Test token creation with integer subject."""
        subject = 456
        token = create_access_token(subject)
        
        payload = decode_token(token)
        assert payload["sub"] == "456"  # Should be converted to string