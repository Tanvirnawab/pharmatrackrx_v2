"""
All application Pydantic schemas in one file for clarity.
Split into per-domain sections.
"""
import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, field_validator, model_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Users ─────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    store_id: Optional[uuid.UUID] = None
    depot_id: Optional[uuid.UUID] = None
    is_active: bool

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "store_staff"
    store_id: Optional[uuid.UUID] = None
    depot_id: Optional[uuid.UUID] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        allowed = {"admin", "store_manager", "store_staff", "depot_staff"}
        if v not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(allowed)}")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    store_id: Optional[uuid.UUID] = None
    depot_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


# ── Depots & Stores ───────────────────────────────────────────────────────────

class DepotOut(BaseModel):
    id: uuid.UUID
    name: str
    code: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


class StoreOut(BaseModel):
    id: uuid.UUID
    name: str
    code: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


# ── Transfer Orders ───────────────────────────────────────────────────────────

class TransferOrderItemOut(BaseModel):
    id: uuid.UUID
    line_number: int
    item_name: str
    expected_qty: Decimal
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    depot_stock: Optional[Decimal] = None
    model_config = {"from_attributes": True}


class TransferOrderOut(BaseModel):
    id: uuid.UUID
    to_number: str
    transfer_date: date
    status: str
    total_items: int
    total_expected_qty: Decimal
    depot: DepotOut
    store: StoreOut
    imported_at: Optional[datetime] = None
    import_filename: Optional[str] = None
    model_config = {"from_attributes": True}


class TransferOrderDetail(TransferOrderOut):
    items: list[TransferOrderItemOut] = []


class ImportResult(BaseModel):
    transfers_created: int
    transfers_skipped: int
    items_created: int
    transfer_numbers: list[str]
    errors: list[str] = []
    message: str


# ── Inward Sessions ───────────────────────────────────────────────────────────

class InwardItemOut(BaseModel):
    id: uuid.UUID
    line_number: int
    item_name: str
    expected_qty: Decimal
    received_qty: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    variance: Optional[Decimal] = None
    variance_type: Optional[str] = None
    notes: Optional[str] = None
    verified_by_name: Optional[str] = None
    verified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_verifier(cls, item) -> "InwardItemOut":
        data = cls.model_validate(item)
        if item.verifier:
            data.verified_by_name = item.verifier.full_name
        return data


class ParticipantOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    last_active_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class InwardSessionOut(BaseModel):
    id: uuid.UUID
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    total_items: int = 0
    verified_items: int = 0
    completion_pct: float = 0.0
    shortage_count: int = 0
    excess_count: int = 0
    transfer_order: Optional[TransferOrderOut] = None
    participants: list[ParticipantOut] = []

    model_config = {"from_attributes": True}


class InwardSessionDetail(InwardSessionOut):
    items: list[InwardItemOut] = []


class StartInwardRequest(BaseModel):
    pass  # No body needed — transfer_order_id comes from the path


class UpdateInwardItemRequest(BaseModel):
    received_qty: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("received_qty")
    @classmethod
    def qty_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("received_qty cannot be negative")
        return v


class CompleteInwardRequest(BaseModel):
    notes: Optional[str] = None


class BatchUpdateItem(BaseModel):
    item_id: uuid.UUID
    received_qty: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None


class BatchUpdateRequest(BaseModel):
    """Update multiple inward items in a single request — for faster data entry."""
    updates: list[BatchUpdateItem]


# ── Discrepancies ─────────────────────────────────────────────────────────────

class DiscrepancyCommentOut(BaseModel):
    id: uuid.UUID
    body: str
    author_name: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class DiscrepancyAttachmentOut(BaseModel):
    id: uuid.UUID
    label: Optional[str] = None
    filename: str
    mime_type: str
    size_bytes: int
    url: Optional[str] = None
    model_config = {"from_attributes": True}


class DiscrepancyOut(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    item_name: str
    expected_qty: Decimal
    received_qty: Decimal
    variance_qty: Decimal
    notes: Optional[str] = None
    depot: DepotOut
    store: StoreOut
    to_number: Optional[str] = None
    raised_by_name: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class DiscrepancyDetail(DiscrepancyOut):
    depot_response: Optional[str] = None
    depot_responded_at: Optional[datetime] = None
    depot_responded_by_name: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_by_name: Optional[str] = None
    comments: list[DiscrepancyCommentOut] = []
    attachments: list[DiscrepancyAttachmentOut] = []


class DepotResponseRequest(BaseModel):
    response: str


class ResolveDiscrepancyRequest(BaseModel):
    new_status: str
    resolution_notes: Optional[str] = None

    @field_validator("new_status")
    @classmethod
    def validate_status(cls, v):
        allowed = {"admin_resolved", "rejected", "closed", "open"}
        if v not in allowed:
            raise ValueError(f"new_status must be one of: {', '.join(allowed)}")
        return v


class AddCommentRequest(BaseModel):
    body: str


# ── Reports ───────────────────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    pending_inwards: int
    in_progress_inwards: int
    open_discrepancies: int
    depot_pending_response: int
    resolved_this_week: int
    transfer_accuracy_30d: float


class DiscrepancyTrendPoint(BaseModel):
    day: str
    type: str
    count: int
    total_variance: float


class TopDiscrepancyItem(BaseModel):
    item_name: str
    discrepancy_count: int
    shortages: int
    excesses: int
    total_variance_qty: float
    avg_variance_qty: float


class DepotPerformance(BaseModel):
    depot_id: str
    depot_name: str
    total_transfers: int
    total_items: int
    matched_items: int
    shortage_items: int
    excess_items: int
    accuracy_pct: float


# ── Notifications ─────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    message: str
    payload: Optional[dict[str, Any]] = None
    read_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


# OCR document receiving

class OcrJobOut(BaseModel):
    id: uuid.UUID
    status: str
    document_type: Optional[str] = None
    transfer_order_id: Optional[uuid.UUID] = None
    file_upload_id: uuid.UUID
    engine: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    error_message: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class OcrResultOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    line_number: int
    medicine_name: Optional[str] = None
    sku: Optional[str] = None
    pack_size: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    quantity: Optional[Decimal] = None
    raw_text: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    corrected_data: Optional[dict[str, Any]] = None
    model_config = {"from_attributes": True}


class OcrMatchResultOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    ocr_result_id: uuid.UUID
    transfer_item_id: Optional[uuid.UUID] = None
    match_status: str
    confidence_score: Optional[Decimal] = None
    mismatch_fields: Optional[dict[str, Any]] = None
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


class OcrJobDetail(OcrJobOut):
    results: list[OcrResultOut] = []
    match_results: list[OcrMatchResultOut] = []


class OcrReviewUpdate(BaseModel):
    result_id: uuid.UUID
    medicine_name: Optional[str] = None
    sku: Optional[str] = None
    pack_size: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    quantity: Optional[Decimal] = None


class OcrApproveRequest(BaseModel):
    notes: Optional[str] = None
    corrections: list[OcrReviewUpdate] = []


class OcrRejectRequest(BaseModel):
    reason: str
