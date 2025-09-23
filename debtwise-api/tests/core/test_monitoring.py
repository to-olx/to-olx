"""
Tests for monitoring and observability functionality.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, Response
from starlette.datastructures import Headers

from app.core.monitoring import (
    ErrorTracker,
    HealthChecker,
    MonitoringMiddleware,
    PerformanceMonitor,
    error_tracker,
    health_checker,
    performance_monitor,
    setup_monitoring,
    shutdown_monitoring,
)


@pytest.fixture
def mock_request():
    """Create a mock request object."""
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url = MagicMock()
    request.url.path = "/api/v1/test"
    request.query_params = {}
    request.headers = Headers({
        "user-agent": "Test/1.0",
        "x-request-id": "test-request-id",
    })
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.state = MagicMock()
    request.state.request_id = "test-request-id"
    request.state.user_id = 123
    return request


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    response = MagicMock(spec=Response)
    response.status_code = 200
    return response


class TestErrorTracker:
    """Test error tracking functionality."""
    
    @pytest.mark.asyncio
    async def test_track_error(self, mock_request):
        """Test error tracking."""
        tracker = ErrorTracker()
        
        # Create test error
        test_error = ValueError("Test error message")
        
        # Track error
        await tracker.track_error(
            error=test_error,
            request=mock_request,
            user_id=123,
            context={"test": "context"},
        )
        
        # Verify error was tracked
        assert len(tracker.error_queue) == 1
        error_data = tracker.error_queue[0]
        
        assert error_data["error_type"] == "ValueError"
        assert error_data["error_message"] == "Test error message"
        assert error_data["user_id"] == 123
        assert error_data["context"]["test"] == "context"
        assert error_data["request"]["method"] == "GET"
        assert error_data["request"]["path"] == "/api/v1/test"
        assert error_data["request_id"] == "test-request-id"
    
    @pytest.mark.asyncio
    async def test_error_queue_auto_flush(self, mock_request):
        """Test error queue auto-flush when full."""
        tracker = ErrorTracker()
        
        with patch("app.core.monitoring.get_redis_client") as mock_redis:
            redis_client = AsyncMock()
            redis_client.lpush = AsyncMock()
            redis_client.ltrim = AsyncMock()
            mock_redis.return_value = redis_client
            
            # Track 100 errors to trigger auto-flush
            for i in range(100):
                error = Exception(f"Error {i}")
                await tracker.track_error(error, mock_request)
            
            # Verify flush was called
            redis_client.lpush.call_count >= 100
            redis_client.ltrim.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_error_stats(self):
        """Test getting error statistics."""
        tracker = ErrorTracker()
        
        with patch("app.core.monitoring.get_redis_client") as mock_redis:
            # Mock error logs in Redis
            error_logs = [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "ValueError",
                    "error_message": "Test error",
                    "request": {"path": "/api/v1/test"},
                },
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "ValueError",
                    "error_message": "Another test error",
                    "request": {"path": "/api/v1/test"},
                },
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "KeyError",
                    "error_message": "Key not found",
                    "request": {"path": "/api/v1/other"},
                },
            ]
            
            redis_client = AsyncMock()
            redis_client.lrange.return_value = [
                json.dumps(log).encode() for log in error_logs
            ]
            mock_redis.return_value = redis_client
            
            # Get stats
            stats = await tracker.get_error_stats(time_window=3600)
            
            # Verify stats
            assert stats["total_errors"] == 3
            assert stats["errors_by_type"]["ValueError"] == 2
            assert stats["errors_by_type"]["KeyError"] == 1
            assert stats["errors_by_endpoint"]["/api/v1/test"] == 2
            assert stats["errors_by_endpoint"]["/api/v1/other"] == 1
            assert len(stats["recent_errors"]) == 3
    
    @pytest.mark.asyncio
    async def test_error_tracker_lifecycle(self):
        """Test error tracker initialization and shutdown."""
        tracker = ErrorTracker()
        
        # Initialize
        await tracker.initialize()
        assert tracker._flush_task is not None
        
        # Shutdown
        await tracker.shutdown()
        assert tracker._flush_task.cancelled()


class TestPerformanceMonitor:
    """Test performance monitoring functionality."""
    
    def test_record_request_duration(self):
        """Test recording request duration."""
        monitor = PerformanceMonitor()
        
        # Record multiple requests
        monitor.record_request_duration(
            endpoint="/api/v1/test",
            method="GET",
            duration_ms=50.5,
            status_code=200,
        )
        monitor.record_request_duration(
            endpoint="/api/v1/test",
            method="GET",
            duration_ms=75.3,
            status_code=200,
        )
        monitor.record_request_duration(
            endpoint="/api/v1/test",
            method="POST",
            duration_ms=120.8,
            status_code=201,
        )
        
        # Verify recordings
        assert len(monitor.metrics) == 2  # Two different keys
        assert len(monitor.metrics["GET:/api/v1/test:200"]) == 2
        assert len(monitor.metrics["POST:/api/v1/test:201"]) == 1
    
    def test_get_performance_stats(self):
        """Test getting performance statistics."""
        monitor = PerformanceMonitor()
        
        # Record requests with different durations
        durations = [10.0, 20.0, 30.0, 40.0, 50.0, 100.0, 200.0]
        for duration in durations:
            monitor.record_request_duration(
                endpoint="/api/v1/test",
                method="GET",
                duration_ms=duration,
                status_code=200,
            )
        
        # Get stats
        stats = monitor.get_performance_stats()
        
        # Verify stats
        key = "GET:/api/v1/test:200"
        assert key in stats
        assert stats[key]["count"] == 7
        assert stats[key]["avg_ms"] == sum(durations) / len(durations)
        assert stats[key]["min_ms"] == 10.0
        assert stats[key]["max_ms"] == 200.0
        assert stats[key]["p50_ms"] == 40.0  # Median
        assert stats[key]["p90_ms"] >= 100.0
        assert stats[key]["p95_ms"] >= 100.0
        assert stats[key]["p99_ms"] >= 200.0
    
    def test_percentile_calculation(self):
        """Test percentile calculation."""
        monitor = PerformanceMonitor()
        
        # Test with known values
        values = list(range(1, 101))  # 1 to 100
        
        assert monitor._percentile(values, 50) == 50
        assert monitor._percentile(values, 90) == 90
        assert monitor._percentile(values, 95) == 95
        assert monitor._percentile(values, 99) == 99
        
        # Test edge cases
        assert monitor._percentile([], 50) == 0
        assert monitor._percentile([42], 50) == 42
    
    @pytest.mark.asyncio
    async def test_performance_monitor_lifecycle(self):
        """Test performance monitor initialization and shutdown."""
        monitor = PerformanceMonitor()
        
        # Initialize
        await monitor.initialize()
        assert monitor._cleanup_task is not None
        
        # Shutdown
        await monitor.shutdown()
        assert monitor._cleanup_task.cancelled()


class TestHealthChecker:
    """Test health checking functionality."""
    
    @pytest.mark.asyncio
    async def test_check_database(self):
        """Test database health check."""
        with patch("app.core.monitoring.get_db") as mock_get_db:
            # Mock successful database query
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock()
            mock_db.commit = AsyncMock()
            
            async def mock_db_generator():
                yield mock_db
            
            mock_get_db.return_value = mock_db_generator()
            
            # Check database
            result = await HealthChecker.check_database()
            
            # Verify healthy status
            assert result["status"] == "healthy"
            assert "response_time_ms" in result
            assert result["response_time_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_check_database_unhealthy(self):
        """Test database health check when unhealthy."""
        with patch("app.core.monitoring.get_db") as mock_get_db:
            # Mock database error
            async def mock_db_error():
                raise Exception("Database connection failed")
                yield
            
            mock_get_db.return_value = mock_db_error()
            
            # Check database
            result = await HealthChecker.check_database()
            
            # Verify unhealthy status
            assert result["status"] == "unhealthy"
            assert "error" in result
            assert "Database connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_check_redis(self):
        """Test Redis health check."""
        with patch("app.core.monitoring.get_redis_client") as mock_redis:
            # Mock healthy Redis
            redis_client = AsyncMock()
            redis_client.ping = AsyncMock()
            redis_client.setex = AsyncMock()
            redis_client.get = AsyncMock(return_value=b"test_value")
            mock_redis.return_value = redis_client
            
            # Check Redis
            result = await HealthChecker.check_redis()
            
            # Verify healthy status
            assert result["status"] == "healthy"
            assert "response_time_ms" in result
            redis_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_redis_unavailable(self):
        """Test Redis health check when unavailable."""
        with patch("app.core.monitoring.get_redis_client") as mock_redis:
            mock_redis.return_value = None
            
            # Check Redis
            result = await HealthChecker.check_redis()
            
            # Verify unavailable status
            assert result["status"] == "unavailable"
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_check_disk_space(self):
        """Test disk space check."""
        with patch("shutil.disk_usage") as mock_disk:
            # Mock disk usage
            mock_disk.return_value = MagicMock(
                total=100_000_000_000,  # 100GB
                used=40_000_000_000,     # 40GB
                free=60_000_000_000,     # 60GB
            )
            
            # Check disk space
            result = await HealthChecker.check_disk_space()
            
            # Verify result
            assert result["status"] == "healthy"
            assert result["total_gb"] == 100.0
            assert result["used_gb"] == 40.0
            assert result["free_gb"] == 60.0
            assert result["used_percent"] == 40.0
    
    @pytest.mark.asyncio
    async def test_check_memory(self):
        """Test memory check."""
        with patch("psutil.virtual_memory") as mock_memory:
            # Mock memory info
            mock_memory.return_value = MagicMock(
                total=16_000_000_000,      # 16GB
                available=8_000_000_000,   # 8GB
                percent=50.0,
            )
            
            # Check memory
            result = await HealthChecker.check_memory()
            
            # Verify result
            assert result["status"] == "healthy"
            assert result["total_gb"] == 16.0
            assert result["available_gb"] == 8.0
            assert result["used_percent"] == 50.0
    
    @pytest.mark.asyncio
    async def test_get_system_health(self):
        """Test overall system health check."""
        # Mock all health checks
        with patch.object(HealthChecker, "check_database") as mock_db, \
             patch.object(HealthChecker, "check_redis") as mock_redis, \
             patch.object(HealthChecker, "check_disk_space") as mock_disk, \
             patch.object(HealthChecker, "check_memory") as mock_memory:
            
            # All healthy
            mock_db.return_value = {"status": "healthy"}
            mock_redis.return_value = {"status": "healthy"}
            mock_disk.return_value = {"status": "healthy"}
            mock_memory.return_value = {"status": "healthy"}
            
            # Get system health
            result = await HealthChecker.get_system_health()
            
            # Verify overall healthy status
            assert result["status"] == "healthy"
            assert "timestamp" in result
            assert "checks" in result
            
            # Test degraded status
            mock_memory.return_value = {"status": "warning"}
            
            result = await HealthChecker.get_system_health()
            assert result["status"] == "degraded"
            
            # Test unhealthy status
            mock_db.return_value = {"status": "unhealthy"}
            
            result = await HealthChecker.get_system_health()
            assert result["status"] == "unhealthy"


class TestMonitoringMiddleware:
    """Test monitoring middleware."""
    
    @pytest.mark.asyncio
    async def test_successful_request_monitoring(self, mock_request, mock_response):
        """Test monitoring successful requests."""
        # Create middleware
        tracker = ErrorTracker()
        monitor = PerformanceMonitor()
        
        middleware = MonitoringMiddleware(
            app=MagicMock(),
            error_tracker=tracker,
            performance_monitor=monitor,
        )
        
        # Mock call_next
        async def mock_call_next(request):
            await asyncio.sleep(0.01)  # Simulate processing time
            return mock_response
        
        # Process request
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        # Verify response
        assert response == mock_response
        
        # Verify performance was recorded
        key = "GET:/api/v1/test:200"
        assert key in monitor.metrics
        assert len(monitor.metrics[key]) == 1
        assert monitor.metrics[key][0]["duration_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_error_request_monitoring(self, mock_request):
        """Test monitoring requests that raise errors."""
        # Create middleware
        tracker = ErrorTracker()
        monitor = PerformanceMonitor()
        
        middleware = MonitoringMiddleware(
            app=MagicMock(),
            error_tracker=tracker,
            performance_monitor=monitor,
        )
        
        # Mock call_next that raises error
        test_error = ValueError("Test error")
        
        async def mock_call_next(request):
            raise test_error
        
        # Process request (should raise error)
        with pytest.raises(ValueError):
            await middleware.dispatch(mock_request, mock_call_next)
        
        # Verify error was tracked
        assert len(tracker.error_queue) == 1
        assert tracker.error_queue[0]["error_type"] == "ValueError"
    
    @pytest.mark.asyncio
    async def test_5xx_error_tracking(self, mock_request):
        """Test tracking 5xx errors."""
        # Create middleware
        tracker = ErrorTracker()
        monitor = PerformanceMonitor()
        
        middleware = MonitoringMiddleware(
            app=MagicMock(),
            error_tracker=tracker,
            performance_monitor=monitor,
        )
        
        # Mock 500 response
        error_response = MagicMock(spec=Response)
        error_response.status_code = 500
        
        async def mock_call_next(request):
            return error_response
        
        # Process request
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        # Verify 5xx error was tracked
        assert len(tracker.error_queue) == 1
        assert "HTTP 500" in tracker.error_queue[0]["error_message"]


@pytest.mark.asyncio
async def test_monitoring_setup_and_shutdown():
    """Test monitoring setup and shutdown."""
    from fastapi import FastAPI
    
    app = FastAPI()
    
    # Setup monitoring
    await setup_monitoring(app)
    
    # Verify components are initialized
    assert error_tracker._flush_task is not None
    assert performance_monitor._cleanup_task is not None
    
    # Shutdown monitoring
    await shutdown_monitoring()
    
    # Verify components are shut down
    assert error_tracker._flush_task.cancelled()
    assert performance_monitor._cleanup_task.cancelled()