from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.networks import parse_networks


class Settings(BaseSettings):
    """Application settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://foodlens:foodlens_dev@localhost:5433/foodlens"
    test_database_url: str = (
        "postgresql+psycopg://foodlens:foodlens_dev@localhost:5433/foodlens_test"
    )
    cors_origins: list[str] = ["http://localhost:3000"]

    # Auth (docs/DECISIONS.md D12, D24, D31-D38)
    session_cookie_name: str = "foodlens_session"
    session_ttl_hours: int = 24
    # Must be true anywhere served over HTTPS.
    session_cookie_secure: bool = False
    bcrypt_rounds: int = 12

    # Rate limits, per client network (IP). Token buckets: a burst, then a steady refill.
    rate_limit_enabled: bool = True
    rate_limit_lookup_burst: int = Field(default=20, ge=1)
    rate_limit_lookup_refill_per_second: float = Field(default=1.0, gt=0)
    rate_limit_login_per_minute: int = Field(default=5, ge=1)  # per IP + email
    rate_limit_register_per_hour: int = Field(default=5, ge=1)
    # Comma-separated IPs or CIDR ranges never limited, e.g. usability-test machines.
    rate_limit_exempt_ips: str = ""
    # Proxies whose X-Forwarded-For header is trusted (the Next.js server).
    trusted_proxy_ips: str = "127.0.0.1,::1"

    # Private folder for change-notice attachments (relative to backend/). Never served statically.
    upload_dir: str = "storage/notices"

    # Seed admin, created by `uv run python -m app.seed` when both are set.
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    seed_admin_display_name: str = "FoodLens Demo Admin"

    @field_validator("rate_limit_exempt_ips", "trusted_proxy_ips")
    @classmethod
    def valid_ip_list(cls, value: str) -> str:
        # Fail at startup on a typo rather than silently limiting a test machine.
        parse_networks(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
