import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import String, ForeignKey, Index, Numeric, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID
from app.db.base import Base, UUIDMixin, TimestampMixin


class DiscrepancyStatus:
    OPEN = "open"                      # Auto-created, awaiting depot review
    DEPOT_RESPONDED = "depot_responded"  # Depot has provided their explanation
    ADMIN_RESOLVED = "admin_resolved"  # Admin marked as resolved
    CLOSED = "closed"                  # Fully closed
    REJECTED = "rejected"              # Admin rejected the discrepancy claim


class DiscrepancyType:
    SHORTAGE = "shortage"
    EXCESS = "excess"
    WRONG_MEDICINE = "wrong_medicine"  # Can be raised manually by manager


class Discrepancy(Base, UUIDMixin, TimestampMixin):
    """
    Auto-created for each InwardItem with variance != 0.
    Follows a two-step resolution: Depot responds → Admin resolves.
    """
    __tablename__ = "discrepancies"
    __table_args__ = (
        Index("ix_disc_tenant_id", "tenant_id"),
        Index("ix_disc_inward_item_id", "inward_item_id", unique=True),
        Index("ix_disc_transfer_order_id", "transfer_order_id"),
        Index("ix_disc_depot_id", "depot_id"),
        Index("ix_disc_status", "status"),
        Index("ix_disc_type", "type"),
        Index("ix_disc_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    # Source references
    inward_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inward_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Denormalized for fast filtering without deep joins
    transfer_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfer_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    depot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("depots.id", ondelete="RESTRICT"), nullable=False
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )

    raised_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # shortage | excess | wrong_medicine
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # open | depot_responded | admin_resolved | closed | rejected
    status: Mapped[str] = mapped_column(String(30), default=DiscrepancyStatus.OPEN, nullable=False)

    # Expected qty, received qty, and computed variance (denormalized)
    expected_qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    variance_qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Medicine name (denormalized)
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Depot's explanation
    depot_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    depot_responded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    depot_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Admin resolution
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    inward_item: Mapped["InwardItem"] = relationship("InwardItem", back_populates="discrepancy")
    transfer_order: Mapped["TransferOrder"] = relationship("TransferOrder")
    depot: Mapped["Depot"] = relationship("Depot")
    store: Mapped["Store"] = relationship("Store")
    raiser: Mapped["User | None"] = relationship("User", foreign_keys=[raised_by])
    depot_responder: Mapped["User | None"] = relationship(
        "User", foreign_keys=[depot_responded_by]
    )
    resolver: Mapped["User | None"] = relationship("User", foreign_keys=[resolved_by])
    comments: Mapped[list["DiscrepancyComment"]] = relationship(
        "DiscrepancyComment",
        back_populates="discrepancy",
        cascade="all, delete-orphan",
        order_by="DiscrepancyComment.created_at",
    )
    attachments: Mapped[list["DiscrepancyAttachment"]] = relationship(
        "DiscrepancyAttachment", back_populates="discrepancy", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Discrepancy {self.type} {self.variance_qty:+} ({self.status})>"


class DiscrepancyComment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "discrepancy_comments"
    __table_args__ = (Index("ix_dc_discrepancy_id", "discrepancy_id"),)

    discrepancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discrepancies.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    discrepancy: Mapped["Discrepancy"] = relationship("Discrepancy", back_populates="comments")
    author: Mapped["User | None"] = relationship("User")


class DiscrepancyAttachment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "discrepancy_attachments"
    __table_args__ = (Index("ix_da_discrepancy_id", "discrepancy_id"),)

    discrepancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discrepancies.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("file_uploads.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    discrepancy: Mapped["Discrepancy"] = relationship("Discrepancy", back_populates="attachments")
    file: Mapped["FileUpload"] = relationship("FileUpload")
    uploader: Mapped["User | None"] = relationship("User")
