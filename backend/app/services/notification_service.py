import uuid
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.audit_notif import Notification
from app.models.user import User


async def notify(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    recipient_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    payload: Optional[dict[str, Any]] = None,
) -> Notification:
    notif = Notification(
        tenant_id=tenant_id,
        recipient_id=recipient_id,
        type=type,
        title=title,
        message=message,
        payload=payload,
    )
    db.add(notif)
    return notif


async def notify_role(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    role: str,
    store_id: Optional[uuid.UUID] = None,
    depot_id: Optional[uuid.UUID] = None,
    type: str,
    title: str,
    message: str,
    payload: Optional[dict[str, Any]] = None,
) -> list[Notification]:
    """Send notification to all active users with the given role (+ optional scope filter)."""
    query = select(User).where(
        User.tenant_id == tenant_id,
        User.role == role,
        User.is_active == True,
    )
    if store_id:
        query = query.where(User.store_id == store_id)
    if depot_id:
        query = query.where(User.depot_id == depot_id)

    result = await db.execute(query)
    users = result.scalars().all()

    notifications = []
    for user in users:
        n = await notify(
            db,
            tenant_id=tenant_id,
            recipient_id=user.id,
            type=type,
            title=title,
            message=message,
            payload=payload,
        )
        notifications.append(n)
    return notifications


# Notification type constants — extend here when adding email/SMS/WhatsApp
class NotifType:
    DISCREPANCY_CREATED = "discrepancy_created"
    DISCREPANCY_UPDATED = "discrepancy_updated"
    DEPOT_RESPONSE_ADDED = "depot_response_added"
    DISCREPANCY_RESOLVED = "discrepancy_resolved"
    INWARD_COMPLETED = "inward_completed"
    INWARD_STARTED = "inward_started"
    TRANSFER_IMPORTED = "transfer_imported"
    OCR_COMPLETED = "ocr_completed"
    OCR_REJECTED = "ocr_rejected"
    ASSIGNMENT_CREATED = "assignment_created"
    EXPIRY_ALERT = "expiry_alert"
    DAILY_SUMMARY = "daily_summary"
