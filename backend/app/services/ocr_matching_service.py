import difflib
import uuid
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr import OcrJob, OcrResult, OcrMatchResult, OcrMatchStatus
from app.models.transfer_order import TransferOrder, TransferOrderItem


def _score(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


async def rebuild_matches(db: AsyncSession, job: OcrJob) -> None:
    if not job.transfer_order_id:
        return

    order = await db.get(TransferOrder, job.transfer_order_id)
    if not order:
        return

    items_q = await db.execute(
        select(TransferOrderItem).where(TransferOrderItem.transfer_order_id == order.id)
    )
    transfer_items = items_q.scalars().all()
    await db.execute(
        OcrMatchResult.__table__.delete().where(OcrMatchResult.job_id == job.id)
    )

    for result in job.results:
        best_item = None
        best_score = 0.0
        for item in transfer_items:
            score = _score(result.medicine_name, item.item_name)
            if score > best_score:
                best_score = score
                best_item = item

        status = OcrMatchStatus.UNKNOWN
        mismatches: dict[str, str] = {}
        if best_item and best_score >= 0.75:
            status = OcrMatchStatus.MATCH
            if result.quantity is not None and Decimal(result.quantity) != Decimal(best_item.expected_qty):
                status = OcrMatchStatus.MISMATCH
                mismatches["quantity"] = f"OCR {result.quantity} vs transfer {best_item.expected_qty}"
        elif best_item:
            status = OcrMatchStatus.MISMATCH
            mismatches["medicine_name"] = f"Low confidence match with {best_item.item_name}"

        db.add(OcrMatchResult(
            job_id=job.id,
            ocr_result_id=result.id,
            transfer_item_id=best_item.id if best_item else None,
            match_status=status,
            confidence_score=round(best_score * 100, 2),
            mismatch_fields=mismatches or None,
        ))


async def verify_transfer_scope(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    transfer_order_id: uuid.UUID | None,
) -> TransferOrder | None:
    if not transfer_order_id:
        return None
    result = await db.execute(
        select(TransferOrder).where(
            TransferOrder.id == transfer_order_id,
            TransferOrder.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()
