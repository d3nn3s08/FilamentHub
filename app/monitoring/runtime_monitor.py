import time
import threading
from collections import deque
from typing import Deque, Tuple, Dict

# Rolling window of 60s for request timestamps and durations (ms)
WINDOW_SECONDS = 60
_lock = threading.Lock()
_requests: Deque[Tuple[float, float]] = deque()  # (timestamp, duration_ms)


def record_request(duration_ms: float) -> None:
    """Record a single HTTP request duration in milliseconds."""
    now = time.time()
    with _lock:
        _requests.append((now, float(duration_ms)))
        _prune_locked(now)


def _prune_locked(now: float) -> None:
    """Remove entries older than the rolling window. Caller must hold _lock."""
    cutoff = now - WINDOW_SECONDS
    while _requests and _requests[0][0] < cutoff:
        _requests.popleft()


def get_runtime_metrics() -> Dict[str, float | str]:
    """Return requests/min and avg response time in ms with defensive defaults."""
    now = time.time()
    with _lock:
        _prune_locked(now)
        count = len(_requests)
        if count > 0:
            total_ms = sum(d for _, d in _requests)
            avg_ms = round(total_ms / count, 2)
            req_per_min = round((count / WINDOW_SECONDS) * 60, 2)
        else:
            avg_ms = 0.0
            req_per_min = 0.0

    state = "active" if req_per_min > 0 else "idle"
    return {
        "requests_per_minute": req_per_min,
        "avg_response_ms": avg_ms,
        "state": state,
    }

