"""
Error monitoring and observability setup for DebtWise API.
Integrates with various monitoring services and provides custom error tracking.
"""

import asyncio
import json
import logging
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis_client

logger = get_logger(__name__)


class ErrorTracker:
    """Track and aggregate application errors."""
    
    def __init__(self):
        self.error_queue: List[Dict[str, Any]] = []
        self.metrics: Dict[str, int] = {}
        self._flush_task = None
    
    async def initialize(self):
        """Initialize error tracker and start background tasks."""
        self._flush_task = asyncio.create_task(self._flush_errors_periodically())
        logger.info("Error tracker initialized")
    
    async def shutdown(self):
        """Shutdown error tracker and flush pending errors."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush any remaining errors
        await self._flush_errors()
        logger.info("Error tracker shutdown complete")
    
    async def track_error(
        self,
        error: Exception,
        request: Optional[Request] = None,
        user_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track an error occurrence."""
        error_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "user_id": user_id,
            "context": context or {},
        }
        
        # Add request information if available
        if request:
            error_data["request"] = {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": dict(request.headers),
                "client_host": request.client.host if request.client else None,
            }
            
            # Add request ID if available
            if hasattr(request.state, "request_id"):
                error_data["request_id"] = request.state.request_id
        
        # Add to queue
        self.error_queue.append(error_data)
        
        # Update metrics
        error_key = f"{error_data['error_type']}:{request.url.path if request else 'unknown'}"
        self.metrics[error_key] = self.metrics.get(error_key, 0) + 1
        
        # Log error
        logger.error(
            f"Error tracked: {error_data['error_type']}",
            extra=error_data
        )
        
        # Flush if queue is getting large
        if len(self.error_queue) >= 100:
            await self._flush_errors()
    
    async def _flush_errors(self) -> None:
        """Flush errors to persistent storage or external service."""
        if not self.error_queue:
            return
        
        errors_to_flush = self.error_queue.copy()
        self.error_queue.clear()
        
        try:
            # Store in Redis for real-time monitoring
            redis_client = await get_redis_client()
            if redis_client:
                for error in errors_to_flush:
                    await redis_client.lpush(
                        "error_log",
                        json.dumps(error)
                    )
                
                # Keep only recent errors (last 10k)
                await redis_client.ltrim("error_log", 0, 9999)
            
            # Here you would also send to external services like:
            # - Sentry
            # - Datadog
            # - New Relic
            # - CloudWatch
            # - Custom logging service
            
            logger.info(f"Flushed {len(errors_to_flush)} errors to storage")
            
        except Exception as e:
            logger.error(f"Failed to flush errors: {e}")
            # Re-add errors to queue for retry
            self.error_queue.extend(errors_to_flush)
    
    async def _flush_errors_periodically(self) -> None:
        """Background task to flush errors periodically."""
        while True:
            try:
                await asyncio.sleep(30)  # Flush every 30 seconds
                await self._flush_errors()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")
    
    async def get_error_stats(
        self,
        time_window: int = 3600
    ) -> Dict[str, Any]:
        """Get error statistics for monitoring dashboard."""
        redis_client = await get_redis_client()
        if not redis_client:
            return {
                "total_errors": 0,
                "errors_by_type": {},
                "errors_by_endpoint": {},
                "recent_errors": [],
            }
        
        # Get recent errors
        recent_errors_raw = await redis_client.lrange("error_log", 0, 999)
        recent_errors = []
        errors_by_type = {}
        errors_by_endpoint = {}
        
        current_time = datetime.now(timezone.utc)
        
        for error_raw in recent_errors_raw:
            try:
                error = json.loads(error_raw)
                error_time = datetime.fromisoformat(
                    error["timestamp"].replace("Z", "+00:00")
                )
                
                # Only count errors within time window
                if (current_time - error_time).total_seconds() <= time_window:
                    recent_errors.append(error)
                    
                    # Count by type
                    error_type = error.get("error_type", "Unknown")
                    errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1
                    
                    # Count by endpoint
                    if "request" in error:
                        endpoint = error["request"].get("path", "Unknown")
                        errors_by_endpoint[endpoint] = errors_by_endpoint.get(endpoint, 0) + 1
                        
            except Exception as e:
                logger.error(f"Failed to parse error log: {e}")
        
        return {
            "total_errors": len(recent_errors),
            "errors_by_type": errors_by_type,
            "errors_by_endpoint": errors_by_endpoint,
            "recent_errors": recent_errors[:10],  # Last 10 errors
            "time_window_seconds": time_window,
        }


