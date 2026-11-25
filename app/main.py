from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.auth import router as auth_router
from app.api.catalog import router as catalog_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.internal_agent import router as internal_agent_router
from app.api.health import router as health_router
from app.api.orders import admin_router, router as orders_router
from app.core.errors import RequestIdMiddleware, register_error_handlers
from app.core.rate_limit import SlidingWindowRateLimiter


def create_app() -> FastAPI:
    application = FastAPI(
        title="Smart Food Ordering & Restaurant Assistant",
        version="0.1.0",
        description="Fictional restaurant ordering API and assistant.",
    )
    application.state.rate_limiter = SlidingWindowRateLimiter()
    application.add_middleware(RequestIdMiddleware)
    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(catalog_router)
    application.include_router(orders_router)
    application.include_router(admin_router)
    application.include_router(chat_router)
    application.include_router(documents_router)
    application.include_router(internal_agent_router)
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        @application.get("/register", include_in_schema=False)
        def registration_page() -> FileResponse:
            return FileResponse(frontend_dir / "register.html")

        application.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return application


app = create_app()
