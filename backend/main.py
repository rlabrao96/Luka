from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from modules.auth.router import router as auth_router
from modules.households.router import router as households_router, invite_router
from modules.email.router import router as email_router
from modules.whatsapp.router import router as whatsapp_router


def create_app() -> FastAPI:
    app = FastAPI(title="Luka API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "app": "luka"}

    app.include_router(auth_router)
    app.include_router(households_router)
    app.include_router(invite_router)
    app.include_router(email_router)
    app.include_router(whatsapp_router)

    return app


app = create_app()
