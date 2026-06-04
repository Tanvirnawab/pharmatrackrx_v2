import uuid
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import String, ForeignKey, Index, Numeric, DateTime, Text, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid
from app.db.base import Base, UUIDMixin, TimestampMixin


class BatchRecord(Base, UUIDMixin, TimestampMixin):
    """
    Optional batch-level detail attached to an InwardItem.
    A single medicine line may physically arrive in multiple batches;
    this table stores each one. V2 feature — always optional.
    """
    __tablename__ = "batch_records"
    __table_args__ = (
        Index("ix_batch_records_inward_item_id", "inward_item_id"),
        Index("ix_batch_records_tenant_id", "tenant_id"),
        Index("ix_batch_records_batch_number", "batch_number"),
        Index("ix_batch_records_expiry_date", "expiry_date"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    inward_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inward_items.id", ondelete="CASCADE"), nullable=False
    )

    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    barcode_value: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 'scan' | 'manual' | 'ocr' | 'import'
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    inward_item: Mapped["InwardItem"] = relationship("InwardItem", back_populates="batch_records")
    creator: Mapped["User | None"] = relationship("User")

    def __repr__(self):
        return f"<BatchRecord {self.batch_number} exp={self.expiry_date}>"
