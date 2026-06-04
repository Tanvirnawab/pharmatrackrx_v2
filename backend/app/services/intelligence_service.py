"""
Intelligence service — V2 analytics beyond basic discrepancy counts.
All queries use dynamic SQL to avoid asyncpg NULL bind parameter issues.
"""
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def get_expiry_patterns(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    days: int = 90,
    store_id: Optional[uuid.UUID] = None,
    limit: int = 20,
) -> list[dict]:
    """
    Medicines that are repeatedly received with the same expiry date.
    Useful for identifying slow-moving stock or supplier batch patterns.
    """
    where = (
        "s.status='completed' AND t.tenant_id=:tid "
        "AND ii.expiry_date IS NOT NULL "
        "AND s.completed_at >= CURRENT_DATE - :days * INTERVAL '1 day'"
    )
    params: dict = {"tid": str(tenant_id), "days": days, "lim": limit}
    if store_id:
        where += " AND t.store_id=:sid"
        params["sid"] = str(store_id)

    sql = text(f"""
        SELECT ii.item_name,
               ii.expiry_date,
               COUNT(*) AS occurrences,
               MIN(s.completed_at)::date AS first_seen,
               MAX(s.completed_at)::date AS last_seen,
               STRING_AGG(DISTINCT dep.name, ', ') AS depots
        FROM inward_items ii
        JOIN inward_sessions s  ON s.id = ii.session_id
        JOIN transfer_orders t  ON t.id = s.transfer_order_id
        JOIN depots dep          ON dep.id = t.depot_id
        WHERE {where}
        GROUP BY ii.item_name, ii.expiry_date
        HAVING COUNT(*) > 1
        ORDER BY occurrences DESC
        LIMIT :lim
    """)
    rows = (await db.execute(sql, params)).all()
    return [
        {
            "item_name": r.item_name,
            "expiry_date": str(r.expiry_date),
            "occurrences": r.occurrences,
            "first_seen": str(r.first_seen),
            "last_seen": str(r.last_seen),
            "depots": r.depots,
        }
        for r in rows
    ]


async def get_high_frequency_discrepancies(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    days: int = 90,
    min_occurrences: int = 3,
    store_id: Optional[uuid.UUID] = None,
    limit: int = 20,
) -> list[dict]:
    """
    Medicines with repeated discrepancies — indicates systemic counting or
    dispatch issues with specific products.
    """
    where = "d.tenant_id=:tid AND d.created_at >= CURRENT_DATE - :days * INTERVAL '1 day'"
    params: dict = {"tid": str(tenant_id), "days": days, "lim": limit, "min": min_occurrences}
    if store_id:
        where += " AND d.store_id=:sid"
        params["sid"] = str(store_id)

    sql = text(f"""
        SELECT d.item_name,
               COUNT(*) AS total_discrepancies,
               SUM(CASE WHEN d.type='shortage' THEN 1 ELSE 0 END) AS shortage_count,
               SUM(CASE WHEN d.type='excess'   THEN 1 ELSE 0 END) AS excess_count,
               AVG(ABS(d.variance_qty))::numeric(10,2) AS avg_variance,
               SUM(ABS(d.variance_qty))::numeric(12,2) AS total_variance,
               COUNT(CASE WHEN d.status IN ('open','depot_responded') THEN 1 END) AS unresolved,
               STRING_AGG(DISTINCT dep.name, ', ') AS depots_involved
        FROM discrepancies d
        JOIN depots dep ON dep.id = d.depot_id
        WHERE {where}
        GROUP BY d.item_name
        HAVING COUNT(*) >= :min
        ORDER BY total_discrepancies DESC
        LIMIT :lim
    """)
    rows = (await db.execute(sql, params)).all()
    return [
        {
            "item_name": r.item_name,
            "total_discrepancies": r.total_discrepancies,
            "shortage_count": r.shortage_count,
            "excess_count": r.excess_count,
            "avg_variance": float(r.avg_variance or 0),
            "total_variance": float(r.total_variance or 0),
            "unresolved": r.unresolved,
            "depots_involved": r.depots_involved,
        }
        for r in rows
    ]


async def get_batch_patterns(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    days: int = 90,
    limit: int = 20,
) -> list[dict]:
    """
    Batch numbers seen across multiple transfers or stores.
    Foundations for recall traceability.
    """
    sql = text("""
        SELECT br.batch_number,
               ii.item_name,
               COUNT(DISTINCT t.id) AS transfer_count,
               COUNT(DISTINCT t.store_id) AS store_count,
               MIN(br.expiry_date) AS earliest_expiry,
               MAX(br.expiry_date) AS latest_expiry,
               SUM(br.quantity) AS total_qty
        FROM batch_records br
        JOIN inward_items ii   ON ii.id = br.inward_item_id
        JOIN inward_sessions s ON s.id = ii.session_id
        JOIN transfer_orders t ON t.id = s.transfer_order_id
        WHERE br.tenant_id = :tid
          AND br.batch_number IS NOT NULL
          AND s.completed_at >= CURRENT_DATE - :days * INTERVAL '1 day'
        GROUP BY br.batch_number, ii.item_name
        HAVING COUNT(DISTINCT t.id) > 1
        ORDER BY transfer_count DESC
        LIMIT :lim
    """)
    rows = (await db.execute(
        sql, {"tid": str(tenant_id), "days": days, "lim": limit}
    )).all()
    return [
        {
            "batch_number": r.batch_number,
            "item_name": r.item_name,
            "transfer_count": r.transfer_count,
            "store_count": r.store_count,
            "earliest_expiry": str(r.earliest_expiry) if r.earliest_expiry else None,
            "latest_expiry": str(r.latest_expiry) if r.latest_expiry else None,
            "total_qty": float(r.total_qty or 0),
        }
        for r in rows
    ]


async def get_expiry_risk_items(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    days_threshold: int = 90,
    store_id: Optional[uuid.UUID] = None,
    limit: int = 30,
) -> list[dict]:
    """
    Items received with expiry within N days from today — potential wastage risk.
    """
    where = (
        "s.status='completed' AND t.tenant_id=:tid "
        "AND ii.expiry_date IS NOT NULL "
        "AND ii.expiry_date <= CURRENT_DATE + :thresh * INTERVAL '1 day' "
        "AND ii.expiry_date >= CURRENT_DATE"
    )
    params: dict = {"tid": str(tenant_id), "thresh": days_threshold, "lim": limit}
    if store_id:
        where += " AND t.store_id=:sid"
        params["sid"] = str(store_id)

    sql = text(f"""
        SELECT ii.item_name,
               ii.expiry_date,
               ii.received_qty,
               st.name AS store_name,
               dep.name AS depot_name,
               t.to_number,
               (ii.expiry_date - CURRENT_DATE) AS days_until_expiry
        FROM inward_items ii
        JOIN inward_sessions s  ON s.id = ii.session_id
        JOIN transfer_orders t  ON t.id = s.transfer_order_id
        JOIN stores st           ON st.id = t.store_id
        JOIN depots dep          ON dep.id = t.depot_id
        WHERE {where}
        ORDER BY ii.expiry_date ASC
        LIMIT :lim
    """)
    rows = (await db.execute(sql, params)).all()
    return [
        {
            "item_name": r.item_name,
            "expiry_date": str(r.expiry_date),
            "received_qty": float(r.received_qty or 0),
            "store_name": r.store_name,
            "depot_name": r.depot_name,
            "to_number": r.to_number,
            "days_until_expiry": int(r.days_until_expiry),
        }
        for r in rows
    ]
