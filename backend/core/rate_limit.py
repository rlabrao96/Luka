"""Rate-limiting utilities backed by ``slowapi``.

Bootstrapped here so route modules can import a shared ``limiter`` instance
and apply ``@limiter.limit(...)`` decorators. The exception handler returns
a JSON 429 response that matches Luka's standard error shape.

Per-IP keying (``get_remote_address`` -> ``request.client.host``) is correct
in production because uvicorn runs with ``--forwarded-allow-ips=*`` (see the
Dockerfile / Procfile / railway.toml). The container is only reachable
through Railway's edge proxy, so uvicorn trusts its ``X-Forwarded-For`` and
rewrites ``request.client.host`` to the real client IP. Without that flag
every request would key on the proxy IP and all users would share one bucket
(SEC-8). The single-trusted-proxy chain is handled by uvicorn's maintained
ProxyHeadersMiddleware -- we deliberately do NOT hand-parse XFF here.

Per-user keying (``per_user_key``) is included for completeness but is not
yet wired into the invite endpoints; per-IP limits already meet the security
objective (token guessing).
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

limiter = Limiter(key_func=get_remote_address, default_limits=[])


def per_user_key(request: Request) -> str:
    """Use authenticated user id when available, else fall back to IP.

    NOTE: For this to work, ``request.state.user`` must be populated *before*
    slowapi's wrapper invokes ``key_func``. Today no middleware does that, so
    callers should stick with ``get_remote_address`` until v2.
    """
    user = getattr(request.state, "user", None)
    if user is not None and getattr(user, "id", None) is not None:
        return f"user:{user.id}"
    return get_remote_address(request)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "rate_limit_exceeded", "retry_after": str(exc.detail)},
    )
