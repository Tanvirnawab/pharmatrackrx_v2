import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.intelligence_service import (
    get_expiry_patterns,
    get_high_frequency_discrepancies,
    get_batch_patterns,
    get_expiry_risk_items,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/expiry-patterns")
async def expiry_patterns(
    days: int = Query(90, ge=7, le=365),
    limit: int = Query(20, ge=1, le=100),
    store_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Medicines repeatedly received with the same expiry date."""
    sid = store_id if current_user.role == "admin" else current_user.store_id
    return await get_expiry_patterns(
        db, tenant_id=current_user.tenant_id, days=days, store_id=sid, limit=limit
    )


@router.get("/high-frequency-discrepancies")
async def high_frequency_discrepancies(
    days: int = Query(90, ge=7, le=365),
    min_occurrences: int = Query(3, ge=2, le=50),
    limit: int = Query(20, ge=1, le=100),
    store_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Medicines with repeated discrepancies — systemic issues."""
    sid = store_id if current_user.role == "admin" else current_user.store_id
    return await get_high_frequency_discrepancies(
        db, tenant_id=current_user.tenant_id, days=days,
        min_occurrences=min_occurrences, store_id=sid, limit=limit
    )


@router.get("/batch-patterns")
async def batch_patterns(
    days: int = Query(90, ge=7, le=365),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Batch numbers appearing across multiple transfers — traceability foundation."""
    return await get_batch_patterns(
        db, tenant_id=current_user.tenant_id, days=days, limit=limit
    )


@router.get("/expiry-risk")
async def expiry_risk(
    days_threshold: int = Query(90, ge=7, le=365),
    limit: int = Query(30, ge=1, le=100),
    store_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Items received with expiry within N days — wastage risk."""
    sid = store_id if current_user.role == "admin" else current_user.store_id
    return await get_expiry_risk_items(
        db, tenant_id=current_user.tenant_id,
        days_threshold=days_threshold, store_id=sid, limit=limit
    )
