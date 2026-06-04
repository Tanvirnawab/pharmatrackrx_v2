import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas import (
    DashboardSummary, DiscrepancyTrendPoint, TopDiscrepancyItem, DepotPerformance
)
from app.services.analytics_service import (
    get_dashboard_summary,
    get_discrepancy_trends,
    get_top_discrepancy_items,
    get_depot_performance,
    get_avg_resolution_time,
)

router = APIRouter(tags=["reports"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KPI cards: pending inwards, open discrepancies, transfer accuracy."""
    store_id = current_user.store_id if current_user.role != "admin" else None
    depot_id = current_user.depot_id if current_user.role == "depot_staff" else None
    data = await get_dashboard_summary(
        db, tenant_id=current_user.tenant_id, store_id=store_id, depot_id=depot_id
    )
    return DashboardSummary(**data)


@router.get("/reports/discrepancy-trends", response_model=list[DiscrepancyTrendPoint])
async def discrepancy_trends(
    days: int = Query(30, ge=7, le=365),
    store_id: Optional[uuid.UUID] = Query(None),
    depot_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Non-admins can only see their own scope
    if current_user.role != "admin":
        store_id = current_user.store_id
        depot_id = current_user.depot_id
    data = await get_discrepancy_trends(
        db, tenant_id=current_user.tenant_id, days=days,
        store_id=store_id, depot_id=depot_id
    )
    return [DiscrepancyTrendPoint(**row) for row in data]


@router.get("/reports/top-medicines", response_model=list[TopDiscrepancyItem])
async def top_discrepancy_medicines(
    days: int = Query(30, ge=7, le=365),
    limit: int = Query(10, ge=1, le=50),
    store_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        store_id = current_user.store_id
    data = await get_top_discrepancy_items(
        db, tenant_id=current_user.tenant_id, limit=limit, days=days, store_id=store_id
    )
    return [TopDiscrepancyItem(**row) for row in data]


@router.get("/reports/depot-performance", response_model=list[DepotPerformance])
async def depot_performance(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await get_depot_performance(
        db, tenant_id=current_user.tenant_id, days=days
    )
    return [DepotPerformance(**row) for row in data]


@router.get("/reports/avg-resolution-time")
async def avg_resolution_time(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    hours = await get_avg_resolution_time(
        db, tenant_id=current_user.tenant_id, days=days
    )
    return {"avg_resolution_hours": hours, "days": days}
