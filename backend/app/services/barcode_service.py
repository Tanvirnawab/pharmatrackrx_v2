"""
Barcode service — GS1-128 / EAN / Code-128 parsing and medicine matching.

Supports:
  - GS1-128 with parenthesised AIs: (01)GTIN(10)BATCH(17)EXPIRY
  - GS1-128 raw (no parentheses): 01GTIN10BATCH17EXPIRY
  - GS1 prefix markers: ]C1 or \\x1d (FNC1)
  - EAN-13 / EAN-8 (plain numeric strings)
  - Code-128 / plain alphanumeric fallback

All parsing is best-effort. Partial results are returned when only some
Application Identifiers are present. Never raises; always returns a result.
"""
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.inward import InwardItem


# ── GS1 Application Identifier (AI) definitions ──────────────────────────────
# Format: AI → (length_if_fixed | None, description)
# Variable-length AIs terminate at FNC1 or end of string.
_FIXED_AIS: dict[str, int] = {
    "00": 18,   # SSCC
    "01": 14,   # GTIN-14
    "02": 14,   # GTIN of contained items
    "11": 6,    # Production date YYMMDD
    "13": 6,    # Packaging date YYMMDD
    "15": 6,    # Best before YYMMDD
    "17": 6,    # Expiration date YYMMDD
    "310": 7,   # Net weight kg (4 decimals) → 310n where n=decimal places
    "311": 7,
    "312": 7,
}
_VAR_AIS = {"10", "21", "240", "251", "30", "37"}


@dataclass
class GS1ParseResult:
    raw: str = ""
    is_gs1: bool = False
    barcode_type: str = "unknown"   # GS1_128 | EAN_13 | EAN_8 | CODE_128 | PLAIN
    gtin: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    serial_number: Optional[str] = None
    errors: list[str] = field(default_factory=list)


def parse_barcode(raw: str) -> GS1ParseResult:
    """Entry point: detect format and parse."""
    raw = (raw or "").strip()
    result = GS1ParseResult(raw=raw)
    if not raw:
        result.errors.append("Empty barcode")
        return result

    # Strip GS1 symbology identifiers
    clean = raw
    if clean.startswith("]C1") or clean.startswith("]d2") or clean.startswith("]Q3"):
        clean = clean[3:]
        result.is_gs1 = True
    # Replace GS/FNC1 separator with opening paren
    clean = clean.replace("\x1d", "\x1d")  # keep as-is for now, handle below

    # Parenthesised format: (01)... most common from label printers
    if "(" in clean:
        return _parse_parenthesised(raw, clean, result)

    # FNC1-separated raw format
    if "\x1d" in clean:
        return _parse_fnc1(raw, clean, result)

    # Pure numeric — could be EAN or raw GS1
    if clean.isdigit():
        if len(clean) == 13:
            result.barcode_type = "EAN_13"
            result.gtin = clean.zfill(14)
            result.is_gs1 = True
            return result
        if len(clean) == 8:
            result.barcode_type = "EAN_8"
            return result
        if len(clean) >= 16 and clean.startswith("01"):
            return _parse_raw_gs1(raw, clean, result)

    # Fallback: Code-128 or plain product code
    result.barcode_type = "CODE_128"
    return result


def _parse_parenthesised(raw: str, clean: str, result: GS1ParseResult) -> GS1ParseResult:
    """Parse (AI)value(AI)value format."""
    result.is_gs1 = True
    result.barcode_type = "GS1_128"
    pattern = re.compile(r"\((\d{2,4})\)([^(]*)")
    for m in pattern.finditer(clean):
        ai, value = m.group(1), m.group(2).strip()
        _apply_ai(result, ai, value)
    return result


def _parse_fnc1(raw: str, clean: str, result: GS1ParseResult) -> GS1ParseResult:
    """Parse FNC1-delimited raw GS1 string."""
    result.is_gs1 = True
    result.barcode_type = "GS1_128"
    parts = clean.split("\x1d")
    for part in parts:
        if not part:
            continue
        _consume_ais(result, part)
    return result


