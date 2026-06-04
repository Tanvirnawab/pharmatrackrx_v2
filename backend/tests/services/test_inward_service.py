"""
Tests for the inward verification workflow.
Covers: session start, item updates, variance calculation, and session completion.
"""
import uuid
import pytest
from decimal import Decimal
from datetime import date

from sqlalchemy import select

from app.models.transfer_order import TransferOrder, TransferOrderItem, TransferOrderStatus
from app.models.inward import InwardSession, InwardItem
from app.models.discrepancy import Discrepancy, DiscrepancyStatus
from app.services.inward_service import (
    start_inward_session, update_inward_item, complete_inward_session
)


async def _create_test_transfer(db, tenant_id, depot_id, store_id) -> TransferOrder:
    transfer = TransferOrder(
        tenant_id=tenant_id,
        to_number="26TEST/STR/001",
        depot_id=depot_id,
        store_id=store_id,
        transfer_date=date(2026, 5, 30),
        status=TransferOrderStatus.PENDING.value,
        total_items=3,
        total_expected_qty=Decimal("600"),
    )
    db.add(transfer)
    await db.flush()

    items = [
        TransferOrderItem(transfer_order_id=transfer.id, line_number=1,
                          item_name="PARACETAMOL 500MG", expected_qty=Decimal("500")),
        TransferOrderItem(transfer_order_id=transfer.id, line_number=2,
                          item_name="AMOXICILLIN 500MG", expected_qty=Decimal("200")),
        TransferOrderItem(transfer_order_id=transfer.id, line_number=3,
                          item_name="IBUPROFEN 400MG", expected_qty=Decimal("100")),
    ]
    for item in items:
        db.add(item)
    await db.flush()
    return transfer


@pytest.mark.asyncio
async def test_start_inward_session_creates_items(seeded_db):
    db = seeded_db["db"]
    transfer = await _create_test_transfer(
        db, seeded_db["tenant"].id, seeded_db["depot"].id, seeded_db["store"].id
    )
    manager = seeded_db["manager"]

    session = await start_inward_session(
        db,
        transfer_order_id=transfer.id,
        tenant_id=seeded_db["tenant"].id,
        current_user=manager,
    )

    assert session.status == "in_progress"
    assert session.transfer_order_id == transfer.id

    result = await db.execute(
        select(InwardItem).where(InwardItem.session_id == session.id)
    )
    items = result.scalars().all()
    assert len(items) == 3
    assert all(item.received_qty is None for item in items)


@pytest.mark.asyncio
async def test_start_session_twice_raises_conflict(seeded_db):
    from app.core.exceptions import ConflictError
    db = seeded_db["db"]
    transfer = await _create_test_transfer(
        db, seeded_db["tenant"].id, seeded_db["depot"].id, seeded_db["store"].id
    )
    manager = seeded_db["manager"]

    await start_inward_session(
        db, transfer_order_id=transfer.id,
        tenant_id=seeded_db["tenant"].id, current_user=manager,
    )

    with pytest.raises(ConflictError):
        await start_inward_session(
            db, transfer_order_id=transfer.id,
            tenant_id=seeded_db["tenant"].id, current_user=manager,
        )


@pytest.mark.asyncio
async def test_variance_calculation_shortage(seeded_db):
    db = seeded_db["db"]
    transfer = await _create_test_transfer(
        db, seeded_db["tenant"].id, seeded_db["depot"].id, seeded_db["store"].id
    )
    manager = seeded_db["manager"]
    session = await start_inward_session(
        db, transfer_order_id=transfer.id,
        tenant_id=seeded_db["tenant"].id, current_user=manager,
    )

    result = await db.execute(
        select(InwardItem).where(InwardItem.session_id == session.id).order_by(InwardItem.line_number)
    )
    items = result.scalars().all()
    first_item = items[0]  # PARACETAMOL, expected 500

    updated = await update_inward_item(
        db,
        session_id=session.id,
        item_id=first_item.id,
        received_qty=Decimal("497"),
        expiry_date=date(2027, 6, 1),
        notes=None,
        current_user=manager,
    )

    assert updated.received_qty == Decimal("497")
    assert updated.variance == Decimal("-3")
    assert updated.variance_type == "shortage"
    assert updated.expiry_date == date(2027, 6, 1)


