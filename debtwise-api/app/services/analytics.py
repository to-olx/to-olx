"""
Analytics service for tracking user interactions and system events.
"""

import asyncio
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis_client

logger = get_logger(__name__)


class EventType(str, Enum):
    """Analytics event types."""
    
    # Authentication events
    USER_SIGNUP = "user.signup"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    PASSWORD_CHANGE = "user.password_change"
    PASSWORD_RESET = "user.password_reset"
    TOKEN_REFRESH = "auth.token_refresh"
    
    # User activity events
    PROFILE_VIEW = "user.profile_view"
    PROFILE_UPDATE = "user.profile_update"
    USER_DELETE = "user.delete"
    
    # API events
    API_REQUEST = "api.request"
    API_ERROR = "api.error"
    RATE_LIMIT_HIT = "api.rate_limit_hit"
    
    # Financial events (for future use)
    TRANSACTION_CREATE = "transaction.create"
    TRANSACTION_UPDATE = "transaction.update"
    TRANSACTION_DELETE = "transaction.delete"
    BUDGET_CREATE = "budget.create"
    BUDGET_UPDATE = "budget.update"
    DEBT_CREATE = "debt.create"
    DEBT_UPDATE = "debt.update"
    DEBT_PAYMENT = "debt.payment"


class AnalyticsEvent(BaseModel):
    """Analytics event model."""
    
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    user_id: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    properties: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AnalyticsService:
    """Service for handling analytics events."""
    
    def __init__(self):
        self._event_queue: List[AnalyticsEvent] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._is_initialized = False
    
    async def initialize(self) -> None:
        """Initialize the analytics service."""
        if self._is_initialized:
            return
        
        # Start background flush task
        if settings.analytics_enabled:
            self._flush_task = asyncio.create_task(self._periodic_flush())
        
        self._is_initialized = True
        logger.info("Analytics service initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the analytics service."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining events
        await self._flush_events()
        
        logger.info("Analytics service shutdown")
    
    async def track_event(
        self,
        event_type: EventType,
        user_id: Optional[int] = None,
        properties: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Track an analytics event.
        
        Args:
            event_type: Type of the event
            user_id: ID of the user (if authenticated)
            properties: Additional event properties
            session_id: Session identifier
            ip_address: Client IP address
            user_agent: Client user agent
        """
        if not settings.analytics_enabled:
            return
        
        event = AnalyticsEvent(
            event_type=event_type,
            user_id=user_id,
            properties=properties or {},
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Add to queue
        self._event_queue.append(event)
        
        # Flush if batch size reached
        if len(self._event_queue) >= settings.analytics_batch_size:
            await self._flush_events()
    
    async def _flush_events(self) -> None:
        """Flush events to Redis."""
        if not self._event_queue:
            return
        
        redis_client = await get_redis_client()
        if not redis_client:
            # Keep events in queue if Redis is not available
            return
        
        events_to_flush = self._event_queue.copy()
        self._event_queue.clear()
        
        try:
            # Store events in Redis sorted set
            pipeline = redis_client.pipeline()
            
            for event in events_to_flush:
                # Store in sorted set with timestamp as score
                key = f"analytics:events:{event.timestamp.strftime('%Y-%m-%d')}"
                score = event.timestamp.timestamp()
                value = event.model_dump_json()
                
                await pipeline.zadd(key, {value: score})
                
                # Set expiry (30 days)
                await pipeline.expire(key, 30 * 24 * 60 * 60)
                
                # Update counters
                counter_key = f"analytics:counters:{event.event_type}:{event.timestamp.strftime('%Y-%m-%d')}"
                await pipeline.hincrby(counter_key, "count", 1)
                await pipeline.expire(counter_key, 30 * 24 * 60 * 60)
                
                # User-specific events
                if event.user_id:
                    user_key = f"analytics:user:{event.user_id}:{event.timestamp.strftime('%Y-%m')}"
                    await pipeline.zadd(user_key, {value: score})
                    await pipeline.expire(user_key, 90 * 24 * 60 * 60)  # 90 days
            
            await pipeline.execute()
            
            logger.debug(f"Flushed {len(events_to_flush)} analytics events")
            
        except Exception as e:
            logger.error(f"Failed to flush analytics events: {e}")
            # Re-add events to queue for retry
            self._event_queue.extend(events_to_flush)
    
    async def _periodic_flush(self) -> None:
        """Periodically flush events."""
        while True:
            try:
                await asyncio.sleep(settings.analytics_flush_interval)
                await self._flush_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")
    
    async def get_event_count(
        self,
        event_type: EventType,
        date: Optional[datetime] = None,
    ) -> int:
        """
        Get event count for a specific type and date.
        
        Args:
            event_type: Type of the event
            date: Date to get count for (defaults to today)
            
        Returns:
            int: Event count
        """
        redis_client = await get_redis_client()
        if not redis_client:
            return 0
        
        if date is None:
            date = datetime.now(timezone.utc)
        
        key = f"analytics:counters:{event_type}:{date.strftime('%Y-%m-%d')}"
        
        try:
            count = await redis_client.hget(key, "count")
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Failed to get event count: {e}")
            return 0
    
    async def get_user_events(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AnalyticsEvent]:
        """
        Get events for a specific user.
        
        Args:
            user_id: User ID
            limit: Maximum number of events to return
            offset: Offset for pagination
            
        Returns:
            List[AnalyticsEvent]: User events
        """
        redis_client = await get_redis_client()
        if not redis_client:
            return []
        
        # Get current month's events
        date = datetime.now(timezone.utc)
        key = f"analytics:user:{user_id}:{date.strftime('%Y-%m')}"
        
        try:
            # Get events in reverse chronological order
            events_json = await redis_client.zrevrange(
                key,
                offset,
                offset + limit - 1,
            )
            
            events = []
            for event_json in events_json:
                try:
                    event_data = json.loads(event_json)
                    events.append(AnalyticsEvent(**event_data))
                except Exception as e:
                    logger.error(f"Failed to parse event: {e}")
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get user events: {e}")
            return []


# Global analytics service instance
analytics_service = AnalyticsService()