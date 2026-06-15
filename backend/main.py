import asyncio

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.database import engine
from core.rate_limit import limiter, rate_limit_exceeded_handler

# Import all models so SQLAlchemy metadata is complete for FK resolution
import modules.auth.models  # noqa: F401
import modules.households.models  # noqa: F401
import modules.transactions.models  # noqa: F401
import modules.merchants.models  # noqa: F401
import modules.settings.models  # noqa: F401
import modules.bank_connect.models  # noqa: F401
import modules.notifications.models  # noqa: F401
import modules.merchant_review.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.currencies.models  # noqa: F401

from modules.auth.router import router as auth_router
from modules.bank_accounts.router import router as bank_accounts_router
from modules.budgets.router import router as budgets_router
from modules.budgets.cuota_router import router as cuota_router
from modules.budgets.user_budget_settings_router import (
    router as user_budget_settings_router,
)
from modules.email.router import router as email_router
from modules.households.router import router as households_router, invite_router
from modules.transactions.router import router as transactions_router
from modules.whatsapp.router import router as whatsapp_router
from modules.settings.router import router as settings_router
from modules.bank_connect.router import router as bank_connect_router
from modules.subscriptions.router import router as subscriptions_router
from modules.notifications.router import router as notifications_router
from modules.merchant_review.router import router as merchant_review_router
from modules.merchant_review.train_router import router as train_router
from modules.plaid.router import router as plaid_router
from modules.currencies.router import router as currencies_router
from modules.trips.router import router as trips_router

# Paths that benefit from short private caching (browser-only, per-user data)
_CACHEABLE_PREFIXES = (
    "/auth/me",
    "/transactions/",
    "/budgets/",
    "/households/",
    "/subscriptions/",
    "/currencies",
)


class CacheHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.method == "GET" and any(
            request.url.path.startswith(p) for p in _CACHEABLE_PREFIXES
        ):
            response.headers.setdefault("Cache-Control", "private, max-age=30")
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="Luka API", version="0.1.0")

    # Wire slowapi rate-limiter (used by trip invite-link endpoints).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Build CORS origins from config (no hardcoded URLs)
    origins = {settings.frontend_url, "http://localhost:3000"}
    if settings.cors_origins:
        origins.update(o.strip() for o in settings.cors_origins.split(",") if o.strip())

    app.add_middleware(CacheHeaderMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "app": "luka"}

    @app.get("/ready")
    async def ready(response: Response):
        # Deep healthcheck: confirms Redis + Postgres are actually responsive.
        # Used as Railway's healthcheckPath so a hung Redis surfaces as ⚠
        # on the API service instead of staying invisible.
        checks: dict[str, str] = {}
        ok = True

        try:
            client = aioredis.from_url(
                settings.redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            try:
                await asyncio.wait_for(client.ping(), timeout=2)
                checks["redis"] = "ok"
            finally:
                await client.aclose()
        except Exception as exc:
            checks["redis"] = f"fail: {type(exc).__name__}"
            ok = False

        try:
            async with engine.connect() as conn:
                await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=2)
            checks["db"] = "ok"
        except Exception as exc:
            checks["db"] = f"fail: {type(exc).__name__}"
            ok = False

        if not ok:
            response.status_code = 503
        return {"status": "ok" if ok else "degraded", "checks": checks}

    app.include_router(auth_router)
    app.include_router(households_router)
    app.include_router(invite_router)
    app.include_router(email_router)
    app.include_router(whatsapp_router)
    app.include_router(transactions_router)
    app.include_router(budgets_router)
    app.include_router(cuota_router)
    app.include_router(user_budget_settings_router)
    app.include_router(bank_accounts_router)
    app.include_router(settings_router)
    app.include_router(bank_connect_router)
    app.include_router(subscriptions_router)
    app.include_router(notifications_router)
    app.include_router(merchant_review_router)
    app.include_router(train_router)
    app.include_router(plaid_router)
    app.include_router(currencies_router)
    app.include_router(trips_router)

    return app


app = create_app()
