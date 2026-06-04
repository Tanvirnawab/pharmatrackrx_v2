import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, ForeignKey, Index, Numeric, Date, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID
from app.db.base import Base, UUIDMixin, TimestampMixin


class OcrJobStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVED = "approved"
    REJECTED = "rejected"


class OcrMatchStatus:
    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class OcrJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ocr_jobs"
    __table_args__ = (
        Index("ix_ocr_jobs_tenant_id", "tenant_id"),
        Index("ix_ocr_jobs_status", "status"),
        Index("ix_ocr_jobs_transfer_order_id", "transfer_order_id"),
        Index("ix_ocr_jobs_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    file_upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("file_uploads.id", ondelete="RESTRICT"), nullable=False
    )
    transfer_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transfer_orders.id", ondelete="SET NULL"), nullable=True
    )

    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=OcrJobStatus.QUEUED, nullable=False)
    engine: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    file_upload: Mapped["FileUpload"] = relationship("FileUpload")
    transfer_order: Mapped["TransferOrder | None"] = relationship("TransferOrder")
    results: Mapped[list["OcrResult"]] = relationship(
        "OcrResult", back_populates="job", cascade="all, delete-orphan", order_by="OcrResult.line_number"
    )
    match_results: Mapped[list["OcrMatchResult"]] = relationship(
        "OcrMatchResult", back_populates="job", cascade="all, delete-orphan"
    )


class OcrResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ocr_results"
    __table_args__ = (
        Index("ix_ocr_results_job_id", "job_id"),
        Index("ix_ocr_results_item_name", "medicine_name"),
        Index("ix_ocr_results_batch_number", "batch_number"),
        Index("ix_ocr_results_expiry_date", "expiry_date"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ocr_jobs.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(default=1, nullable=False)
    medicine_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pack_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    corrected_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    job: Mapped["OcrJob"] = relationship("OcrJob", back_populates="results")
    match_results: Mapped[list["OcrMatchResult"]] = relationship(
        "OcrMatchResult", back_populates="ocr_result", cascade="all, delete-orphan"
    )


class OcrMatchResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ocr_match_results"
    __table_args__ = (
        Index("ix_ocr_match_results_job_id", "job_id"),
        Index("ix_ocr_match_results_ocr_result_id", "ocr_result_id"),
        Index("ix_ocr_match_results_transfer_item_id", "transfer_item_id"),
        Index("ix_ocr_match_results_status", "match_status"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ocr_jobs.id", ondelete="CASCADE"), nullable=False
    )
    ocr_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ocr_results.id", ondelete="CASCADE"), nullable=False
    )
    transfer_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transfer_order_items.id", ondelete="SET NULL"), nullable=True
    )
    match_status: Mapped[str] = mapped_column(String(30), default=OcrMatchStatus.UNKNOWN, nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    mismatch_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["OcrJob"] = relationship("OcrJob", back_populates="match_results")
    ocr_result: Mapped["OcrResult"] = relationship("OcrResult", back_populates="match_results")
    transfer_item: Mapped["TransferOrderItem | None"] = relationship("TransferOrderItem")