class PerformanceMonitor:
    """Monitor API performance metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self._cleanup_task = None
    
    async def initialize(self):
        """Initialize performance monitor."""
        self._cleanup_task = asyncio.create_task(self._cleanup_old_metrics())
        logger.info("Performance monitor initialized")
    
    async def shutdown(self):
        """Shutdown performance monitor."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Performance monitor shutdown complete")
    
    def record_request_duration(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: int,
    ) -> None:
        """Record request duration for performance tracking."""
        key = f"{method}:{endpoint}:{status_code}"
        
        if key not in self.metrics:
            self.metrics[key] = []
        
        self.metrics[key].append({
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        })
        
        # Keep only recent metrics (last hour)
        cutoff_time = time.time() - 3600
        self.metrics[key] = [
            m for m in self.metrics[key]
            if m["timestamp"] > cutoff_time
        ]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = {}
        
        for key, measurements in self.metrics.items():
            if not measurements:
                continue
            
            durations = [m["duration_ms"] for m in measurements]
            
            # Skip if no durations found
            if not durations:
                continue
            
            # Calculate statistics
            stats[key] = {
                "count": len(durations),
                "avg_ms": sum(durations) / len(durations),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "p50_ms": self._percentile(durations, 50),
                "p90_ms": self._percentile(durations, 90),
                "p95_ms": self._percentile(durations, 95),
                "p99_ms": self._percentile(durations, 99),
            }
        
        return stats
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not values:
            return 0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        
        if index >= len(sorted_values):
            return sorted_values[-1]
        
        return sorted_values[index]
    
    async def _cleanup_old_metrics(self) -> None:
        """Background task to cleanup old metrics."""
        while True:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
                cutoff_time = time.time() - 3600
                for key in list(self.metrics.keys()):
                    self.metrics[key] = [
                        m for m in self.metrics.get(key, [])
                        if m["timestamp"] > cutoff_time
                    ]
                    
                    # Remove empty keys
                    if not self.metrics[key]:
                        del self.metrics[key]
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics cleanup: {e}")


