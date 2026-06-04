"""
Test fixtures — provides isolated async DB sessions and seeded data.
Uses SQLite (aiosqlite) for speed; schema is created fresh for each test session.
"""
import uuid
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import create_app
from app.db.base import Base
from app.db.session import get_db
from app.models import Tenant, User, Depot, Store
from app.core.security import hash_password

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def seeded_db(db: AsyncSession):
    """Provides a DB session with a tenant, admin user, depot, and store."""
    tenant = Tenant(name="Test Pharma", subdomain="test-pharma")
    db.add(tenant)
    await db.flush()

    admin = User(
        tenant_id=tenant.id,
        email="admin@test.com",
        full_name="Test Admin",
        hashed_password=hash_password("testpass123"),
        role="admin",
    )
    manager = User(
        tenant_id=tenant.id,
        email="manager@test.com",
        full_name="Store Manager",
        hashed_password=hash_password("testpass123"),
        role="store_manager",
    )
    depot_user = User(
        tenant_id=tenant.id,
        email="depot@test.com",
        full_name="Depot Staff",
        hashed_password=hash_password("testpass123"),
        role="depot_staff",
    )
    depot = Depot(tenant_id=tenant.id, name="MITENDI WAREHOUSE")
    store = Store(tenant_id=tenant.id, name="BOMA P1")

    db.add_all([admin, manager, depot_user, depot, store])
    await db.flush()

    manager.store_id = store.id
    depot_user.depot_id = depot.id
    await db.flush()

    yield {
        "tenant": tenant,
        "admin": admin,
        "manager": manager,
        "depot_user": depot_user,
        "depot": depot,
        "store": store,
        "db": db,
    }


@pytest_asyncio.fixture
async def client(seeded_db):
    """HTTPX async client bound to the FastAPI app with injected DB."""
    app = create_app()

    async def override_get_db():
        yield seeded_db["db"]

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, seeded_db


async def get_auth_token(client: AsyncClient, email: str, password: str = "testpass123") -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
