import threading
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import error_response_body


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """Small in-process fixed-window limiter for single-process deployments."""

    def __init__(
        self,
        app,
        max_requests: int,
        window_seconds: int,
        excluded_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.max_requests = max(1, max_requests)
        self.window_seconds = max(1, window_seconds)
        self.excluded_paths = excluded_paths or set()
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        now = time.monotonic()
        client_host = request.client.host if request.client else "unknown"
        key = (client_host, request.url.path)

        with self._lock:
            timestamps = self._requests[key]
            self._remove_expired(timestamps=timestamps, now=now)

            if len(timestamps) >= self.max_requests:
                retry_after = self._retry_after_seconds(timestamps=timestamps, now=now)
                return JSONResponse(
                    status_code=429,
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                    content=error_response_body(
                        code="rate_limit_exceeded",
                        message="Too many requests",
                        details={
                            "limit": self.max_requests,
                            "window_seconds": self.window_seconds,
                            "retry_after_seconds": retry_after,
                        },
                    ),
                )

            timestamps.append(now)
            remaining = self.max_requests - len(timestamps)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _remove_expired(self, timestamps: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

    def _retry_after_seconds(self, timestamps: deque[float], now: float) -> int:
        if not timestamps:
            return 1

        oldest_request_age = now - timestamps[0]
        retry_after = self.window_seconds - oldest_request_age
        return max(1, int(retry_after) + 1)
