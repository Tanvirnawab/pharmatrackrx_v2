from functools import lru_cache
from typing import Optional
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _normalize_database_url(value: str) -> str:
    url = value.strip().strip('"').strip("'")

    while url.upper().startswith("DATABASE_URL="):
        url = url.split("=", 1)[1].strip().strip('"').strip("'")

    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    return url


def _query_has_ssl_required(url: str) -> bool:
    query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    return query.get("ssl", "").lower() in {"true", "1", "require", "required"} or query.get("sslmode", "").lower() in {
        "require",
        "verify-ca",
        "verify-full",
    }


def sqlalchemy_database_url(url: str) -> str:
    parsed = urlsplit(_normalize_database_url(url))
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key not in {"ssl", "sslmode"}]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def asyncpg_connect_args(url: str) -> dict:
    if _query_has_ssl_required(_normalize_database_url(url)):
        return {"ssl": True}
    return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://pharma:pharmasecret@localhost:5432/pharmatrackrx"

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return _normalize_database_url(str(value))

    @property
    def sqlalchemy_database_url(self) -> str:
        return sqlalchemy_database_url(self.database_url)

    @property
    def asyncpg_connect_args(self) -> dict:
        return asyncpg_connect_args(self.database_url)

    # Redis
    redis_url: str = "redis://:redissecret@localhost:6379/0"

    # Security
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # S3 / MinIO
    s3_endpoint_url: Optional[str] = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
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
    default_admin_email: str = ""
    default_admin_password: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def validate_debug(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in {"release", "prod", "production"}:
            return False
        return value

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
