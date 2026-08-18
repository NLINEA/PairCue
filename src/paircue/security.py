from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def token_dependency(expected_token: str) -> Callable[[Request], Awaitable[None]]:
    async def require_token(request: Request) -> None:
        credentials: HTTPAuthorizationCredentials | None = await bearer(request)
        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
            or not hmac.compare_digest(credentials.credentials, expected_token)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return require_token


async def security_headers_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'self'"
    )
    return response


def require_bounded_content_length(request: Request, maximum: int) -> None:
    raw = request.headers.get("content-length")
    if raw is None or not raw.isdigit():
        raise HTTPException(status_code=411, detail="Content-Length is required")
    if int(raw) > maximum:
        raise HTTPException(status_code=413, detail="request body is too large")
