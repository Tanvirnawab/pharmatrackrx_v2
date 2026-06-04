"""
Analytics service — dynamic SQL avoids asyncpg AmbiguousParameterError.
Never pass NULL as a typed bind parameter — build WHERE clauses dynamically.
"""
import uuid
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from app.models.transfer_order import TransferOrder, TransferOrderStatus
from app.models.discrepancy import Discrepancy, DiscrepancyStatus


async def get_dashboard_summary(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    store_id: Optional[uuid.UUID] = None,
    depot_id: Optional[uuid.UUID] = None,
) -> dict:
    filters = [TransferOrder.tenant_id == tenant_id]
    disc_filters = [Discrepancy.tenant_id == tenant_id]
    if store_id:
        filters.append(TransferOrder.store_id == store_id)
        disc_filters.append(Discrepancy.store_id == store_id)
    if depot_id:
        filters.append(TransferOrder.depot_id == depot_id)
        disc_filters.append(Discrepancy.depot_id == depot_id)

    pending_q = await db.execute(
        select(func.count()).where(*filters,
            TransferOrder.status == TransferOrderStatus.PENDING.value))
    in_progress_q = await db.execute(
        select(func.count()).where(*filters,
            TransferOrder.status == TransferOrderStatus.IN_PROGRESS.value))
    open_q = await db.execute(
        select(func.count()).where(*disc_filters,
            Discrepancy.status == DiscrepancyStatus.OPEN))
    open_count = open_q.scalar() or 0
    week_ago = date.today() - timedelta(days=7)
    resolved_q = await db.execute(
        select(func.count()).where(
            *disc_filters,
            Discrepancy.status.in_([DiscrepancyStatus.ADMIN_RESOLVED, DiscrepancyStatus.CLOSED]),
            Discrepancy.resolved_at >= week_ago,
        )
    )

    # Accuracy — build WHERE string dynamically to avoid NULL params
    thirty_ago = date.today() - timedelta(days=30)
    acc_where = "t.tenant_id = :tid AND s.status='completed' AND s.completed_at >= :since"
    acc_params: dict = {"tid": str(tenant_id), "since": thirty_ago}
    if store_id:
        acc_where += " AND t.store_id = :sid"
        acc_params["sid"] = str(store_id)
    if depot_id:
        acc_where += " AND t.depot_id = :did"
        acc_params["did"] = str(depot_id)

    acc_sql = text(f"""
        SELECT ROUND(100.0 * COUNT(CASE WHEN ii.variance_type='match' THEN 1 END)
               / NULLIF(COUNT(ii.id),0), 1) AS accuracy
        FROM inward_sessions s
        JOIN transfer_orders t ON t.id = s.transfer_order_id
        JOIN inward_items ii   ON ii.session_id = s.id
        WHERE {acc_where}
    """)
    acc = (await db.execute(acc_sql, acc_params)).scalar()

    return {
        "pending_inwards": pending_q.scalar() or 0,
        "in_progress_inwards": in_progress_q.scalar() or 0,
        "open_discrepancies": open_count,
        "depot_pending_response": open_count,
        "resolved_this_week": resolved_q.scalar() or 0,
        "transfer_accuracy_30d": float(acc or 100.0),
    }


async def get_discrepancy_trends(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    days: int = 30,
    store_id: Optional[uuid.UUID] = None,
    depot_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    where = "d.tenant_id=:tid AND d.created_at >= CURRENT_DATE - :days * INTERVAL '1 day'"
    p: dict = {"tid": str(tenant_id), "days": days}
    if store_id:
        where += " AND d.store_id=:sid"; p["sid"] = str(store_id)
    if depot_id:
        where += " AND d.depot_id=:did"; p["did"] = str(depot_id)
    rows = (await db.execute(text(f"""
        SELECT DATE(d.created_at) AS day_key, d.type, COUNT(*) AS cnt,
               SUM(ABS(d.variance_qty)) tot
        FROM discrepancies d WHERE {where}
        GROUP BY DATE(d.created_at), d.type ORDER BY day_key
    """), p)).all()
    return [{"day": str(r.day_key), "type": r.type, "count": r.cnt,
             "total_variance": float(r.tot or 0)} for r in rows]


async def get_top_discrepancy_items(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int = 10,
    days: int = 30,
    store_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    where = "d.tenant_id=:tid AND d.created_at >= CURRENT_DATE - :days * INTERVAL '1 day'"
    p: dict = {"tid": str(tenant_id), "days": days, "lim": limit}
    if store_id:
        where += " AND d.store_id=:sid"; p["sid"] = str(store_id)
    rows = (await db.execute(text(f"""
        SELECT d.item_name,
               COUNT(*) dc,
               SUM(CASE WHEN d.type='shortage' THEN 1 ELSE 0 END) sh,
               SUM(CASE WHEN d.type='excess'   THEN 1 ELSE 0 END) ex,
               SUM(ABS(d.variance_qty)) tv,
               AVG(ABS(d.variance_qty)) av
        FROM discrepancies d WHERE {where}
        GROUP BY d.item_name ORDER BY dc DESC LIMIT :lim
    """), p)).all()
    return [{"item_name": r.item_name, "discrepancy_count": r.dc, "shortages": r.sh,
             "excesses": r.ex, "total_variance_qty": float(r.tv or 0),
             "avg_variance_qty": float(r.av or 0)} for r in rows]


async def get_depot_performance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    days: int = 30,
) -> list[dict]:
    rows = (await db.execute(text("""
        SELECT dep.id did, dep.name dn,
               COUNT(DISTINCT t.id) tt,
               COUNT(ii.id) ti,
               COUNT(CASE WHEN ii.variance_type='match'    THEN 1 END) mi,
               COUNT(CASE WHEN ii.variance_type='shortage' THEN 1 END) si,
               COUNT(CASE WHEN ii.variance_type='excess'   THEN 1 END) ei,
               ROUND(100.0 * COUNT(CASE WHEN ii.variance_type='match' THEN 1 END)
                     / NULLIF(COUNT(ii.id),0), 1) ap
        FROM depots dep
        JOIN transfer_orders t ON t.depot_id=dep.id
        JOIN inward_sessions s ON s.transfer_order_id=t.id
        JOIN inward_items ii   ON ii.session_id=s.id
        WHERE dep.tenant_id=:tid AND s.status='completed'
          AND s.completed_at >= CURRENT_DATE - :days * INTERVAL '1 day'
        GROUP BY dep.id, dep.name ORDER BY ap
    """), {"tid": str(tenant_id), "days": days})).all()
    return [{"depot_id": str(r.did), "depot_name": r.dn, "total_transfers": r.tt,
             "total_items": r.ti, "matched_items": r.mi, "shortage_items": r.si,
             "excess_items": r.ei, "accuracy_pct": float(r.ap or 0)} for r in rows]


async def get_avg_resolution_time(
    db: AsyncSession, *, tenant_id: uuid.UUID, days: int = 30
) -> float:
    val = (await db.execute(text("""
        SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))/3600)
        FROM discrepancies
        WHERE tenant_id=:tid AND resolved_at IS NOT NULL
          AND created_at >= CURRENT_DATE - :days * INTERVAL '1 day'
    """), {"tid": str(tenant_id), "days": days})).scalar()
    return round(float(val), 1) if val else 0.0
