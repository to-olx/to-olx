"""
User schemas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: bool = True
    is_verified: bool = False


class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """User update schema."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=20)


class UserInDB(UserBase):
    """User in database schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    hashed_password: str
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class User(UserBase):
    """User response schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    phone_number: Optional[str] = None


class UserMe(User):
    """Current user response schema with additional fields."""
    pass