"""Notifications endpoints."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.audit_notif import Notification
from app.models.user import User
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Notification).where(
        Notification.recipient_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(50)

    if unread_only:
        q = q.where(Notification.read_at.is_(None))

    result = await db.execute(q)
    return [NotificationOut.model_validate(n) for n in result.scalars().all()]


@router.post("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == current_user.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    return {"message": "All notifications marked as read"}


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.recipient_id == current_user.id,
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    return {"message": "Notification marked as read"}
