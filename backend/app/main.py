from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiters
from app.routers import (
    admin,
    announcements,
    auth,
    catalogue,
    change_notices,
    check,
    companies,
    health,
    orders,
    suppliers,
    units,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="FoodLens API", version="0.1.0")
    app.state.settings = settings
    app.state.rate_limiters = RateLimiters(settings)
    app.state.upload_dir = Path(settings.upload_dir).resolve()
    app.state.public_base_url = settings.public_base_url
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Retry-After", "Content-Disposition", "X-FoodLens-Label-Warning"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(companies.router)
    app.include_router(catalogue.router)
    app.include_router(change_notices.router)
    app.include_router(announcements.router)
    app.include_router(admin.router)
    app.include_router(suppliers.router)
    app.include_router(units.router)
    app.include_router(check.router)
    if settings.orders_enabled:
        app.include_router(orders.router)
    return app


app = create_app()
