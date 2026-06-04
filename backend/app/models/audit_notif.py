import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Index, DateTime, Text, JSON, BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID
from app.db.base import Base, UUIDMixin


class AuditLog(Base, UUIDMixin):
    """
    Append-only audit trail. Never updated or deleted.
    Records every significant state change in the system.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_tenant_id", "tenant_id"),
        Index("ix_audit_actor_id", "actor_id"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True  # NULL = system action
    )
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Entity being changed
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Action performed
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # Snapshot before and after
    old_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=__import__('sqlalchemy').func.now(),
    )


class Notification(Base, UUIDMixin):
    """In-app notifications. Extensible for email/SMS/WhatsApp later."""
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notif_recipient_id", "recipient_id"),
        Index("ix_notif_read_at", "read_at"),
        Index("ix_notif_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Type: discrepancy_created | discrepancy_updated | inward_completed | depot_response_needed
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Navigation payload: {"entity_type": "discrepancy", "entity_id": "..."}
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=__import__('sqlalchemy').func.now(),
    )

    recipient: Mapped["User"] = relationship("User")


class FileUpload(Base, UUIDMixin):
    """Tracks every uploaded file. Actual bytes stored in S3/MinIO."""
    __tablename__ = "file_uploads"
    __table_args__ = (Index("ix_file_uploads_tenant_id", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(1024), nullable=False)  # S3 object key
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=__import__('sqlalchemy').func.now(),
    )

    uploader: Mapped["User | None"] = relationship("User")
