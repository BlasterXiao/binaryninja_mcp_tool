from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Require Authorization: Bearer <token> for MCP paths."""

    def __init__(self, app, get_token_callable, path_prefix: str = "/mcp"):
        super().__init__(app)
        self._get_token = get_token_callable
        self._prefix = path_prefix

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        if path.startswith(self._prefix):
            expected = self._get_token()
            auth = request.headers.get("authorization") or ""
            if not auth.lower().startswith("bearer "):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
            token = auth[7:].strip()
            if not expected or token != expected:
                return JSONResponse({"detail": "Invalid token"}, status_code=401)
        return await call_next(request)
