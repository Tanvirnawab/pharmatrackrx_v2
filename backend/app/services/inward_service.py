"""
Inward service — core business logic for the verification workflow.

Rules:
1. One InwardSession per TransferOrder (enforced by unique constraint)
2. Any store_manager or store_staff for that store can join and update items
3. Inward session can be completed even with unverified items (null → treated as 0)
4. Completing triggers auto-discrepancy creation for all variance != 0 items
5. The inward is never blocked — stock is recorded at actual received qty immediately
"""
import uuid
from decimal import Decimal
from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.transfer_order import TransferOrder, TransferOrderItem, TransferOrderStatus
from app.models.inward import InwardSession, InwardItem, InwardSessionParticipant
from app.models.discrepancy import Discrepancy, DiscrepancyStatus, DiscrepancyType
from app.models.user import User
from app.core.exceptions import (
    NotFoundError, ConflictError, ForbiddenError, BusinessRuleError
)
from app.services.audit_service import write_audit_log
from app.services.notification_service import notify_role, NotifType


async def start_inward_session(
    db: AsyncSession,
    *,
    transfer_order_id: uuid.UUID,
    tenant_id: uuid.UUID,
    current_user: User,
) -> InwardSession:
    """
    Start an inward session for a transfer order.
    Creates InwardItem stubs for all TransferOrderItems.
    """
    # Load transfer order with items
    result = await db.execute(
        select(TransferOrder)
        .options(selectinload(TransferOrder.items))
        .where(
            TransferOrder.id == transfer_order_id,
            TransferOrder.tenant_id == tenant_id,
        )
    )
    transfer = result.scalar_one_or_none()
    if not transfer:
        raise NotFoundError("TransferOrder", str(transfer_order_id))

    if transfer.status == TransferOrderStatus.COMPLETED.value:
        raise BusinessRuleError("This transfer order has already been fully verified.")

    if transfer.status == TransferOrderStatus.CANCELLED.value:
        raise BusinessRuleError("This transfer order has been cancelled.")

    # Check store access
    if (
        current_user.role not in ("admin",)
        and current_user.store_id != transfer.store_id
    ):
        raise ForbiddenError("You can only start inward sessions for your assigned store.")

    # Check if session already exists
    existing = await db.execute(
        select(InwardSession).where(
            InwardSession.transfer_order_id == transfer_order_id
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            "An inward session already exists for this transfer order. "
            "Use the existing session."
        )

    # Create the session
    session = InwardSession(
        tenant_id=tenant_id,
        transfer_order_id=transfer_order_id,
        store_id=transfer.store_id,
        created_by=current_user.id,
        status="in_progress",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()

    # Create InwardItem stubs for every transfer item
    for item in transfer.items:
        inward_item = InwardItem(
            session_id=session.id,
            transfer_item_id=item.id,
            line_number=item.line_number,
            item_name=item.item_name,
            expected_qty=item.expected_qty,
        )
        db.add(inward_item)

    # Add creator as first participant
    participant = InwardSessionParticipant(
        session_id=session.id,
        user_id=current_user.id,
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(participant)

    # Update transfer order status
    transfer.status = TransferOrderStatus.IN_PROGRESS.value

    await write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        entity_type="inward_session",
        entity_id=session.id,
        entity_label=transfer.to_number,
        action="session_started",
        new_values={"transfer_order_id": str(transfer_order_id), "store_id": str(transfer.store_id)},
    )

    return session


async def join_session(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    current_user: User,
) -> InwardSessionParticipant:
    """Register a user as a participant in an active inward session."""
    session = await _get_session_or_404(db, session_id)

    if session.status != "in_progress":
        raise BusinessRuleError("Cannot join a session that is not in progress.")

    # Upsert participant
    result = await db.execute(
        select(InwardSessionParticipant).where(
            InwardSessionParticipant.session_id == session_id,
            InwardSessionParticipant.user_id == current_user.id,
        )
    )
    participant = result.scalar_one_or_none()
    if not participant:
        participant = InwardSessionParticipant(
            session_id=session_id,
            user_id=current_user.id,
            last_active_at=datetime.now(timezone.utc),
        )
        db.add(participant)
    else:
        participant.last_active_at = datetime.now(timezone.utc)

    return participant


async def update_inward_item(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    received_qty: Optional[Decimal],
    expiry_date: Optional[date],
    notes: Optional[str],
    current_user: User,
) -> InwardItem:
    """
    Record actual received quantity and expiry for one inward item.
    Automatically calculates variance and variance_type.
    """
    session = await _get_session_or_404(db, session_id)

    if session.status != "in_progress":
        raise BusinessRuleError("Cannot update items in a completed session.")

    result = await db.execute(
        select(InwardItem).where(
            InwardItem.id == item_id,
            InwardItem.session_id == session_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("InwardItem", str(item_id))

    old_received = item.received_qty

    if received_qty is not None:
        item.received_qty = received_qty
        item.calculate_variance()
        item.verified_by = current_user.id
        item.verified_at = datetime.now(timezone.utc)

    if expiry_date is not None:
        item.expiry_date = expiry_date

    if notes is not None:
        item.notes = notes

    # Update participant last_active_at
    await join_session(db, session_id=session_id, current_user=current_user)

    await write_audit_log(
        db,
        tenant_id=session.tenant_id,
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        entity_type="inward_item",
        entity_id=item.id,
        entity_label=item.item_name,
        action="item_verified",
        old_values={"received_qty": str(old_received) if old_received else None},
        new_values={
            "received_qty": str(received_qty),
            "variance": str(item.variance),
            "variance_type": item.variance_type,
        },
    )

    return item


async def complete_inward_session(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    notes: Optional[str],
    tenant_id: uuid.UUID,
    current_user: User,
) -> tuple[InwardSession, list[Discrepancy]]:
    """
    Finalize an inward session.
    - Null received_qty items are treated as received_qty = 0 (shortage)
    - Auto-creates discrepancy records for all items with variance != 0
    - Inward is never blocked — stock is recorded immediately
    - Transfer order status → completed
    Returns (session, list_of_discrepancies_created)
    """
    session = await db.execute(
        select(InwardSession)
        .options(
            selectinload(InwardSession.items),
            selectinload(InwardSession.transfer_order),
        )
        .where(InwardSession.id == session_id, InwardSession.tenant_id == tenant_id)
    )
    session = session.scalar_one_or_none()
    if not session:
        raise NotFoundError("InwardSession", str(session_id))

    if session.status == "completed":
        raise BusinessRuleError("This session is already completed.")

    if current_user.role not in ("admin", "store_manager"):
        raise ForbiddenError("Only store managers or admins can complete an inward session.")

    if (
        current_user.role != "admin"
        and current_user.store_id != session.store_id
    ):
        raise ForbiddenError("You can only complete sessions for your assigned store.")

    # Finalise all unverified items as received_qty = 0
    for item in session.items:
        if item.received_qty is None:
            item.received_qty = Decimal("0")
            item.calculate_variance()
            item.verified_by = current_user.id
            item.verified_at = datetime.now(timezone.utc)
            item.notes = (item.notes or "") + " [auto-completed as 0]"

    # Mark session completed
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    session.completed_by = current_user.id
    if notes:
        session.notes = notes

    # Mark transfer order completed
    transfer = session.transfer_order
    transfer.status = TransferOrderStatus.COMPLETED.value

    # Auto-create discrepancies for every non-match item
    discrepancies_created: list[Discrepancy] = []
    for item in session.items:
        if item.variance_type in ("shortage", "excess"):
            disc = Discrepancy(
                tenant_id=tenant_id,
                inward_item_id=item.id,
                transfer_order_id=transfer.id,
                depot_id=transfer.depot_id,
                store_id=transfer.store_id,
                raised_by=current_user.id,
                type=item.variance_type,
                status=DiscrepancyStatus.OPEN,
                expected_qty=item.expected_qty,
                received_qty=item.received_qty,
                variance_qty=item.variance,
                item_name=item.item_name,
            )
            db.add(disc)
            discrepancies_created.append(disc)

    await db.flush()

    # Audit log
    await write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        entity_type="inward_session",
        entity_id=session.id,
        entity_label=transfer.to_number,
        action="session_completed",
        new_values={
            "total_items": len(session.items),
            "discrepancies_created": len(discrepancies_created),
            "transfer_order": transfer.to_number,
        },
    )

    # Notify depot staff about new discrepancies
    if discrepancies_created:
        await notify_role(
            db,
            tenant_id=tenant_id,
            role="depot_staff",
            depot_id=transfer.depot_id,
            type=NotifType.DISCREPANCY_CREATED,
            title=f"New discrepancies: {transfer.to_number}",
            message=(
                f"{len(discrepancies_created)} discrepancy(ies) raised after "
                f"inward verification of {transfer.to_number}. Please review."
            ),
            payload={"transfer_order_id": str(transfer.id)},
        )
        # Notify admins
        await notify_role(
            db,
            tenant_id=tenant_id,
            role="admin",
            type=NotifType.DISCREPANCY_CREATED,
            title=f"{len(discrepancies_created)} new discrepancies — {transfer.to_number}",
            message=f"Inward session completed for {transfer.to_number}.",
            payload={"transfer_order_id": str(transfer.id)},
        )

    return session, discrepancies_created


async def get_session_with_items(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> InwardSession:
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
        .where(InwardSession.id == session_id, InwardSession.tenant_id == tenant_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("InwardSession", str(session_id))
    return session


async def _get_session_or_404(db: AsyncSession, session_id: uuid.UUID) -> InwardSession:
    result = await db.execute(
        select(InwardSession).where(InwardSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("InwardSession", str(session_id))
    return session
