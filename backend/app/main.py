from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiters
from app.routers import admin, auth, companies, health, lookups, suppliers


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="FoodLens API", version="0.1.0")
    app.state.rate_limiters = RateLimiters(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Retry-After"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(lookups.router)
    app.include_router(companies.router)
    app.include_router(admin.router)
    app.include_router(suppliers.router)
    return app


app = create_app()
