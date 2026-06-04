"""
Tests for the Excel import service using data that matches the real AExpert format.
"""
import io
import uuid
import pytest
from decimal import Decimal
from datetime import date
import openpyxl

from app.services.import_service import _parse_excel_bytes, import_transfer_orders


def _make_excel_bytes(rows: list[tuple]) -> bytes:
    """Helper: build an AExpert-style Excel file in memory."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "IVW2121stockinw"
    ws.append(("Pending Stock Inward Report",) + (None,) * 10)
    ws.append(("Pending Stock Inward Report",) + (None,) * 10)
    ws.append((
        "Transfer No", "Transfer Date", "Location (From)", "Location (To)",
        "Itemname", "SBM($)", "Discontinued?", "Stock", "Transfer Qty", "Balanceqty", None
    ))
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


SAMPLE_DATE = date(2026, 5, 30)
from datetime import datetime
SAMPLE_DT = datetime(2026, 5, 30, 0, 0)


def test_parse_single_transfer():
    rows = [
        ("26MATD/STR/000247", SAMPLE_DT, "MATADI DEPOT", "BOMA P1",
         "PARACETAMOL 500MG", 0.5, "No", 100, 500, 500, "Make Inward"),
        (None, None, None, None, "Total", None, None, None, 500, 500, None),
    ]
    parsed, errors = _parse_excel_bytes(_make_excel_bytes(rows))
    assert len(parsed) == 1
    assert parsed[0].to_number == "26MATD/STR/000247"
    assert parsed[0].item_name == "PARACETAMOL 500MG"
    assert parsed[0].expected_qty == Decimal("500")
    assert parsed[0].depot_name == "MATADI DEPOT"
    assert parsed[0].store_name == "BOMA P1"
    assert parsed[0].transfer_date == SAMPLE_DATE


def test_parse_skips_total_rows():
    rows = [
        ("26MWH/STRM/000702", SAMPLE_DT, "MITENDI WAREHOUSE", "BOMA P1",
         "AMOXICILLIN 500MG", 1.0, "No", 200, 300, 300, "Make Inward"),
        ("26MWH/STRM/000702", SAMPLE_DT, "MITENDI WAREHOUSE", "BOMA P1",
         "PARACETAMOL 500MG", 0.5, "No", 100, 200, 200, "Make Inward"),
        (None, None, None, None, "Total", None, None, None, 500, 500, None),
    ]
    parsed, errors = _parse_excel_bytes(_make_excel_bytes(rows))
    assert len(parsed) == 2
    names = [p.item_name for p in parsed]
    assert "AMOXICILLIN 500MG" in names
    assert "PARACETAMOL 500MG" in names


def test_parse_duplicate_medicine_within_transfer():
    """Same medicine appears twice in one transfer — both should be parsed."""
    rows = [
        ("26MWH/STRM/000702", SAMPLE_DT, "MITENDI WAREHOUSE", "BOMA P1",
         "ARTES 30 MG INJ B/1 AMP (I)", 1.29, "No", 256, 408, 408, "Make Inward"),
        ("26MWH/STRM/000702", SAMPLE_DT, "MITENDI WAREHOUSE", "BOMA P1",
         "ARTES 30 MG INJ B/1 AMP (I)", 1.29, "No", 256, 92, 92, "Make Inward"),
        (None, None, None, None, "Total", None, None, None, 500, 500, None),
    ]
    parsed, errors = _parse_excel_bytes(_make_excel_bytes(rows))
    assert len(parsed) == 2
    assert parsed[0].expected_qty == Decimal("408")
    assert parsed[1].expected_qty == Decimal("92")


def test_parse_multiple_transfers():
    rows = [
        ("26MATD/STR/000001", SAMPLE_DT, "DEPOT A", "STORE A",
         "MEDICINE A", 1.0, "No", 10, 100, 100, "Make Inward"),
        (None, None, None, None, "Total", None, None, None, 100, 100, None),
        ("26MATD/STR/000002", SAMPLE_DT, "DEPOT B", "STORE B",
         "MEDICINE B", 2.0, "No", 20, 200, 200, "Make Inward"),
        (None, None, None, None, "Total", None, None, None, 200, 200, None),
    ]
    parsed, errors = _parse_excel_bytes(_make_excel_bytes(rows))
    assert len(parsed) == 2
    assert {p.to_number for p in parsed} == {"26MATD/STR/000001", "26MATD/STR/000002"}


def test_parse_invalid_qty_skips_row():
    rows = [
        ("26MATD/STR/000001", SAMPLE_DT, "DEPOT A", "STORE A",
         "MEDICINE A", 1.0, "No", 10, "NOT_A_NUMBER", 100, "Make Inward"),
        ("26MATD/STR/000001", SAMPLE_DT, "DEPOT A", "STORE A",
         "MEDICINE B", 1.0, "No", 10, 50, 50, "Make Inward"),
    ]
    parsed, errors = _parse_excel_bytes(_make_excel_bytes(rows))
    assert len(parsed) == 1  # Second row only
    assert len(errors) == 1  # One error logged


@pytest.mark.asyncio
async def test_import_idempotent(seeded_db):
    """Importing same file twice should create transfers only once."""
    rows = [
        ("26TEST/STR/000001", SAMPLE_DT, "MITENDI WAREHOUSE", "BOMA P1",
         "TEST MEDICINE 500MG", 1.5, "No", 50, 100, 100, "Make Inward"),
    ]
    file_bytes = _make_excel_bytes(rows)
    db = seeded_db["db"]
    tenant_id = seeded_db["tenant"].id
    importer_id = seeded_db["admin"].id

    result1 = await import_transfer_orders(
        db, tenant_id=tenant_id, importer_id=importer_id,
        file_bytes=file_bytes, filename="test.xlsx"
    )
    result2 = await import_transfer_orders(
        db, tenant_id=tenant_id, importer_id=importer_id,
        file_bytes=file_bytes, filename="test.xlsx"
    )

    assert result1.transfers_created == 1
    assert result1.items_created == 1
    assert result2.transfers_created == 0
    assert result2.transfers_skipped == 1


@pytest.mark.asyncio
async def test_import_creates_depot_and_store_on_first_run(seeded_db):
    """Depots/stores from the Excel file are auto-created if they don't exist."""
    rows = [
        ("26NEW/STR/000099", SAMPLE_DT, "BRAND NEW DEPOT", "BRAND NEW STORE",
         "SOME MEDICINE", 1.0, "No", 0, 50, 50, "Make Inward"),
    ]
    file_bytes = _make_excel_bytes(rows)
    db = seeded_db["db"]
    result = await import_transfer_orders(
        db, tenant_id=seeded_db["tenant"].id, importer_id=seeded_db["admin"].id,
        file_bytes=file_bytes, filename="new.xlsx"
    )
    assert result.transfers_created == 1
