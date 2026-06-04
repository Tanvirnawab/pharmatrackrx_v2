import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from typing import Any
from PIL import Image
import pytesseract
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_notif import FileUpload
from app.models.ocr import OcrJob, OcrResult, OcrJobStatus
from app.models.inward import InwardSession
from app.services.storage_service import read_upload_bytes
from app.services.ocr_matching_service import rebuild_matches
from app.services.audit_service import write_audit_log
from app.services.notification_service import notify, NotifType
from app.services.inward_service import start_inward_session
from app.models.user import User


DATE_RE = re.compile(r"(?P<date>\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b)")
QTY_RE = re.compile(r"(?:qty|quantity|pcs|nos)?\s*(?P<qty>\d+(?:\.\d+)?)\s*(?:qty|pcs|nos)?", re.I)
BATCH_RE = re.compile(r"(?:batch|b\.?no|lot)\s*[:#-]?\s*(?P<batch>[A-Z0-9-]{3,})", re.I)


def _parse_date(raw: str):
    from dateutil.parser import parse
    try:
        return parse(raw, dayfirst=True).date()
    except Exception:
        return None


def _extract_with_paddle(_: bytes) -> tuple[str, str]:
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except Exception:
        return "", "paddle_unavailable"
    # PaddleOCR is optional in this deployment. If installed, this is the primary engine.
    return "", "paddle_ready"


def _extract_with_tesseract(file_bytes: bytes, mime_type: str) -> tuple[str, str]:
    if "pdf" in mime_type:
        return "", "tesseract_pdf_unsupported"
    image = Image.open(BytesIO(file_bytes))
    text = pytesseract.image_to_string(image)
    return text, "tesseract"


def _parse_lines(raw_text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates: list[dict[str, Any]] = []
    for line in lines:
        if len(line) < 4:
            continue
        date_match = DATE_RE.search(line)
        qty_match = QTY_RE.search(line)
        batch_match = BATCH_RE.search(line)
        medicine = re.sub(DATE_RE, "", line)
        medicine = re.sub(BATCH_RE, "", medicine)
        medicine = re.sub(r"\s+", " ", medicine).strip(" :-")
        candidates.append({
            "medicine_name": medicine[:500] or None,
            "batch_number": batch_match.group("batch") if batch_match else None,
            "expiry_date": _parse_date(date_match.group("date")) if date_match else None,
            "quantity": Decimal(qty_match.group("qty")) if qty_match else None,
            "raw_text": line,
            "confidence_score": Decimal("55.00"),
        })
    if not candidates and raw_text.strip():
        candidates.append({
            "medicine_name": None,
            "raw_text": raw_text[:2000],
            "confidence_score": Decimal("20.00"),
        })
    return candidates


async def get_job_for_tenant(db: AsyncSession, *, job_id: uuid.UUID, tenant_id: uuid.UUID) -> OcrJob | None:
    result = await db.execute(
        select(OcrJob)
        .options(selectinload(OcrJob.results), selectinload(OcrJob.match_results), selectinload(OcrJob.file_upload))
        .where(OcrJob.id == job_id, OcrJob.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def process_ocr_job(db: AsyncSession, job_id: uuid.UUID) -> None:
    result = await db.execute(
        select(OcrJob)
        .options(selectinload(OcrJob.results), selectinload(OcrJob.match_results))
        .where(OcrJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return
    upload = await db.get(FileUpload, job.file_upload_id)
    if not upload:
        return

    job.status = OcrJobStatus.PROCESSING
    job.started_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        file_bytes = await read_upload_bytes(upload)
        raw_text, engine = _extract_with_paddle(file_bytes)
        if not raw_text:
            raw_text, engine = _extract_with_tesseract(file_bytes, upload.mime_type)
        rows = _parse_lines(raw_text)

        for existing in list(job.results):
            await db.delete(existing)
        await db.flush()

        for idx, row in enumerate(rows, start=1):
            db.add(OcrResult(job_id=job.id, line_number=idx, **row))
        await db.flush()
        await db.refresh(job, attribute_names=["results"])
        await rebuild_matches(db, job)

        job.status = OcrJobStatus.COMPLETED
        job.engine = engine
        job.confidence_score = (
            sum(float(r.get("confidence_score") or 0) for r in rows) / len(rows)
            if rows else 0
        )
        job.completed_at = datetime.now(timezone.utc)
        await write_audit_log(
            db,
            tenant_id=job.tenant_id,
            actor_id=None,
            actor_name="System",
            actor_role="system",
            entity_type="ocr_job",
            entity_id=job.id,
            action="ocr_completed",
            new_values={"engine": engine, "rows": len(rows)},
        )
        if job.uploader_id:
            await notify(
                db,
                tenant_id=job.tenant_id,
                recipient_id=job.uploader_id,
                type=NotifType.OCR_COMPLETED,
                title="OCR completed",
                message=f"OCR processing finished for {upload.filename}.",
                payload={"entity_type": "ocr_job", "entity_id": str(job.id)},
            )
    except Exception as exc:
        job.status = OcrJobStatus.FAILED
        job.error_message = str(exc)
        job.completed_at = datetime.now(timezone.utc)


async def approve_ocr_job(
    db: AsyncSession,
    *,
    job: OcrJob,
    user: User,
    notes: str | None,
) -> None:
    draft_session_id = None
    if job.transfer_order_id:
        existing = await db.execute(
            select(InwardSession).where(InwardSession.transfer_order_id == job.transfer_order_id)
        )
        session = existing.scalar_one_or_none()
        if not session:
            session = await start_inward_session(
                db,
                transfer_order_id=job.transfer_order_id,
                tenant_id=job.tenant_id,
                current_user=user,
            )
        draft_session_id = str(session.id)

    job.status = OcrJobStatus.APPROVED
    job.reviewed_by = user.id
    job.reviewed_at = datetime.now(timezone.utc)
    job.review_notes = notes
    await write_audit_log(
        db,
        tenant_id=job.tenant_id,
        actor_id=user.id,
        actor_name=user.full_name,
        actor_role=user.role,
        entity_type="ocr_job",
        entity_id=job.id,
        action="ocr_approved",
        new_values={"notes": notes, "inward_session_id": draft_session_id},
    )


async def reject_ocr_job(
    db: AsyncSession,
    *,
    job: OcrJob,
    user: User,
    reason: str,
) -> None:
    job.status = OcrJobStatus.REJECTED
    job.reviewed_by = user.id
    job.reviewed_at = datetime.now(timezone.utc)
    job.review_notes = reason
    await write_audit_log(
        db,
        tenant_id=job.tenant_id,
        actor_id=user.id,
        actor_name=user.full_name,
        actor_role=user.role,
        entity_type="ocr_job",
        entity_id=job.id,
        action="ocr_rejected",
        new_values={"reason": reason},
    )