@pytest.mark.asyncio
async def test_variance_calculation_excess(seeded_db):
    db = seeded_db["db"]
    transfer = await _create_test_transfer(
        db, seeded_db["tenant"].id, seeded_db["depot"].id, seeded_db["store"].id
    )
    manager = seeded_db["manager"]
    session = await start_inward_session(
        db, transfer_order_id=transfer.id,
        tenant_id=seeded_db["tenant"].id, current_user=manager,
    )

    result = await db.execute(
        select(InwardItem).where(InwardItem.session_id == session.id).order_by(InwardItem.line_number)
    )
    items = result.scalars().all()

    updated = await update_inward_item(
        db, session_id=session.id, item_id=items[0].id,
        received_qty=Decimal("510"), expiry_date=None, notes=None,
        current_user=manager,
    )

    assert updated.variance == Decimal("10")
    assert updated.variance_type == "excess"


@pytest.mark.asyncio
async def test_variance_match(seeded_db):
    db = seeded_db["db"]
    transfer = await _create_test_transfer(
        db, seeded_db["tenant"].id, seeded_db["depot"].id, seeded_db["store"].id
    )
    manager = seeded_db["manager"]
    session = await start_inward_session(
        db, transfer_order_id=transfer.id,
        tenant_id=seeded_db["tenant"].id, current_user=manager,
    )
    result = await db.execute(
        select(InwardItem).where(InwardItem.session_id == session.id).limit(1)
    )
    item = result.scalar_one()

    updated = await update_inward_item(
        db, session_id=session.id, item_id=item.id,
        received_qty=item.expected_qty, expiry_date=None, notes=None,
        current_user=manager,
    )

    assert updated.variance == Decimal("0")
    assert updated.variance_type == "match"


@pytest.mark.asyncio
async def test_complete_session_creates_discrepancies(seeded_db):
    db = seeded_db["db"]
    transfer = await _create_test_transfer(
        db, seeded_db["tenant"].id, seeded_db["depot"].id, seeded_db["store"].id
    )
    manager = seeded_db["manager"]
    session = await start_inward_session(
        db, transfer_order_id=transfer.id,
        tenant_id=seeded_db["tenant"].id, current_user=manager,
    )

    result = await db.execute(
        select(InwardItem).where(InwardItem.session_id == session.id).order_by(InwardItem.line_number)
    )
    items = result.scalars().all()

    # Item 1: shortage
    await update_inward_item(
        db, session_id=session.id, item_id=items[0].id,
        received_qty=Decimal("490"), expiry_date=None, notes=None,
        current_user=manager,
    )
    # Item 2: match
    await update_inward_item(
        db, session_id=session.id, item_id=items[1].id,
        received_qty=Decimal("200"), expiry_date=None, notes=None,
        current_user=manager,
    )
    # Item 3: not verified → treated as 0 on complete (shortage)

    session_out, discrepancies = await complete_inward_session(
        db, session_id=session.id, notes="Test complete",
        tenant_id=seeded_db["tenant"].id, current_user=manager,
    )

    # Should have 2 discrepancies: item 1 shortage + item 3 unverified→shortage
    assert len(discrepancies) == 2
    assert all(d.status == DiscrepancyStatus.OPEN for d in discrepancies)
    shortage_discs = [d for d in discrepancies if d.type == "shortage"]
    assert len(shortage_discs) == 2
    assert session_out.status == "completed"


@pytest.mark.asyncio
async def test_complete_session_is_never_blocked(seeded_db):
    """
    Business rule: completing is always allowed even if zero items are verified.
    All unverified items become shortage discrepancies.
    """
    db = seeded_db["db"]
    transfer = await _create_test_transfer(
        db, seeded_db["tenant"].id, seeded_db["depot"].id, seeded_db["store"].id
    )
    manager = seeded_db["manager"]
    session = await start_inward_session(
        db, transfer_order_id=transfer.id,
        tenant_id=seeded_db["tenant"].id, current_user=manager,
    )

    # Complete without entering any received qtys
    session_out, discrepancies = await complete_inward_session(
        db, session_id=session.id, notes=None,
        tenant_id=seeded_db["tenant"].id, current_user=manager,
    )

    assert session_out.status == "completed"
    assert len(discrepancies) == 3  # All 3 items become shortages
