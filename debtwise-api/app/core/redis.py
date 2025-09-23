"""
Redis connection management module.
"""

import redis.asyncio as redis
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> Optional[redis.Redis]:
    """
    Get the Redis client instance.
    
    Returns:
        Optional[redis.Redis]: Redis client instance or None if not available.
    """
    return _redis_client


async def init_redis() -> None:
    """
    Initialize Redis connection.
    """
    global _redis_client
    
    try:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            retry_on_error=[redis.ConnectionError, redis.TimeoutError],
        )
        
        # Test connection
        await _redis_client.ping()
        logger.info("Redis connection initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        _redis_client = None
        # Continue without Redis - graceful degradation


async def close_redis() -> None:
    """
    Close Redis connection.
    """
    global _redis_client
    
    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
        finally:
            _redis_client = None


async def is_redis_healthy() -> bool:
    """
    Check if Redis connection is healthy.
    
    Returns:
        bool: True if Redis is healthy, False otherwise.
    """
    if not _redis_client:
        return False
    
    try:
        await _redis_client.ping()
        return True
    except Exception:
        return False