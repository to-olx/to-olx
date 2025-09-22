"""
Authentication endpoints.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    Token,
    PasswordChangeRequest,
)
from app.schemas.user import User as UserSchema
from app.services import analytics_service, EventType

router = APIRouter()


@router.post("/register", response_model=UserSchema)
async def register(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: RegisterRequest,
) -> Any:
    """
    Register a new user.
    """
    # Check if user already exists
    result = await db.execute(
        select(User).where(
            or_(User.email == user_in.email, User.username == user_in.username)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )
    
    # Create new user
    user = User(
        email=user_in.email,
        username=user_in.username,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_verified=False,  # Email verification can be implemented later
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Track signup event
    await analytics_service.track_event(
        event_type=EventType.USER_SIGNUP,
        user_id=user.id,
        properties={
            "username": user.username,
            "email": user.email,
        }
    )
    
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    OAuth2 compatible token login.
    """
    # Try to find user by username or email
    result = await db.execute(
        select(User).where(
            or_(User.username == form_data.username, User.email == form_data.username)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    
    # Create tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    # Track login event
    await analytics_service.track_event(
        event_type=EventType.USER_LOGIN,
        user_id=user.id,
        properties={
            "username": user.username,
        }
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    *,
    db: AsyncSession = Depends(get_db),
    token_data: RefreshTokenRequest,
) -> Any:
    """
    Refresh access token using refresh token.
    """
    try:
        payload = decode_token(token_data.refresh_token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if not user_id or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        
        # Get user
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive",
            )
        
        # Create new tokens
        access_token = create_access_token(subject=user.id)
        new_refresh_token = create_refresh_token(subject=user.id)
        
        # Track token refresh event
        await analytics_service.track_event(
            event_type=EventType.TOKEN_REFRESH,
            user_id=user.id,
        )
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


@router.post("/change-password")
async def change_password(
    *,
    db: AsyncSession = Depends(get_db),
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Change password for current user.
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()
    
    # Track password change event
    await analytics_service.track_event(
        event_type=EventType.PASSWORD_CHANGE,
        user_id=current_user.id,
    )
    
    return {"message": "Password updated successfully"}


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Logout current user.
    
    Note: This is a placeholder endpoint. In a stateless JWT system,
    logout is typically handled client-side by removing the token.
    For server-side logout, you would need to implement token blacklisting.
    """
    # Track logout event
    await analytics_service.track_event(
        event_type=EventType.USER_LOGOUT,
        user_id=current_user.id,
    )
    
    return {"message": "Successfully logged out"}