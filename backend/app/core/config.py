from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://pharma:pharmasecret@localhost:5432/pharmatrackrx"

    # Redis
    redis_url: str = "redis://:redissecret@localhost:6379/0"

    # Security
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # S3 / MinIO
    s3_endpoint_url: Optional[str] = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin123"
    s3_bucket: str = "pharmatrackrx"
    s3_region: str = "us-east-1"

    # App
    environment: str = "development"
    debug: bool = True
    allowed_origins: str = "http://localhost:5173,http://localhost:80"
    api_prefix: str = "/api/v1"
    app_name: str = "PharmaTrackRx"
    app_version: str = "1.0.0"

    # Initial tenant setup
    default_tenant_name: str = "Prince Pharma"
    default_admin_email: str = "admin@princepharma.com"
    default_admin_password: str = "changeme123"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
