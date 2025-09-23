"""
Monitoring and observability endpoints for system health and metrics.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_active_user
from app.core.monitoring import error_tracker, health_checker, performance_monitor
from app.models.user import User

router = APIRouter()


@router.get("/health/detailed", tags=["Monitoring"])
async def get_detailed_health(
    include_checks: bool = Query(True, description="Include detailed health checks"),
) -> Dict[str, Any]:
    """
    Get detailed health status of the system.
    
    This endpoint provides comprehensive health information including:
    - Database connectivity
    - Redis availability
    - Disk space
    - Memory usage
    
    No authentication required for basic health checks.
    """
    if not include_checks:
        return {
            "status": "healthy",
            "message": "Service is running",
        }
    
    health_status = await health_checker.get_system_health()
    return health_status


@router.get("/metrics", tags=["Monitoring"])
async def get_metrics(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get system metrics and performance statistics.
    
    Requires authentication. Returns:
    - Request performance metrics
    - Error statistics
    - System resource usage
    """
    # Check if user is admin (in production, implement proper admin check)
    # if not current_user.is_admin:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Admin access required"
    #     )
    
    performance_stats = performance_monitor.get_performance_stats()
    error_stats = await error_tracker.get_error_stats()
    
    return {
        "performance": performance_stats,
        "errors": error_stats,
        "timestamp": health_checker.get_system_health()["timestamp"],
    }


@router.get("/errors", tags=["Monitoring"])
async def get_error_logs(
    time_window: int = Query(3600, description="Time window in seconds (default: 1 hour)"),
    limit: int = Query(100, description="Maximum number of errors to return"),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get recent error logs.
    
    Requires authentication. Returns detailed error information for debugging.
    """
    # Check admin permission
    # if not current_user.is_admin:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Admin access required"
    #     )
    
    error_stats = await error_tracker.get_error_stats(time_window=time_window)
    
    # Limit the number of recent errors returned
    error_stats["recent_errors"] = error_stats["recent_errors"][:limit]
    
    return error_stats


@router.get("/performance/{endpoint:path}", tags=["Monitoring"])
async def get_endpoint_performance(
    endpoint: str,
    method: Optional[str] = Query(None, description="HTTP method to filter by"),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get performance statistics for a specific endpoint.
    
    Requires authentication. Returns detailed performance metrics for the specified endpoint.
    """
    # Normalize endpoint
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    
    all_stats = performance_monitor.get_performance_stats()
    
    # Filter by endpoint
    endpoint_stats = {}
    for key, stats in all_stats.items():
        parts = key.split(":")
        if len(parts) >= 2:
            key_method, key_endpoint = parts[0], parts[1]
            
            if key_endpoint == endpoint:
                if method is None or key_method == method.upper():
                    endpoint_stats[key] = stats
    
    if not endpoint_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No performance data found for endpoint: {endpoint}"
        )
    
    return {
        "endpoint": endpoint,
        "method": method,
        "statistics": endpoint_stats,
    }


@router.post("/errors/test", tags=["Monitoring"])
async def trigger_test_error(
    error_type: str = Query("generic", description="Type of error to trigger"),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, str]:
    """
    Trigger a test error for monitoring system validation.
    
    Requires authentication. Used to test error tracking and alerting.
    """
    # This endpoint is for testing the error monitoring system
    
    if error_type == "generic":
        raise Exception("This is a test error for monitoring validation")
    elif error_type == "value":
        raise ValueError("This is a test ValueError")
    elif error_type == "http":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This is a test HTTP error"
        )
    else:
        return {
            "message": f"Unknown error type: {error_type}",
            "available_types": ["generic", "value", "http"]
        }


@router.get("/dashboard", tags=["Monitoring"])
async def get_monitoring_dashboard(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get comprehensive monitoring dashboard data.
    
    Requires authentication. Returns all monitoring data in a single response
    suitable for displaying on a monitoring dashboard.
    """
    # Gather all monitoring data
    health_status = await health_checker.get_system_health()
    performance_stats = performance_monitor.get_performance_stats()
    error_stats = await error_tracker.get_error_stats(time_window=3600)  # Last hour
    
    # Calculate summary statistics
    total_requests = sum(
        stats["count"]
        for stats in performance_stats.values()
    )
    
    avg_response_time = 0
    if total_requests > 0:
        total_duration = sum(
            stats["avg_ms"] * stats["count"]
            for stats in performance_stats.values()
        )
        avg_response_time = total_duration / total_requests
    
    # Get error rate
    error_rate = 0
    if total_requests > 0:
        total_errors = sum(
            stats["count"]
            for key, stats in performance_stats.items()
            if len(key.split(":")) >= 3 and "5" in key.split(":")[2]  # 5xx status codes
        )
        error_rate = (total_errors / total_requests) * 100
    
    return {
        "summary": {
            "health_status": health_status["status"],
            "total_requests": total_requests,
            "avg_response_time_ms": round(avg_response_time, 2),
            "error_rate_percent": round(error_rate, 2),
            "total_errors_last_hour": error_stats["total_errors"],
        },
        "health": health_status,
        "performance": {
            "endpoints": performance_stats,
            "slowest_endpoints": _get_slowest_endpoints(performance_stats, limit=5),
        },
        "errors": {
            "by_type": error_stats["errors_by_type"],
            "by_endpoint": error_stats["errors_by_endpoint"],
            "recent": error_stats["recent_errors"][:5],  # Last 5 errors
        },
    }


def _get_slowest_endpoints(
    performance_stats: Dict[str, Dict[str, float]],
    limit: int = 5
) -> list:
    """Get the slowest endpoints by average response time."""
    endpoint_times = []
    
    for key, stats in performance_stats.items():
        parts = key.split(":")
        if len(parts) >= 2:
            endpoint_times.append({
                "method": parts[0],
                "endpoint": parts[1],
                "status_code": parts[2] if len(parts) > 2 else "unknown",
                "avg_ms": stats["avg_ms"],
                "count": stats["count"],
            })
    
    # Sort by average response time (descending)
    endpoint_times.sort(key=lambda x: x["avg_ms"], reverse=True)
    
    return endpoint_times[:limit]