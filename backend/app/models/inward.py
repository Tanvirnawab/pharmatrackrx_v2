import uuid
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import (
    String, ForeignKey, Index, Numeric, DateTime,
    Text, Integer, Date, UniqueConstraint, Uuid
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin, TimestampMixin


class InwardSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "inward_sessions"
    __table_args__ = (
        Index("ix_inward_sessions_transfer_order_id", "transfer_order_id", unique=True),
        Index("ix_inward_sessions_store_id", "store_id"),
        Index("ix_inward_sessions_status", "status"),
        Index("ix_inward_sessions_tenant_id", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    transfer_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("transfer_orders.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    transfer_order: Mapped["TransferOrder"] = relationship(
        "TransferOrder", back_populates="inward_session"
    )
    store: Mapped["Store"] = relationship("Store", back_populates="inward_sessions")
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])
    completer: Mapped["User | None"] = relationship("User", foreign_keys=[completed_by])
    items: Mapped[list["InwardItem"]] = relationship(
        "InwardItem", back_populates="session",
        cascade="all, delete-orphan", order_by="InwardItem.line_number",
    )
    participants: Mapped[list["InwardSessionParticipant"]] = relationship(
        "InwardSessionParticipant", back_populates="session", cascade="all, delete-orphan"
    )

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def verified_items(self) -> int:
        return sum(1 for i in self.items if i.received_qty is not None)

    @property
    def completion_pct(self) -> float:
        if not self.items:
            return 0.0
        return round(self.verified_items / len(self.items) * 100, 1)


class InwardSessionParticipant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "inward_session_participants"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_session_participant"),
        Index("ix_isp_session_id", "session_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inward_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["InwardSession"] = relationship("InwardSession", back_populates="participants")
    user: Mapped["User"] = relationship("User")


class InwardItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "inward_items"
    __table_args__ = (
        Index("ix_inward_items_session_id", "session_id"),
        Index("ix_inward_items_transfer_item_id", "transfer_item_id", unique=True),
        Index("ix_inward_items_variance_type", "variance_type"),
        Index("ix_inward_items_scan_result", "scan_result"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inward_sessions.id", ondelete="CASCADE"), nullable=False
    )
    transfer_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("transfer_order_items.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)
    expected_qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Filled during verification
    received_qty: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Variance (calculated on save)
    variance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    variance_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Who verified
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── V2 fields ─────────────────────────────────────────────────────────────
    barcode_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    barcode_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 'match' | 'mismatch' | 'unknown' | None = not scanned
    scan_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ocr_suggested_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    ocr_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    session: Mapped["InwardSession"] = relationship("InwardSession", back_populates="items")
    transfer_item: Mapped["TransferOrderItem"] = relationship(
        "TransferOrderItem", back_populates="inward_item"
    )
    verifier: Mapped["User | None"] = relationship("User", foreign_keys=[verified_by])
    discrepancy: Mapped["Discrepancy | None"] = relationship(
        "Discrepancy", back_populates="inward_item", uselist=False
    )
    batch_records: Mapped[list["BatchRecord"]] = relationship(
        "BatchRecord", back_populates="inward_item", cascade="all, delete-orphan"
    )

    def calculate_variance(self) -> None:
        if self.received_qty is not None:
            self.variance = self.received_qty - self.expected_qty
            if self.variance == 0:
                self.variance_type = "match"
            elif self.variance < 0:
                self.variance_type = "shortage"
            else:
                self.variance_type = "excess"
        else:
            self.variance = None
            self.variance_type = None
