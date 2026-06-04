import uuid
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_notif import AuditLog


async def write_audit_log(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: Optional[uuid.UUID],
    actor_name: Optional[str],
    actor_role: Optional[str],
    entity_type: str,
    entity_id: uuid.UUID,
    entity_label: Optional[str] = None,
    action: str,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        action=action,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    # Note: caller must commit the session
    return entry
