"""
PharmaTrackRx — FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import PharmaException, pharma_exception_handler
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables (safety net) then seed default tenant."""
    await _create_tables_if_missing()
    await _ensure_default_tenant()
    yield


async def _create_tables_if_missing():
    """
    Safety net: create all tables if they don't exist.
    In production the entrypoint.sh runs alembic upgrade head first.
    This keeps local `uvicorn app.main:app --reload` working without migration.
    """
    from app.db.session import engine
    from app.db.base import Base
    import app.models  # noqa — registers all models
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"⚠  create_all warning: {e}")


async def _ensure_default_tenant():
    """
    Seed the default Prince Pharma tenant and admin on first run.
    Idempotent: does nothing if a tenant already exists.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.core.security import hash_password
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Tenant).limit(1))
            if result.scalar_one_or_none():
                return  # already seeded

            tenant = Tenant(
                name=settings.default_tenant_name,
                subdomain="prince-pharma",
            )
            db.add(tenant)
            await db.flush()

            admin = User(
                tenant_id=tenant.id,
                email=settings.default_admin_email,
                full_name="System Admin",
                hashed_password=hash_password(settings.default_admin_password),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            await db.commit()
            print(
                f"✓ Seeded tenant '{tenant.name}' and admin '{admin.email}'. "
                "Change the password immediately!"
            )
        except Exception as e:
            await db.rollback()
            print(f"⚠  Seeding skipped: {e}")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Transfer verification and discrepancy management SaaS "
            "for pharmaceutical distributors."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(PharmaException, pharma_exception_handler)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()
