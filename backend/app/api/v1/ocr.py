import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, require_manager_or_above
from app.core.exceptions import NotFoundError, ForbiddenError
from app.db.session import get_db
from app.models.user import User
from app.models.ocr import OcrJob, OcrJobStatus, OcrResult
from app.models.transfer_order import TransferOrder
from app.schemas import OcrJobOut, OcrJobDetail, OcrApproveRequest, OcrRejectRequest
from app.schemas.common import PaginatedResponse
from app.services.storage_service import store_upload
from app.services.ocr_queue_service import enqueue_ocr_job
from app.services.ocr_document_service import get_job_for_tenant, approve_ocr_job, reject_ocr_job
from app.services.ocr_matching_service import verify_transfer_scope, rebuild_matches
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/ocr", tags=["ocr"])

MAX_OCR_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}


def _scope_filters(user: User):
    filters = [OcrJob.tenant_id == user.tenant_id]
    if user.role in ("store_manager", "store_staff") and user.store_id:
        filters.append(TransferOrder.store_id == user.store_id)
    if user.role == "depot_staff" and user.depot_id:
        filters.append(TransferOrder.depot_id == user.depot_id)
    return filters


@router.post("/upload", response_model=OcrJobOut)
async def upload_ocr_document(
    file: UploadFile = File(...),
    transfer_order_id: Optional[uuid.UUID] = Form(None),
    document_type: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    if not file.filename:
        raise ForbiddenError("Filename is required.")
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_TYPES:
        raise ForbiddenError("Only PDF and image files are supported for OCR upload.")

    content = await file.read()
    if len(content) > MAX_OCR_UPLOAD_BYTES:
        raise ForbiddenError("File too large. Maximum size is 25 MB.")

    order = await verify_transfer_scope(
        db, tenant_id=current_user.tenant_id, transfer_order_id=transfer_order_id
    )
    if transfer_order_id and not order:
        raise NotFoundError("TransferOrder", str(transfer_order_id))

    if order and current_user.role in ("store_manager", "store_staff") and current_user.store_id != order.store_id:
        raise ForbiddenError("Access denied to this transfer order.")

    stored = await store_upload(
        db,
        tenant_id=current_user.tenant_id,
        uploader_id=current_user.id,
        filename=file.filename,
        mime_type=mime_type,
        content=content,
    )
    job = OcrJob(
        tenant_id=current_user.tenant_id,
        uploader_id=current_user.id,
        file_upload_id=stored.upload.id,
        transfer_order_id=transfer_order_id,
        document_type=document_type,
        status=OcrJobStatus.QUEUED,
        metadata_json={"filename": file.filename, "mime_type": mime_type},
    )
    db.add(job)
    await db.flush()
    await write_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        entity_type="ocr_job",
        entity_id=job.id,
        entity_label=file.filename,
        action="ocr_uploaded",
        new_values={"transfer_order_id": str(transfer_order_id) if transfer_order_id else None},
    )
    await enqueue_ocr_job(job.id)
    return OcrJobOut.model_validate(job)


@router.get("/jobs", response_model=PaginatedResponse[OcrJobOut])
async def list_ocr_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = _scope_filters(current_user)
    if status:
        filters.append(OcrJob.status == status)

    base = select(OcrJob).outerjoin(TransferOrder, OcrJob.transfer_order_id == TransferOrder.id).where(*filters)
    count_q = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_q.scalar() or 0

    rows_q = await db.execute(
        base.order_by(OcrJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    jobs = rows_q.scalars().all()
    return PaginatedResponse(
        items=[OcrJobOut.model_validate(job) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/job/{job_id}", response_model=OcrJobDetail)
async def get_ocr_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await get_job_for_tenant(db, job_id=job_id, tenant_id=current_user.tenant_id)
    if not job:
        raise NotFoundError("OcrJob", str(job_id))
    return OcrJobDetail.model_validate(job)


@router.get("/job/{job_id}/results", response_model=OcrJobDetail)
async def get_ocr_job_results(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_ocr_job(job_id, db, current_user)


@router.post("/job/{job_id}/approve", response_model=OcrJobDetail)
async def approve_job(
    job_id: uuid.UUID,
    payload: OcrApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    job = await get_job_for_tenant(db, job_id=job_id, tenant_id=current_user.tenant_id)
    if not job:
        raise NotFoundError("OcrJob", str(job_id))
    corrections = {c.result_id: c for c in payload.corrections}
    for result in job.results:
        correction = corrections.get(result.id)
        if correction:
            result.corrected_data = correction.model_dump(exclude_none=True, mode="json")
            for key, value in correction.model_dump(exclude={"result_id"}, exclude_none=True).items():
                setattr(result, key, value)
    await db.flush()
    await rebuild_matches(db, job)
    await approve_ocr_job(db, job=job, user=current_user, notes=payload.notes)
    await db.flush()
    return OcrJobDetail.model_validate(job)


@router.post("/job/{job_id}/reject", response_model=OcrJobOut)
async def reject_job(
    job_id: uuid.UUID,
    payload: OcrRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    job = await get_job_for_tenant(db, job_id=job_id, tenant_id=current_user.tenant_id)
    if not job:
        raise NotFoundError("OcrJob", str(job_id))
    await reject_ocr_job(db, job=job, user=current_user, reason=payload.reason)
    return OcrJobOut.model_validate(job)
