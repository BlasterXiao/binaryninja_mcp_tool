from __future__ import annotations

import time
from collections import deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding window: max_requests per window_seconds per client IP."""

    def __init__(self, app, max_requests: int = 30, window_seconds: float = 1.0):
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque] = {}
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(client, deque())
            while q and now - q[0] > self._window:
                q.popleft()
            if len(q) >= self._max:
                return JSONResponse(
                    {"detail": "Too Many Requests"}, status_code=429
                )
            q.append(now)
        return await call_next(request)
