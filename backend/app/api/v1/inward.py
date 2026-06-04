import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.inward import InwardSession, InwardItem, InwardSessionParticipant
from app.models.user import User
from app.schemas import (
    InwardSessionOut, InwardSessionDetail, InwardItemOut,
    UpdateInwardItemRequest, CompleteInwardRequest, BatchUpdateRequest,
)
from app.schemas.common import PaginatedResponse
from app.services.inward_service import (
    start_inward_session,
    update_inward_item,
    complete_inward_session,
    get_session_with_items,
)
from app.core.exceptions import NotFoundError, ForbiddenError

router = APIRouter(prefix="/inward", tags=["inward"])


def _session_to_out(session: InwardSession, include_items: bool = False):
    """Build response dict from session ORM object."""
    items = session.items if hasattr(session, "items") else []
    shortage_count = sum(1 for i in items if i.variance_type == "shortage")
    excess_count = sum(1 for i in items if i.variance_type == "excess")

    base = {
        "id": session.id,
        "status": session.status,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "notes": session.notes,
        "total_items": len(items),
        "verified_items": sum(1 for i in items if i.received_qty is not None),
        "completion_pct": session.completion_pct if items else 0.0,
        "shortage_count": shortage_count,
        "excess_count": excess_count,
        "transfer_order": session.transfer_order if hasattr(session, "transfer_order") else None,
        "participants": [
            {
                "user_id": p.user_id,
                "full_name": p.user.full_name if p.user else "Unknown",
                "last_active_at": p.last_active_at,
            }
            for p in (session.participants if hasattr(session, "participants") else [])
        ],
    }
    if include_items:
        base["items"] = [
            InwardItemOut.from_orm_with_verifier(i) for i in items
        ]
    return base


@router.post("/start/{transfer_order_id}", response_model=InwardSessionOut)
async def start_session(
    transfer_order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start an inward verification session for a transfer order."""
    session = await start_inward_session(
        db,
        transfer_order_id=transfer_order_id,
        tenant_id=current_user.tenant_id,
        current_user=current_user,
    )
    # Reload with items for response
    session = await get_session_with_items(
        db, session_id=session.id, tenant_id=current_user.tenant_id
    )
    return _session_to_out(session)


@router.get("/active", response_model=list[InwardSessionOut])
async def list_active_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all in-progress inward sessions visible to the current user."""
    from app.models.transfer_order import TransferOrder

    q = (
        select(InwardSession)
        .options(
            selectinload(InwardSession.items),
            selectinload(InwardSession.participants).selectinload(
                InwardSessionParticipant.user
            ),
            selectinload(InwardSession.transfer_order)
            .selectinload(TransferOrder.depot),
            selectinload(InwardSession.transfer_order)
            .selectinload(TransferOrder.store),
        )
        .where(
            InwardSession.tenant_id == current_user.tenant_id,
            InwardSession.status == "in_progress",
        )
    )
    if current_user.role in ("store_manager", "store_staff") and current_user.store_id:
        q = q.where(InwardSession.store_id == current_user.store_id)

    result = await db.execute(q)
    sessions = result.scalars().all()
    return [_session_to_out(s) for s in sessions]


@router.get("/by-transfer/{transfer_order_id}", response_model=InwardSessionDetail)
async def get_session_by_transfer_order(
    transfer_order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve the in-progress/completed inward session for a transfer order."""
    from app.models.transfer_order import TransferOrder

    result = await db.execute(
        select(InwardSession)
        .options(
            selectinload(InwardSession.items)
            .selectinload(InwardItem.verifier),
            selectinload(InwardSession.participants)
            .selectinload(InwardSessionParticipant.user),
            selectinload(InwardSession.transfer_order)
            .selectinload(TransferOrder.depot),
            selectinload(InwardSession.transfer_order)
            .selectinload(TransferOrder.store),
        )
        .where(
            InwardSession.transfer_order_id == transfer_order_id,
            InwardSession.tenant_id == current_user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("InwardSession", str(transfer_order_id))

    if (
        current_user.role in ("store_manager", "store_staff")
        and current_user.store_id
        and session.store_id != current_user.store_id
    ):
        raise ForbiddenError("Access denied to this inward session.")

    return _session_to_out(session, include_items=True)


@router.get("/{session_id}", response_model=InwardSessionDetail)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full session detail including all inward items."""
    session = await get_session_with_items(
        db, session_id=session_id, tenant_id=current_user.tenant_id
    )

    # Store-scope check
    if (
        current_user.role in ("store_manager", "store_staff")
        and current_user.store_id
        and session.store_id != current_user.store_id
    ):
        raise ForbiddenError("Access denied to this inward session.")

    return _session_to_out(session, include_items=True)


@router.put("/{session_id}/items/{item_id}", response_model=InwardItemOut)
async def update_item(
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    body: UpdateInwardItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Record received quantity and expiry date for one inward item.
    Any participant (store_staff or above) can update any item.
    """
    item = await update_inward_item(
        db,
        session_id=session_id,
        item_id=item_id,
        received_qty=body.received_qty,
        expiry_date=body.expiry_date,
        notes=body.notes,
        current_user=current_user,
    )
    return InwardItemOut.from_orm_with_verifier(item)


@router.put("/{session_id}/items", response_model=list[InwardItemOut])
async def batch_update_items(
    session_id: uuid.UUID,
    body: BatchUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update multiple inward items in one request.
    Designed for keyboard-fast entry flows where manager inputs several rows quickly.
    """
    updated = []
    for update_req in body.updates:
        item = await update_inward_item(
            db,
            session_id=session_id,
            item_id=update_req.item_id,
            received_qty=update_req.received_qty,
            expiry_date=update_req.expiry_date,
            notes=update_req.notes,
            current_user=current_user,
        )
        updated.append(InwardItemOut.from_orm_with_verifier(item))
    return updated


@router.post("/{session_id}/complete", response_model=InwardSessionDetail)
async def complete_session(
    session_id: uuid.UUID,
    body: CompleteInwardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Finalise the inward session. Triggers automatic discrepancy creation.
    Unverified items are treated as received_qty = 0.
    Stock is recorded immediately — inward is NEVER blocked.
    """
    session, discrepancies = await complete_inward_session(
        db,
        session_id=session_id,
        notes=body.notes,
        tenant_id=current_user.tenant_id,
        current_user=current_user,
    )
    session = await get_session_with_items(
        db, session_id=session.id, tenant_id=current_user.tenant_id
    )
    return _session_to_out(session, include_items=True)
