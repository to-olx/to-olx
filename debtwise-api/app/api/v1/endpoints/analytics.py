"""
Analytics endpoints for retrieving user activity data.
"""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_active_user, get_current_superuser
from app.models.user import User
from app.services import analytics_service, EventType

router = APIRouter()


@router.get("/events/count")
async def get_event_count(
    event_type: EventType,
    date: Optional[datetime] = Query(None, description="Date to get count for (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Get event count for a specific type and date (superuser only).
    """
    count = await analytics_service.get_event_count(event_type, date)
    return {
        "event_type": event_type,
        "date": date.isoformat() if date else datetime.now().date().isoformat(),
        "count": count,
    }


@router.get("/user/me/events")
async def get_my_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get current user's analytics events.
    """
    events = await analytics_service.get_user_events(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    
    return {
        "events": [event.dict() for event in events],
        "count": len(events),
        "limit": limit,
        "offset": offset,
    }


@router.get("/user/{user_id}/events")
async def get_user_events(
    user_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Get specific user's analytics events (superuser only).
    """
    events = await analytics_service.get_user_events(
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    
    return {
        "user_id": user_id,
        "events": [event.dict() for event in events],
        "count": len(events),
        "limit": limit,
        "offset": offset,
    }