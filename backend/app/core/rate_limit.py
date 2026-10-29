import time
from collections import defaultdict, deque
from typing import Dict, Deque
from threading import Lock
from fastapi import Request
from app.core.exceptions import WadihAPIException


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self, max_requests: int = 15, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> bool:
        """Record attempt and return True if within limit, False if exceeded."""
        now = time.time()
        with self._lock:
            q = self._requests[key]
            cutoff = now - self.window_seconds
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        """Clear all recorded rate limit windows (useful for test resets)."""
        with self._lock:
            self._requests.clear()


demo_session_limiter = SlidingWindowRateLimiter(max_requests=15, window_seconds=60)


def check_demo_session_rate_limit(request: Request) -> None:
    """Enforce rate limits on synthetic demo-session creation."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "unknown"

    if not demo_session_limiter.check(client_ip):
        raise WadihAPIException(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            message="Too many demo session requests. Please wait a minute before requesting another demo session.",
        )
