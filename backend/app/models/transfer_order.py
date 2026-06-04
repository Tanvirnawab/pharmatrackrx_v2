import uuid
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import (
    String, Boolean, ForeignKey, Index, Numeric, Integer,
    Date, DateTime, Text, Enum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID
from app.db.base import Base, UUIDMixin, TimestampMixin
import enum


class TransferOrderStatus(str, enum.Enum):
    PENDING = "pending"          # Imported, not started
    IN_PROGRESS = "in_progress"  # Inward session active
    COMPLETED = "completed"      # Inward session completed
    CANCELLED = "cancelled"      # Cancelled by admin


class TransferOrder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "transfer_orders"
    __table_args__ = (
        Index("ix_to_tenant_id", "tenant_id"),
        Index("ix_to_store_id", "store_id"),
        Index("ix_to_depot_id", "depot_id"),
        Index("ix_to_status", "status"),
        Index("ix_to_number", "to_number"),
        Index("ix_to_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    depot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("depots.id", ondelete="RESTRICT"), nullable=False
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )

    # AExpert transfer number, e.g. "26MATD/STR/000247"
    to_number: Mapped[str] = mapped_column(String(100), nullable=False)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=TransferOrderStatus.PENDING.value, nullable=False
    )

    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_expected_qty: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, nullable=False
    )

    # Import tracking
    imported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    import_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="transfer_orders")
    depot: Mapped["Depot"] = relationship("Depot", back_populates="transfer_orders")
    store: Mapped["Store"] = relationship("Store", back_populates="transfer_orders")
    importer: Mapped["User | None"] = relationship("User", foreign_keys=[imported_by])
    items: Mapped[list["TransferOrderItem"]] = relationship(
        "TransferOrderItem",
        back_populates="transfer_order",
        cascade="all, delete-orphan",
        order_by="TransferOrderItem.line_number",
    )
    inward_session: Mapped["InwardSession | None"] = relationship(
        "InwardSession", back_populates="transfer_order", uselist=False
    )

    def __repr__(self):
        return f"<TransferOrder {self.to_number}>"


class TransferOrderItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "transfer_order_items"
    __table_args__ = (
        Index("ix_toi_transfer_order_id", "transfer_order_id"),
        Index("ix_toi_item_name", "item_name"),
    )

    transfer_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfer_orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Positional line number (1-based, preserves Excel row order)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Medicine name exactly as supplied by AExpert
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Quantity exactly as supplied by AExpert — no conversion in V1
    expected_qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Unit field (for data model completeness; no conversion logic in V1)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Price from AExpert SBM column
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    # Current depot stock from AExpert (informational)
    depot_stock: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Relationships
    transfer_order: Mapped["TransferOrder"] = relationship(
        "TransferOrder", back_populates="items"
    )
    inward_item: Mapped["InwardItem | None"] = relationship(
        "InwardItem", back_populates="transfer_item", uselist=False
    )

    def __repr__(self):
        return f"<TransferOrderItem {self.item_name} x{self.expected_qty}>"
