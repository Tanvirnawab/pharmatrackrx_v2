"""
Import service for AExpert Excel/CSV transfer order exports.

Expected Excel format (from sample):
  Row 0-1: Title row ("Pending Stock Inward Report")
  Row 2:   Headers: Transfer No | Transfer Date | Location (From) | Location (To) |
                    Itemname | SBM($) | Discontinued? | Stock | Transfer Qty | Balanceqty
  Row 3+:  Data rows; "Total" summary rows have None in col[0]

Same medicine can appear multiple times within one transfer — treated as
separate line items with distinct line_number values.
"""
import uuid
import io
from decimal import Decimal
from datetime import date, datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
import openpyxl

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.depot_store import Depot, Store
from app.models.transfer_order import TransferOrder, TransferOrderItem, TransferOrderStatus
from app.core.exceptions import ImportError as PharmaImportError


@dataclass
class ParsedRow:
    to_number: str
    transfer_date: date
    depot_name: str
    store_name: str
    item_name: str
    expected_qty: Decimal
    unit_price: Optional[Decimal]
    depot_stock: Optional[Decimal]


@dataclass
class ImportResult:
    transfers_created: int = 0
    transfers_skipped: int = 0  # already imported
    items_created: int = 0
    errors: list[str] = field(default_factory=list)
    transfer_numbers: list[str] = field(default_factory=list)


def _parse_excel_bytes(file_bytes: bytes) -> list[ParsedRow]:
    """Parse raw .xlsx bytes into a list of ParsedRow objects."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as e:
        raise PharmaImportError(f"Cannot read Excel file: {e}")

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if len(rows) < 3:
        raise PharmaImportError("File has fewer than 3 rows — not a valid AExpert export.")

    # Detect header row (first row containing "Transfer No")
    header_row_idx = None
    for i, row in enumerate(rows[:5]):  # Header is in first 5 rows
        if row and str(row[0]).strip() == "Transfer No":
            header_row_idx = i
            break

    if header_row_idx is None:
        raise PharmaImportError(
            "Could not find 'Transfer No' header. "
            "Ensure this is an AExpert Pending Stock Inward Report."
        )

    parsed: list[ParsedRow] = []
    line_errors: list[str] = []

    for row_idx, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 2):
        # Skip blank rows and "Total" summary rows
        if not row or row[0] is None:
            continue
        to_number = str(row[0]).strip()
        if not to_number or to_number.lower() == "transfer no":
            continue

        item_name_raw = row[4] if len(row) > 4 else None
        if item_name_raw is None or str(item_name_raw).strip().lower() in ("total", ""):
            continue

        # Parse transfer date
        transfer_date_raw = row[1] if len(row) > 1 else None
        if isinstance(transfer_date_raw, datetime):
            transfer_date = transfer_date_raw.date()
        elif isinstance(transfer_date_raw, date):
            transfer_date = transfer_date_raw
        else:
            line_errors.append(f"Row {row_idx}: Invalid date '{transfer_date_raw}' — skipped.")
            continue

        depot_name = str(row[2]).strip() if row[2] else "Unknown Depot"
        store_name = str(row[3]).strip() if row[3] else "Unknown Store"
        item_name = str(item_name_raw).strip()

        # Transfer Qty is column index 8
        try:
            expected_qty = Decimal(str(row[8])) if row[8] is not None else Decimal("0")
        except Exception:
            line_errors.append(f"Row {row_idx}: Invalid qty '{row[8]}' for '{item_name}' — skipped.")
            continue

        # SBM price (col 5) — optional
        try:
            unit_price = Decimal(str(row[5])) if row[5] is not None else None
        except Exception:
            unit_price = None

        # Depot stock (col 7) — optional
        try:
            depot_stock = Decimal(str(row[7])) if row[7] is not None else None
        except Exception:
            depot_stock = None

        parsed.append(ParsedRow(
            to_number=to_number,
            transfer_date=transfer_date,
            depot_name=depot_name,
            store_name=store_name,
            item_name=item_name,
            expected_qty=expected_qty,
            unit_price=unit_price,
            depot_stock=depot_stock,
        ))

    if line_errors:
        # Non-fatal: return partial results but log errors
        pass

    return parsed, line_errors


async def _get_or_create_depot(
    db: AsyncSession, tenant_id: uuid.UUID, name: str
) -> Depot:
    result = await db.execute(
        select(Depot).where(Depot.tenant_id == tenant_id, Depot.name == name)
    )
    depot = result.scalar_one_or_none()
    if not depot:
        depot = Depot(tenant_id=tenant_id, name=name)
        db.add(depot)
        await db.flush()  # Get ID without committing
    return depot


async def _get_or_create_store(
    db: AsyncSession, tenant_id: uuid.UUID, name: str
) -> Store:
    result = await db.execute(
        select(Store).where(Store.tenant_id == tenant_id, Store.name == name)
    )
    store = result.scalar_one_or_none()
    if not store:
        store = Store(tenant_id=tenant_id, name=name)
        db.add(store)
        await db.flush()
    return store


async def import_transfer_orders(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    importer_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
) -> ImportResult:
    """
    Parse an AExpert Excel export and persist transfer orders + items.
    Idempotent: skips transfers that are already in the database.
    Returns a summary of what was created.
    """
    parsed_rows, parse_errors = _parse_excel_bytes(file_bytes)

    if not parsed_rows:
        raise PharmaImportError(
            "No valid data rows found in the file. " + " ".join(parse_errors)
        )

    # Group rows by Transfer No
    from collections import defaultdict
    groups: dict[str, list[ParsedRow]] = defaultdict(list)
    for row in parsed_rows:
        groups[row.to_number].append(row)

    result = ImportResult(errors=parse_errors)

    for to_number, rows in groups.items():
        # Check if already imported
        existing = await db.execute(
            select(TransferOrder).where(
                TransferOrder.tenant_id == tenant_id,
                TransferOrder.to_number == to_number,
            )
        )
        if existing.scalar_one_or_none():
            result.transfers_skipped += 1
            continue

        first = rows[0]  # All rows in group share depot/store/date

        depot = await _get_or_create_depot(db, tenant_id, first.depot_name)
        store = await _get_or_create_store(db, tenant_id, first.store_name)

        transfer = TransferOrder(
            tenant_id=tenant_id,
            to_number=to_number,
            depot_id=depot.id,
            store_id=store.id,
            transfer_date=first.transfer_date,
            status=TransferOrderStatus.PENDING.value,
            total_items=len(rows),
            total_expected_qty=sum(r.expected_qty for r in rows),
            imported_by=importer_id,
            import_filename=filename,
            imported_at=datetime.now(timezone.utc),
        )
        db.add(transfer)
        await db.flush()  # Get transfer.id

        for line_number, row in enumerate(rows, start=1):
            item = TransferOrderItem(
                transfer_order_id=transfer.id,
                line_number=line_number,
                item_name=row.item_name,
                expected_qty=row.expected_qty,
                unit_price=row.unit_price,
                depot_stock=row.depot_stock,
            )
            db.add(item)

        result.transfers_created += 1
        result.items_created += len(rows)
        result.transfer_numbers.append(to_number)

    return result