class HealthChecker:
    """Check health of various system components."""
    
    @staticmethod
    async def check_database() -> Dict[str, Any]:
        """Check database connectivity and performance."""
        from sqlalchemy import text
        from app.core.database import get_db
        
        start_time = time.time()
        
        try:
            async for db in get_db():
                result = await db.execute(text("SELECT 1"))
                await db.commit()
            
            duration_ms = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": duration_ms,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": (time.time() - start_time) * 1000,
            }
    
    @staticmethod
    async def check_redis() -> Dict[str, Any]:
        """Check Redis connectivity and performance."""
        start_time = time.time()
        
        try:
            redis_client = await get_redis_client()
            if not redis_client:
                return {
                    "status": "unavailable",
                    "error": "Redis client not configured",
                }
            
            # Ping Redis
            await redis_client.ping()
            
            # Test set/get
            test_key = "health_check_test"
            test_value = str(time.time())
            await redis_client.setex(test_key, 10, test_value)
            retrieved = await redis_client.get(test_key)
            
            if retrieved.decode() != test_value:
                raise ValueError("Redis test value mismatch")
            
            duration_ms = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": duration_ms,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": (time.time() - start_time) * 1000,
            }
    
    @staticmethod
    async def check_disk_space() -> Dict[str, Any]:
        """Check available disk space."""
        import shutil
        
        try:
            stat = shutil.disk_usage("/")
            
            return {
                "status": "healthy" if stat.free > 1_000_000_000 else "warning",  # 1GB threshold
                "total_gb": round(stat.total / 1_000_000_000, 2),
                "used_gb": round(stat.used / 1_000_000_000, 2),
                "free_gb": round(stat.free / 1_000_000_000, 2),
                "used_percent": round((stat.used / stat.total) * 100, 2),
            }
        except Exception as e:
            return {
                "status": "unknown",
                "error": str(e),
            }
    
    @staticmethod
    async def check_memory() -> Dict[str, Any]:
        """Check system memory usage."""
        import psutil
        
        try:
            memory = psutil.virtual_memory()
            
            return {
                "status": "healthy" if memory.percent < 80 else "warning",
                "total_gb": round(memory.total / 1_000_000_000, 2),
                "available_gb": round(memory.available / 1_000_000_000, 2),
                "used_percent": memory.percent,
            }
        except Exception as e:
            return {
                "status": "unknown",
                "error": str(e),
            }
    
    @classmethod
    async def get_system_health(cls) -> Dict[str, Any]:
        """Get overall system health status."""
        health_checks = await asyncio.gather(
            cls.check_database(),
            cls.check_redis(),
            cls.check_disk_space(),
            cls.check_memory(),
            return_exceptions=True,
        )
        
        results = {
            "database": health_checks[0] if not isinstance(health_checks[0], Exception) else {"status": "error", "error": str(health_checks[0])},
            "redis": health_checks[1] if not isinstance(health_checks[1], Exception) else {"status": "error", "error": str(health_checks[1])},
            "disk": health_checks[2] if not isinstance(health_checks[2], Exception) else {"status": "error", "error": str(health_checks[2])},
            "memory": health_checks[3] if not isinstance(health_checks[3], Exception) else {"status": "error", "error": str(health_checks[3])},
        }
        
        # Determine overall status
        statuses = [check.get("status", "unknown") for check in results.values()]
        
        if any(status in ["unhealthy", "error"] for status in statuses):
            overall_status = "unhealthy"
        elif any(status == "warning" for status in statuses):
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": results,
        }


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to monitor requests and track errors."""
    
    def __init__(self, app, error_tracker: ErrorTracker, performance_monitor: PerformanceMonitor):
        super().__init__(app)
        self.error_tracker = error_tracker
        self.performance_monitor = performance_monitor
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request and handle errors."""
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Record performance metrics
            duration_ms = (time.time() - start_time) * 1000
            self.performance_monitor.record_request_duration(
                endpoint=request.url.path,
                method=request.method,
                duration_ms=duration_ms,
                status_code=response.status_code,
            )
            
            # Track 5xx errors
            if response.status_code >= 500:
                await self.error_tracker.track_error(
                    Exception(f"HTTP {response.status_code}"),
                    request=request,
                    user_id=getattr(request.state, "user_id", None),
                    context={
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    },
                )
            
            return response
            
        except Exception as e:
            # Track the error
            await self.error_tracker.track_error(
                e,
                request=request,
                user_id=getattr(request.state, "user_id", None),
            )
            
            # Re-raise the error
            raise


# Global instances
error_tracker = ErrorTracker()
performance_monitor = PerformanceMonitor()
health_checker = HealthChecker()


async def setup_monitoring(app: FastAPI) -> None:
    """Setup monitoring for the application."""
    await error_tracker.initialize()
    await performance_monitor.initialize()
    
    # Add monitoring middleware
    app.add_middleware(
        MonitoringMiddleware,
        error_tracker=error_tracker,
        performance_monitor=performance_monitor,
    )
    
    logger.info("Monitoring setup complete")


async def shutdown_monitoring() -> None:
    """Shutdown monitoring services."""
    await error_tracker.shutdown()
    await performance_monitor.shutdown()
    
    logger.info("Monitoring shutdown complete")