"""
Monitoring API Routes
Real-time performance metrics and health monitoring
"""
from fastapi import APIRouter, Query
from typing import Optional
from app.services.performance_monitoring import get_performance_monitor

router = APIRouter()


@router.get("/api/monitoring/health")
def get_health_report():
    """
    Get comprehensive health report with performance metrics

    Returns:
        Health status, uptime, metrics, and slowest endpoints
    """
    monitor = get_performance_monitor()
    return monitor.get_health_report()


@router.get("/api/monitoring/endpoints")
def get_endpoint_stats(top_n: Optional[int] = Query(None, ge=1, le=100)):
    """
    Get performance statistics for all endpoints

    Args:
        top_n: If set, return only top N slowest endpoints

    Returns:
        List of endpoint statistics sorted by average response time
    """
    monitor = get_performance_monitor()
    stats = monitor.get_endpoint_stats(top_n=top_n)

    return [
        {
            "endpoint": s.endpoint,
            "requests": s.request_count,
            "avg_ms": round(s.avg_duration_ms, 1),
            "min_ms": round(s.min_duration_ms, 1),
            "max_ms": round(s.max_duration_ms, 1),
            "errors": s.error_count,
            "error_rate": round(s.error_rate, 4),
            "rating": s.rating,
            "last_request": s.last_request.isoformat() if s.last_request else None
        }
        for s in stats
    ]


@router.get("/api/monitoring/recent")
def get_recent_requests(
    minutes: Optional[int] = Query(None, ge=1, le=60),
    limit: Optional[int] = Query(100, ge=1, le=1000)
):
    """
    Get recent requests

    Args:
        minutes: Only return requests from last N minutes
        limit: Maximum number of requests to return

    Returns:
        List of recent request metrics
    """
    monitor = get_performance_monitor()
    requests = monitor.get_recent_requests(minutes=minutes, limit=limit)

    return [
        {
            "endpoint": r.endpoint,
            "method": r.method,
            "duration_ms": round(r.duration_ms, 1),
            "status_code": r.status_code,
            "timestamp": r.timestamp.isoformat()
        }
        for r in requests
    ]


@router.get("/api/monitoring/slow-requests")
def get_slow_requests(threshold_ms: float = Query(1000, ge=100, le=10000)):
    """
    Get requests that exceeded threshold

    Args:
        threshold_ms: Threshold in milliseconds (default: 1000ms)

    Returns:
        List of slow requests
    """
    monitor = get_performance_monitor()
    slow = monitor.get_slow_requests(threshold_ms=threshold_ms)

    return {
        "threshold_ms": threshold_ms,
        "count": len(slow),
        "requests": [
            {
                "endpoint": r.endpoint,
                "method": r.method,
                "duration_ms": round(r.duration_ms, 1),
                "status_code": r.status_code,
                "timestamp": r.timestamp.isoformat()
            }
            for r in slow
        ]
    }


@router.post("/api/monitoring/reset")
def reset_monitoring_stats():
    """
    Reset all monitoring statistics

    ⚠️ USE WITH CAUTION - This clears all performance history
    """
    monitor = get_performance_monitor()
    monitor.reset_stats()
    return {"status": "reset", "message": "All monitoring statistics have been reset"}


@router.get("/api/monitoring/alerts")
def get_performance_alerts():
    """
    Get active performance alerts

    Returns:
        List of performance issues requiring attention
    """
    monitor = get_performance_monitor()
    health = monitor.get_health_report()

    alerts = []

    # Check for degraded status
    if health["status"] == "DEGRADED":
        alerts.append({
            "severity": "WARNING",
            "type": "DEGRADED_PERFORMANCE",
            "message": "System performance is degraded"
        })

    # Check for high error rate
    error_rate = health["metrics"]["error_rate"]
    if error_rate > 0.1:
        alerts.append({
            "severity": "ERROR",
            "type": "HIGH_ERROR_RATE",
            "message": f"Error rate is {error_rate:.1%} (threshold: 10%)"
        })

    # Check for slow recent requests
    recent_avg = health["metrics"]["recent_avg_ms"]
    if recent_avg > 1000:
        alerts.append({
            "severity": "WARNING",
            "type": "SLOW_RESPONSE_TIME",
            "message": f"Recent average response time: {recent_avg:.1f}ms (threshold: 1000ms)"
        })

    # Check for poor-rated endpoints
    poor_count = health["endpoint_ratings"]["POOR"]
    if poor_count > 0:
        alerts.append({
            "severity": "CRITICAL",
            "type": "POOR_ENDPOINT_PERFORMANCE",
            "message": f"{poor_count} endpoint(s) have POOR performance (>2s avg)"
        })

    return {
        "status": "HEALTHY" if len(alerts) == 0 else "ALERTING",
        "alert_count": len(alerts),
        "alerts": alerts
    }
