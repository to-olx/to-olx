"""
Authentication schemas.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class TokenBase(BaseModel):
    """Base token schema."""
    access_token: str
    token_type: str = "bearer"


class Token(TokenBase):
    """Token response schema."""
    refresh_token: str


class TokenPayload(BaseModel):
    """Token payload schema."""
    sub: str
    type: str
    exp: int


class LoginRequest(BaseModel):
    """Login request schema."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., min_length=8)


class RegisterRequest(BaseModel):
    """User registration request schema."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100, pattern="^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(None, max_length=255)


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""
    token: str
    new_password: str = Field(..., min_length=8)


class PasswordChangeRequest(BaseModel):
    """Password change request schema."""
    current_password: str
    new_password: str = Field(..., min_length=8)