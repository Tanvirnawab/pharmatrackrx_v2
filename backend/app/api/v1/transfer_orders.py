import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_manager_or_above
from app.models.transfer_order import TransferOrder, TransferOrderStatus
from app.models.user import User
from app.schemas import TransferOrderOut, TransferOrderDetail, ImportResult
from app.schemas.common import PaginatedResponse
from app.services.import_service import import_transfer_orders
from app.core.exceptions import NotFoundError, ForbiddenError

router = APIRouter(prefix="/transfer-orders", tags=["transfer-orders"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _build_scope_filter(user: User):
    """Build store/depot filter based on user role."""
    filters = [TransferOrder.tenant_id == user.tenant_id]
    if user.role == "store_manager" or user.role == "store_staff":
        if user.store_id:
            filters.append(TransferOrder.store_id == user.store_id)
    elif user.role == "depot_staff":
        if user.depot_id:
            filters.append(TransferOrder.depot_id == user.depot_id)
    return filters


@router.post("/import", response_model=ImportResult)
async def import_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    """
    Upload an AExpert Pending Stock Inward Report (.xlsx).
    Creates transfer orders + items. Idempotent — skips existing TO numbers.
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        from app.core.exceptions import ImportError as PharmaImportError
        raise PharmaImportError("Only .xlsx, .xls, or .csv files are accepted.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        from app.core.exceptions import ImportError as PharmaImportError
        raise PharmaImportError("File too large. Maximum size is 10 MB.")

    result = await import_transfer_orders(
        db,
        tenant_id=current_user.tenant_id,
        importer_id=current_user.id,
        file_bytes=content,
        filename=file.filename,
    )

    result.message = (
        f"Import complete: {result.transfers_created} transfer(s) created, "
        f"{result.transfers_skipped} skipped (already imported), "
        f"{result.items_created} line items added."
    )
    return result


@router.get("", response_model=PaginatedResponse[TransferOrderOut])
async def list_transfer_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    store_id: Optional[uuid.UUID] = Query(None),
    depot_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = _build_scope_filter(current_user)

    if status:
        filters.append(TransferOrder.status == status)
    if store_id and current_user.role == "admin":
        filters.append(TransferOrder.store_id == store_id)
    if depot_id and current_user.role in ("admin", "depot_staff"):
        filters.append(TransferOrder.depot_id == depot_id)

    # Count
    count_q = await db.execute(select(func.count()).select_from(TransferOrder).where(*filters))
    total = count_q.scalar() or 0

    # Fetch
    q = (
        select(TransferOrder)
        .options(
            selectinload(TransferOrder.depot),
            selectinload(TransferOrder.store),
        )
        .where(*filters)
        .order_by(TransferOrder.transfer_date.desc(), TransferOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    orders = result.scalars().all()

    return PaginatedResponse(
        items=[TransferOrderOut.model_validate(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{transfer_order_id}", response_model=TransferOrderDetail)
async def get_transfer_order(
    transfer_order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TransferOrder)
        .options(
            selectinload(TransferOrder.depot),
            selectinload(TransferOrder.store),
            selectinload(TransferOrder.items),
        )
        .where(
            TransferOrder.id == transfer_order_id,
            TransferOrder.tenant_id == current_user.tenant_id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundError("TransferOrder", str(transfer_order_id))

    # Scope check
    if current_user.role == "store_staff" and current_user.store_id != order.store_id:
        raise ForbiddenError("Access denied to this transfer order.")

    return TransferOrderDetail.model_validate(order)
