"""
Scanning API — barcode validation and OCR-assisted expiry capture.
All scan/OCR features are additive and fail gracefully.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError, BusinessRuleError
from app.models.inward import InwardItem, InwardSession
from app.models.batch_barcode import BatchRecord
from app.models.user import User
from app.services.barcode_service import parse_barcode, match_scan_to_item
from app.services.ocr_service import extract_expiry_from_image

router = APIRouter(prefix="/scanning", tags=["scanning"])


# ── Request / Response schemas ────────────────────────────────────────────────

class ScanRequest(BaseModel):
    raw_barcode: str

class ScanResponse(BaseModel):
    result: str          # 'match' | 'mismatch' | 'unknown'
    barcode_type: str
    is_gs1: bool
    gtin: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None
    confidence: float
    notes: str

class OCRRequest(BaseModel):
    image_b64: str       # base64-encoded JPEG or PNG

class OCRResponse(BaseModel):
    available: bool
    candidates: list[str]
    best_date: Optional[str] = None
    confidence: float
    raw_text: str
    message: str

class BatchRecordIn(BaseModel):
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None   # ISO date string YYYY-MM-DD
    quantity: Optional[float] = None
    barcode_value: Optional[str] = None
    source: str = "manual"
    notes: Optional[str] = None

class BatchRecordOut(BaseModel):
    id: str
    batch_number: Optional[str]
    expiry_date: Optional[str]
    quantity: Optional[float]
    source: str
    barcode_value: Optional[str]
    notes: Optional[str]
    created_at: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/inward/{session_id}/items/{item_id}/scan", response_model=ScanResponse)
async def scan_item(
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Record a barcode scan for one inward item.
    Parses GS1 data when available, stores result, returns match outcome.
    Scanning is optional — the inward workflow proceeds regardless of result.
    """
    match = await match_scan_to_item(
        db, session_id=session_id, item_id=item_id, raw_barcode=body.raw_barcode
    )
    parsed = match.scan

    # Persist scan data onto the inward item
    res = await db.execute(
        select(InwardItem).where(InwardItem.id == item_id, InwardItem.session_id == session_id)
    )
    item = res.scalar_one_or_none()
    if not item:
        raise NotFoundError("InwardItem", str(item_id))

    item.barcode_value = parsed.raw
    item.barcode_type = parsed.barcode_type
    item.scan_result = match.result
    if parsed.batch_number and not item.batch_number:
        item.batch_number = parsed.batch_number
    if parsed.expiry_date and not item.ocr_suggested_expiry:
        item.ocr_suggested_expiry = parsed.expiry_date

    return ScanResponse(
        result=match.result,
        barcode_type=parsed.barcode_type,
        is_gs1=parsed.is_gs1,
        gtin=parsed.gtin,
        batch_number=parsed.batch_number,
        expiry_date=str(parsed.expiry_date) if parsed.expiry_date else None,
        confidence=match.confidence,
        notes=match.notes,
    )


@router.post("/ocr/extract-expiry", response_model=OCRResponse)
async def ocr_extract_expiry(
    body: OCRRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Upload a base64 image of a medicine label/carton.
    Returns OCR-extracted expiry date suggestions.
    The user MUST confirm before any date is saved.
    """
    result = extract_expiry_from_image(body.image_b64)
    return OCRResponse(
        available=result.available,
        candidates=result.candidates,
        best_date=str(result.best_date) if result.best_date else None,
        confidence=result.confidence,
        raw_text=result.raw_text,
        message=result.message,
    )


@router.post("/inward/{session_id}/items/{item_id}/batches", response_model=BatchRecordOut)
async def add_batch_record(
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    body: BatchRecordIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a batch record to an inward item. One item may have multiple batches."""
    res = await db.execute(
        select(InwardItem).where(InwardItem.id == item_id, InwardItem.session_id == session_id)
    )
    item = res.scalar_one_or_none()
    if not item:
        raise NotFoundError("InwardItem", str(item_id))

    from datetime import date as _date
    expiry = None
    if body.expiry_date:
        try:
            expiry = _date.fromisoformat(body.expiry_date)
        except ValueError:
            pass

    batch = BatchRecord(
        tenant_id=item.session.tenant_id if hasattr(item, "session") else current_user.tenant_id,
        inward_item_id=item.id,
        batch_number=body.batch_number,
        expiry_date=expiry,
        quantity=body.quantity,
        barcode_value=body.barcode_value,
        source=body.source,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(batch)
    await db.flush()

    # Also update the item's primary batch_number and expiry_date if not yet set
    if body.batch_number and not item.batch_number:
        item.batch_number = body.batch_number
    if expiry and not item.expiry_date:
        item.expiry_date = expiry

    return BatchRecordOut(
        id=str(batch.id),
        batch_number=batch.batch_number,
        expiry_date=str(batch.expiry_date) if batch.expiry_date else None,
        quantity=float(batch.quantity) if batch.quantity else None,
        source=batch.source,
        barcode_value=batch.barcode_value,
        notes=batch.notes,
        created_at=batch.created_at.isoformat(),
    )


@router.get("/inward/{session_id}/items/{item_id}/batches", response_model=list[BatchRecordOut])
async def list_batch_records(
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all batch records for an inward item."""
    from sqlalchemy.orm import selectinload
    res = await db.execute(
        select(BatchRecord)
        .where(BatchRecord.inward_item_id == item_id)
        .order_by(BatchRecord.created_at)
    )
    records = res.scalars().all()
    return [
        BatchRecordOut(
            id=str(r.id),
            batch_number=r.batch_number,
            expiry_date=str(r.expiry_date) if r.expiry_date else None,
            quantity=float(r.quantity) if r.quantity else None,
            source=r.source,
            barcode_value=r.barcode_value,
            notes=r.notes,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]
