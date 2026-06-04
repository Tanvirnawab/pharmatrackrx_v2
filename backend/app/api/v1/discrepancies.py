import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.discrepancy import Discrepancy, DiscrepancyComment
from app.models.user import User
from app.schemas import (
    DiscrepancyOut, DiscrepancyDetail, DiscrepancyCommentOut,
    DepotResponseRequest, ResolveDiscrepancyRequest, AddCommentRequest,
)
from app.schemas.common import PaginatedResponse
from app.services.discrepancy_service import (
    get_discrepancy, add_depot_response, resolve_discrepancy, add_comment, attach_file
)
from app.core.exceptions import ForbiddenError

router = APIRouter(prefix="/discrepancies", tags=["discrepancies"])


def _disc_to_out(disc: Discrepancy, detail: bool = False):
    to_number = disc.transfer_order.to_number if disc.transfer_order else None

    base = {
        "id": disc.id,
        "type": disc.type,
        "status": disc.status,
        "item_name": disc.item_name,
        "expected_qty": disc.expected_qty,
        "received_qty": disc.received_qty,
        "variance_qty": disc.variance_qty,
        "notes": disc.notes,
        "depot": disc.depot,
        "store": disc.store,
        "to_number": to_number,
        "raised_by_name": disc.raiser.full_name if disc.raiser else None,
        "created_at": disc.created_at,
        "resolved_at": disc.resolved_at,
    }

    if detail:
        base.update({
            "depot_response": disc.depot_response,
            "depot_responded_at": disc.depot_responded_at,
            "depot_responded_by_name": (
                disc.depot_responder.full_name if disc.depot_responder else None
            ),
            "resolution_notes": disc.resolution_notes,
            "resolved_by_name": disc.resolver.full_name if disc.resolver else None,
            "comments": [
                {
                    "id": c.id,
                    "body": c.body,
                    "author_name": c.author.full_name if c.author else "System",
                    "created_at": c.created_at,
                }
                for c in disc.comments
            ],
            "attachments": [
                {
                    "id": a.id,
                    "label": a.label,
                    "filename": a.file.filename,
                    "mime_type": a.file.mime_type,
                    "size_bytes": a.file.size_bytes,
                }
                for a in disc.attachments
                if a.file
            ],
        })
    return base


def _build_disc_filters(current_user: User, **kwargs):
    filters = [Discrepancy.tenant_id == current_user.tenant_id]
    if current_user.role in ("store_manager", "store_staff") and current_user.store_id:
        filters.append(Discrepancy.store_id == current_user.store_id)
    elif current_user.role == "depot_staff" and current_user.depot_id:
        filters.append(Discrepancy.depot_id == current_user.depot_id)

    if kwargs.get("status"):
        filters.append(Discrepancy.status == kwargs["status"])
    if kwargs.get("type"):
        filters.append(Discrepancy.type == kwargs["type"])
    if kwargs.get("depot_id") and current_user.role == "admin":
        filters.append(Discrepancy.depot_id == kwargs["depot_id"])
    if kwargs.get("store_id") and current_user.role == "admin":
        filters.append(Discrepancy.store_id == kwargs["store_id"])
    return filters


@router.get("", response_model=PaginatedResponse[DiscrepancyOut])
async def list_discrepancies(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    depot_id: Optional[uuid.UUID] = Query(None),
    store_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = _build_disc_filters(
        current_user, status=status, type=type, depot_id=depot_id, store_id=store_id
    )

    count_q = await db.execute(
        select(func.count()).select_from(Discrepancy).where(*filters)
    )
    total = count_q.scalar() or 0

    q = (
        select(Discrepancy)
        .options(
            selectinload(Discrepancy.depot),
            selectinload(Discrepancy.store),
            selectinload(Discrepancy.raiser),
            selectinload(Discrepancy.transfer_order),
        )
        .where(*filters)
        .order_by(Discrepancy.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    discs = result.scalars().all()

    return PaginatedResponse(
        items=[DiscrepancyOut.model_validate(_disc_to_out(d)) for d in discs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{discrepancy_id}", response_model=DiscrepancyDetail)
async def get_discrepancy_detail(
    discrepancy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    disc = await get_discrepancy(
        db, discrepancy_id=discrepancy_id, tenant_id=current_user.tenant_id
    )
    # Scope check
    if current_user.role in ("store_manager", "store_staff"):
        if current_user.store_id and disc.store_id != current_user.store_id:
            raise ForbiddenError("Access denied.")
    elif current_user.role == "depot_staff":
        if current_user.depot_id and disc.depot_id != current_user.depot_id:
            raise ForbiddenError("Access denied.")
    return DiscrepancyDetail.model_validate(_disc_to_out(disc, detail=True))


@router.post("/{discrepancy_id}/depot-response", response_model=DiscrepancyDetail)
async def depot_response(
    discrepancy_id: uuid.UUID,
    body: DepotResponseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Depot staff provides their explanation for the discrepancy."""
    disc = await add_depot_response(
        db,
        discrepancy_id=discrepancy_id,
        tenant_id=current_user.tenant_id,
        response_text=body.response,
        current_user=current_user,
    )
    disc = await get_discrepancy(
        db, discrepancy_id=discrepancy_id, tenant_id=current_user.tenant_id
    )
    return DiscrepancyDetail.model_validate(_disc_to_out(disc, detail=True))


@router.post("/{discrepancy_id}/resolve", response_model=DiscrepancyDetail)
async def resolve(
    discrepancy_id: uuid.UUID,
    body: ResolveDiscrepancyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin resolves, rejects, or closes a discrepancy."""
    disc = await resolve_discrepancy(
        db,
        discrepancy_id=discrepancy_id,
        tenant_id=current_user.tenant_id,
        new_status=body.new_status,
        resolution_notes=body.resolution_notes,
        current_user=current_user,
    )
    disc = await get_discrepancy(
        db, discrepancy_id=discrepancy_id, tenant_id=current_user.tenant_id
    )
    return DiscrepancyDetail.model_validate(_disc_to_out(disc, detail=True))


@router.post("/{discrepancy_id}/comments", response_model=DiscrepancyCommentOut)
async def post_comment(
    discrepancy_id: uuid.UUID,
    body: AddCommentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = await add_comment(
        db,
        discrepancy_id=discrepancy_id,
        tenant_id=current_user.tenant_id,
        body=body.body,
        current_user=current_user,
    )
    await db.flush()
    return DiscrepancyCommentOut.model_validate({
        "id": comment.id,
        "body": comment.body,
        "author_name": current_user.full_name,
        "created_at": comment.created_at,
    })
