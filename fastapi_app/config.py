from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "bookworms"
    postgres_user: str = "bookworms"
    postgres_password: str = ""

    # Override full URL if set (takes precedence)
    database_url: str | None = None

    # Same secret Django SimpleJWT uses (DJANGO_SECRET_KEY)
    django_secret_key: str = "django-insecure-dev-only"

    # Align with Django JWT_ACCESS_DAYS / JWT_REFRESH_DAYS when set;
    # FastAPI also accepts minute-level access lifetime.
    jwt_access_days: int = 7
    jwt_access_minutes: int | None = None
    jwt_refresh_days: int = 30

    skip_email_activation: bool = False

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def access_token_timedelta_seconds(self) -> int:
        if self.jwt_access_minutes is not None:
            return max(1, self.jwt_access_minutes) * 60
        return max(1, self.jwt_access_days) * 86400

    @property
    def refresh_token_timedelta_seconds(self) -> int:
        return max(1, self.jwt_refresh_days) * 86400


@lru_cache
def get_settings() -> Settings:
    return Settings()
