"""
Discrepancy resolution workflow:
  open → depot_responded → admin_resolved → closed
  open → rejected (admin can reject without depot response)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.discrepancy import (
    Discrepancy, DiscrepancyComment, DiscrepancyAttachment,
    DiscrepancyStatus, DiscrepancyType
)
from app.models.audit_notif import FileUpload
from app.models.user import User
from app.core.exceptions import NotFoundError, ForbiddenError, BusinessRuleError
from app.services.audit_service import write_audit_log
from app.services.notification_service import notify, NotifType


# Valid status transitions
VALID_TRANSITIONS: dict[str, list[str]] = {
    DiscrepancyStatus.OPEN: [
        DiscrepancyStatus.DEPOT_RESPONDED,
        DiscrepancyStatus.REJECTED,
        DiscrepancyStatus.ADMIN_RESOLVED,
    ],
    DiscrepancyStatus.DEPOT_RESPONDED: [
        DiscrepancyStatus.ADMIN_RESOLVED,
        DiscrepancyStatus.REJECTED,
        DiscrepancyStatus.OPEN,  # re-open if depot response was insufficient
    ],
    DiscrepancyStatus.ADMIN_RESOLVED: [DiscrepancyStatus.CLOSED],
    DiscrepancyStatus.CLOSED: [],
    DiscrepancyStatus.REJECTED: [],
}


async def get_discrepancy(
    db: AsyncSession,
    *,
    discrepancy_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Discrepancy:
    result = await db.execute(
        select(Discrepancy)
        .options(
            selectinload(Discrepancy.comments).selectinload(DiscrepancyComment.author),
            selectinload(Discrepancy.attachments).selectinload(DiscrepancyAttachment.file),
            selectinload(Discrepancy.raiser),
            selectinload(Discrepancy.depot_responder),
            selectinload(Discrepancy.resolver),
            selectinload(Discrepancy.depot),
            selectinload(Discrepancy.store),
            selectinload(Discrepancy.transfer_order),
        )
        .where(
            Discrepancy.id == discrepancy_id,
            Discrepancy.tenant_id == tenant_id,
        )
    )
    disc = result.scalar_one_or_none()
    if not disc:
        raise NotFoundError("Discrepancy", str(discrepancy_id))
    return disc


async def add_depot_response(
    db: AsyncSession,
    *,
    discrepancy_id: uuid.UUID,
    tenant_id: uuid.UUID,
    response_text: str,
    current_user: User,
) -> Discrepancy:
    """Depot staff adds their explanation/response."""
    disc = await get_discrepancy(db, discrepancy_id=discrepancy_id, tenant_id=tenant_id)

    if current_user.role not in ("admin", "depot_staff"):
        raise ForbiddenError("Only depot staff or admins can add a depot response.")

    if current_user.role == "depot_staff" and current_user.depot_id != disc.depot_id:
        raise ForbiddenError("You can only respond to discrepancies from your assigned depot.")

    if disc.status not in (DiscrepancyStatus.OPEN, DiscrepancyStatus.DEPOT_RESPONDED):
        raise BusinessRuleError(
            f"Cannot add depot response to a discrepancy with status '{disc.status}'."
        )

    old_status = disc.status
    disc.depot_response = response_text
    disc.depot_responded_by = current_user.id
    disc.depot_responded_at = datetime.now(timezone.utc)
    disc.status = DiscrepancyStatus.DEPOT_RESPONDED

    # Auto-add a system comment
    comment = DiscrepancyComment(
        discrepancy_id=disc.id,
        author_id=current_user.id,
        body=f"**Depot response:** {response_text}",
    )
    db.add(comment)

    await write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        entity_type="discrepancy",
        entity_id=disc.id,
        entity_label=disc.item_name,
        action="depot_responded",
        old_values={"status": old_status},
        new_values={"status": disc.status, "depot_response": response_text},
    )

    # Notify admin
    await notify(
        db,
        tenant_id=tenant_id,
        recipient_id=disc.raised_by,
        type=NotifType.DEPOT_RESPONSE_ADDED,
        title=f"Depot responded: {disc.item_name[:50]}",
        message=f"Depot has responded to the discrepancy for '{disc.item_name}'.",
        payload={"discrepancy_id": str(disc.id)},
    )

    return disc


async def resolve_discrepancy(
    db: AsyncSession,
    *,
    discrepancy_id: uuid.UUID,
    tenant_id: uuid.UUID,
    new_status: str,
    resolution_notes: Optional[str],
    current_user: User,
) -> Discrepancy:
    """Admin marks discrepancy as resolved, rejected, or closed."""
    if current_user.role != "admin":
        raise ForbiddenError("Only admins can resolve discrepancies.")

    disc = await get_discrepancy(db, discrepancy_id=discrepancy_id, tenant_id=tenant_id)

    allowed = VALID_TRANSITIONS.get(disc.status, [])
    if new_status not in allowed:
        raise BusinessRuleError(
            f"Cannot transition from '{disc.status}' to '{new_status}'. "
            f"Allowed: {allowed}"
        )

    old_status = disc.status
    disc.status = new_status
    disc.resolution_notes = resolution_notes
    disc.resolved_by = current_user.id
    disc.resolved_at = datetime.now(timezone.utc)

    if new_status == DiscrepancyStatus.CLOSED:
        # Add a system comment
        comment = DiscrepancyComment(
            discrepancy_id=disc.id,
            author_id=current_user.id,
            body=f"**Discrepancy closed.** {resolution_notes or ''}".strip(),
        )
        db.add(comment)

    await write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        entity_type="discrepancy",
        entity_id=disc.id,
        entity_label=disc.item_name,
        action=f"status_changed_to_{new_status}",
        old_values={"status": old_status},
        new_values={"status": new_status, "resolution_notes": resolution_notes},
    )

    # Notify the store staff who raised it
    if disc.raised_by:
        await notify(
            db,
            tenant_id=tenant_id,
            recipient_id=disc.raised_by,
            type=NotifType.DISCREPANCY_RESOLVED,
            title=f"Discrepancy {new_status}: {disc.item_name[:50]}",
            message=f"Admin has marked the discrepancy as '{new_status}'.",
            payload={"discrepancy_id": str(disc.id)},
        )

    return disc


async def add_comment(
    db: AsyncSession,
    *,
    discrepancy_id: uuid.UUID,
    tenant_id: uuid.UUID,
    body: str,
    current_user: User,
) -> DiscrepancyComment:
    # Verify discrepancy exists and belongs to tenant
    result = await db.execute(
        select(Discrepancy).where(
            Discrepancy.id == discrepancy_id,
            Discrepancy.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("Discrepancy", str(discrepancy_id))

    comment = DiscrepancyComment(
        discrepancy_id=discrepancy_id,
        author_id=current_user.id,
        body=body,
    )
    db.add(comment)
    return comment


async def attach_file(
    db: AsyncSession,
    *,
    discrepancy_id: uuid.UUID,
    tenant_id: uuid.UUID,
    file_upload_id: uuid.UUID,
    label: Optional[str],
    current_user: User,
) -> DiscrepancyAttachment:
    result = await db.execute(
        select(Discrepancy).where(
            Discrepancy.id == discrepancy_id,
            Discrepancy.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("Discrepancy", str(discrepancy_id))

    attachment = DiscrepancyAttachment(
        discrepancy_id=discrepancy_id,
        file_upload_id=file_upload_id,
        label=label,
        uploaded_by=current_user.id,
    )
    db.add(attachment)
    return attachment
