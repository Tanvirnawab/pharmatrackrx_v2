"""Admin endpoints — user/depot/store management."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_admin
from app.core.security import hash_password
from app.core.exceptions import ConflictError, NotFoundError
from app.models.user import User
from app.models.depot_store import Depot, Store
from app.models.audit_notif import AuditLog, Notification
from app.schemas import UserOut, UserCreate, UserUpdate, DepotOut, StoreOut, NotificationOut
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=PaginatedResponse[UserOut])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    filters = [User.tenant_id == current_user.tenant_id, User.deleted_at.is_(None)]
    count_q = await db.execute(select(func.count()).select_from(User).where(*filters))
    total = count_q.scalar() or 0
    q = (
        select(User).where(*filters)
        .order_by(User.full_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    users = result.scalars().all()
    return PaginatedResponse(
        items=[UserOut.model_validate(u) for u in users],
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = await db.execute(
        select(User).where(
            User.email == body.email,
            User.tenant_id == current_user.tenant_id,
            User.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"User with email '{body.email}' already exists.")

    user = User(
        tenant_id=current_user.tenant_id,
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
        store_id=body.store_id,
        depot_id=body.depot_id,
    )
    db.add(user)
    await db.flush()
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User", str(user_id))

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    return UserOut.model_validate(user)


# ── Depots ────────────────────────────────────────────────────────────────────

@router.get("/depots", response_model=list[DepotOut])
async def list_depots(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Depot)
        .where(Depot.tenant_id == current_user.tenant_id, Depot.is_active == True)
        .order_by(Depot.name)
    )
    return [DepotOut.model_validate(d) for d in result.scalars().all()]


# ── Stores ────────────────────────────────────────────────────────────────────

@router.get("/stores", response_model=list[StoreOut])
async def list_stores(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Store)
        .where(Store.tenant_id == current_user.tenant_id, Store.is_active == True)
        .order_by(Store.name)
    )
    return [StoreOut.model_validate(s) for s in result.scalars().all()]


# ── Audit logs ────────────────────────────────────────────────────────────────

@router.get("/audit-logs")
async def audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    entity_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    filters = [AuditLog.tenant_id == current_user.tenant_id]
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)

    count_q = await db.execute(select(func.count()).select_from(AuditLog).where(*filters))
    total = count_q.scalar() or 0
    q = (
        select(AuditLog).where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": str(log.id),
                "actor_name": log.actor_name,
                "actor_role": log.actor_role,
                "entity_type": log.entity_type,
                "entity_id": str(log.entity_id),
                "entity_label": log.entity_label,
                "action": log.action,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