def _parse_raw_gs1(raw: str, clean: str, result: GS1ParseResult) -> GS1ParseResult:
    """Parse concatenated raw GS1 string (no separators)."""
    result.is_gs1 = True
    result.barcode_type = "GS1_128"
    _consume_ais(result, clean)
    return result


def _consume_ais(result: GS1ParseResult, s: str) -> None:
    """Walk string consuming AIs in order."""
    i = 0
    while i < len(s):
        matched = False
        for length in (4, 3, 2):
            if i + length > len(s):
                continue
            ai = s[i: i + length]
            if ai in _FIXED_AIS:
                data_len = _FIXED_AIS[ai]
                value = s[i + length: i + length + data_len]
                _apply_ai(result, ai, value)
                i += length + data_len
                matched = True
                break
            base = ai[:2] if len(ai) >= 2 else ai
            if base in _VAR_AIS:
                # Read until end or next known AI
                rest = s[i + length:]
                value = rest  # variable length, take all remaining
                _apply_ai(result, base, value)
                i = len(s)  # consumed everything
                matched = True
                break
        if not matched:
            i += 1  # skip unrecognised character


def _apply_ai(result: GS1ParseResult, ai: str, value: str) -> None:
    """Map a parsed AI + value onto the result object."""
    try:
        if ai == "01":
            result.gtin = value.strip()
        elif ai in ("10",):
            result.batch_number = value.strip() or None
        elif ai in ("17", "15"):
            result.expiry_date = _parse_yymmdd(value.strip())
        elif ai == "21":
            result.serial_number = value.strip() or None
    except Exception as e:
        result.errors.append(f"AI {ai}: {e}")


def _parse_yymmdd(s: str) -> Optional[date]:
    """Convert YYMMDD string to date. YY < 50 → 2000s, else 1900s."""
    if len(s) < 6:
        return None
    try:
        yy, mm, dd = int(s[:2]), int(s[2:4]), int(s[4:6])
        year = 2000 + yy if yy < 50 else 1900 + yy
        # DD=00 means last day of month — default to 28
        return date(year, mm, dd if dd > 0 else 28)
    except (ValueError, TypeError):
        return None


# ── Medicine matching ─────────────────────────────────────────────────────────

@dataclass
class ScanMatchResult:
    scan: GS1ParseResult
    result: str          # 'match' | 'mismatch' | 'unknown'
    matched_item_id: Optional[uuid.UUID] = None
    confidence: float = 0.0
    notes: str = ""


async def match_scan_to_item(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    raw_barcode: str,
) -> ScanMatchResult:
    """
    Parse the barcode and try to match it against the expected medicine.
    Returns 'match', 'mismatch', or 'unknown' with confidence score.
    """
    parsed = parse_barcode(raw_barcode)

    # Load the inward item
    result = await db.execute(
        select(InwardItem).where(InwardItem.id == item_id, InwardItem.session_id == session_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return ScanMatchResult(scan=parsed, result="unknown", notes="Item not found")

    # If we don't have structured GS1 data, just record as 'unknown'
    if not parsed.is_gs1 and parsed.barcode_type == "CODE_128":
        return ScanMatchResult(
            scan=parsed, result="unknown", matched_item_id=item.id,
            notes="Non-GS1 barcode — cannot verify against medicine master"
        )

    # Fuzzy name match: check if any word from the scanned GTIN/batch appears in item_name
    # In pharma, GTIN encodes product identity; we do a best-effort text match
    item_name_upper = item.item_name.upper()
    confidence = 0.0

    if parsed.gtin:
        # Very basic: GTINs don't directly match names — mark as unknown
        # In V3 this connects to a medicine master with GTIN lookup
        confidence = 0.3
        return ScanMatchResult(
            scan=parsed, result="unknown", matched_item_id=item.id,
            confidence=confidence,
            notes="GS1 GTIN detected — no medicine master to match against yet. Record manually."
        )

    return ScanMatchResult(
        scan=parsed, result="unknown", matched_item_id=item.id,
        confidence=0.0,
        notes="Barcode scanned and recorded. Manual verification required."
    )
