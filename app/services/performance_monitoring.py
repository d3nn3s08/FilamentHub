"""
Performance Monitoring Service
Tracks API response times and system health metrics
"""
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RequestMetric:
    """Single request performance metric"""
    endpoint: str
    method: str
    duration_ms: float
    status_code: int
    timestamp: datetime


@dataclass
class EndpointStats:
    """Aggregated statistics for an endpoint"""
    endpoint: str
    request_count: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    error_count: int = 0
    last_request: Optional[datetime] = None

    @property
    def avg_duration_ms(self) -> float:
        """Calculate average response time"""
        if self.request_count == 0:
            return 0.0
        return self.total_duration_ms / self.request_count

    @property
    def error_rate(self) -> float:
        """Calculate error rate (0.0 - 1.0)"""
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count

    @property
    def rating(self) -> str:
        """Performance rating based on average response time"""
        avg = self.avg_duration_ms
        if avg < 500:
            return "EXCELLENT"
        elif avg < 1000:
            return "GOOD"
        elif avg < 2000:
            return "ACCEPTABLE"
        else:
            return "POOR"


class PerformanceMonitor:
    """
    Centralized performance monitoring service

    Features:
    - Track request response times
    - Identify slow endpoints
    - Monitor error rates
    - Generate health reports
    - Alert on performance degradation
    """

    def __init__(self, max_history: int = 1000, alert_threshold_ms: float = 500):
        """
        Initialize performance monitor

        Args:
            max_history: Maximum number of recent requests to keep
            alert_threshold_ms: Threshold for slow request alerts
        """
        self.max_history = max_history
        self.alert_threshold_ms = alert_threshold_ms

        # Recent request history (ring buffer)
        self.recent_requests: deque = deque(maxlen=max_history)

        # Per-endpoint statistics
        self.endpoint_stats: Dict[str, EndpointStats] = {}

        # Global counters
        self.total_requests = 0
        self.total_errors = 0
        self.start_time = datetime.now()

    def record_request(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: int
    ):
        """
        Record a completed request

        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            duration_ms: Request duration in milliseconds
            status_code: HTTP status code
        """
        now = datetime.now()

        # Create metric
        metric = RequestMetric(
            endpoint=endpoint,
            method=method,
            duration_ms=duration_ms,
            status_code=status_code,
            timestamp=now
        )

        # Add to history
        self.recent_requests.append(metric)

        # Update global counters
        self.total_requests += 1
        if status_code >= 400:
            self.total_errors += 1

        # Update endpoint statistics
        key = f"{method} {endpoint}"
        if key not in self.endpoint_stats:
            self.endpoint_stats[key] = EndpointStats(endpoint=key)

        stats = self.endpoint_stats[key]
        stats.request_count += 1
        stats.total_duration_ms += duration_ms
        stats.min_duration_ms = min(stats.min_duration_ms, duration_ms)
        stats.max_duration_ms = max(stats.max_duration_ms, duration_ms)
        stats.last_request = now

        if status_code >= 400:
            stats.error_count += 1

        # Alert on slow requests
        if duration_ms > self.alert_threshold_ms:
            logger.warning(
                f"[PERF-ALERT] Slow request: {method} {endpoint} "
                f"took {duration_ms:.1f}ms (threshold: {self.alert_threshold_ms}ms)"
            )

        # Alert on errors
        if status_code >= 500:
            logger.error(
                f"[PERF-ALERT] Server error: {method} {endpoint} "
                f"returned {status_code}"
            )

    def get_endpoint_stats(self, top_n: Optional[int] = None) -> List[EndpointStats]:
        """
        Get endpoint statistics

        Args:
            top_n: If set, return only top N slowest endpoints

        Returns:
            List of endpoint statistics, sorted by average response time
        """
        stats = list(self.endpoint_stats.values())
        stats.sort(key=lambda x: x.avg_duration_ms, reverse=True)

        if top_n:
            return stats[:top_n]
        return stats

    def get_recent_requests(
        self,
        minutes: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[RequestMetric]:
        """
        Get recent requests

        Args:
            minutes: If set, only return requests from last N minutes
            limit: Maximum number of requests to return

        Returns:
            List of recent request metrics
        """
        requests = list(self.recent_requests)

        if minutes:
            cutoff = datetime.now() - timedelta(minutes=minutes)
            requests = [r for r in requests if r.timestamp >= cutoff]

        if limit:
            requests = requests[-limit:]

        return requests

    def get_slow_requests(self, threshold_ms: float = 1000) -> List[RequestMetric]:
        """
        Get requests that exceeded threshold

        Args:
            threshold_ms: Threshold in milliseconds

        Returns:
            List of slow requests
        """
        return [
            r for r in self.recent_requests
            if r.duration_ms >= threshold_ms
        ]

    def get_health_report(self) -> Dict:
        """
        Generate comprehensive health report

        Returns:
            Dictionary with health metrics
        """
        now = datetime.now()
        uptime = now - self.start_time

        # Recent requests (last 5 minutes)
        recent = self.get_recent_requests(minutes=5)

        # Calculate recent metrics
        recent_avg = 0.0
        recent_errors = 0
        if recent:
            recent_avg = sum(r.duration_ms for r in recent) / len(recent)
            recent_errors = sum(1 for r in recent if r.status_code >= 400)

        # Overall error rate
        error_rate = 0.0
        if self.total_requests > 0:
            error_rate = self.total_errors / self.total_requests

        # Top 10 slowest endpoints
        slowest = self.get_endpoint_stats(top_n=10)

        # Count endpoints by rating
        all_stats = self.get_endpoint_stats()
        rating_counts = {
            "EXCELLENT": sum(1 for s in all_stats if s.rating == "EXCELLENT"),
            "GOOD": sum(1 for s in all_stats if s.rating == "GOOD"),
            "ACCEPTABLE": sum(1 for s in all_stats if s.rating == "ACCEPTABLE"),
            "POOR": sum(1 for s in all_stats if s.rating == "POOR"),
        }

        # Overall health status
        if rating_counts["POOR"] > 0:
            health_status = "DEGRADED"
        elif error_rate > 0.1:
            health_status = "DEGRADED"
        elif recent_avg > 1000:
            health_status = "DEGRADED"
        else:
            health_status = "HEALTHY"

        return {
            "status": health_status,
            "timestamp": now.isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "metrics": {
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "error_rate": round(error_rate, 4),
                "recent_requests_5min": len(recent),
                "recent_avg_ms": round(recent_avg, 1),
                "recent_errors_5min": recent_errors
            },
            "endpoint_ratings": rating_counts,
            "slowest_endpoints": [
                {
                    "endpoint": s.endpoint,
                    "avg_ms": round(s.avg_duration_ms, 1),
                    "min_ms": round(s.min_duration_ms, 1),
                    "max_ms": round(s.max_duration_ms, 1),
                    "requests": s.request_count,
                    "errors": s.error_count,
                    "rating": s.rating
                }
                for s in slowest
            ]
        }

    def reset_stats(self):
        """Reset all statistics (useful for testing)"""
        self.recent_requests.clear()
        self.endpoint_stats.clear()
        self.total_requests = 0
        self.total_errors = 0
        self.start_time = datetime.now()
        logger.info("[PERF] Statistics reset")


# Global singleton instance
_monitor_instance: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """
    Get global performance monitor instance

    Returns:
        PerformanceMonitor singleton
    """
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = PerformanceMonitor(
            max_history=1000,
            alert_threshold_ms=500
        )
    return _monitor_instance
