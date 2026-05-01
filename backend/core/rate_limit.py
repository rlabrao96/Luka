"""Rate-limiting utilities backed by ``slowapi``.

Bootstrapped here so route modules can import a shared ``limiter`` instance
and apply ``@limiter.limit(...)`` decorators. The exception handler returns
a JSON 429 response that matches Luka's standard error shape.

Per-user keying (``per_user_key``) is included for completeness but is not
yet wired into the trips invite-link endpoints — slowapi resolves
``key_func`` *before* the route body runs, so attaching ``request.state.user``
inside the route is too late. v2 will move the user lookup into a middleware
layer so per-user limits work; for v1, per-IP limits protect against token
guessing (the relevant security objective).
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
