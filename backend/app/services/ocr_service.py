"""
OCR service — expiry date extraction from medicine label images.

Uses pytesseract + Pillow when available.
Gracefully returns empty suggestions if Tesseract is not installed
so the feature degrades to manual entry without breaking the workflow.

The frontend always requires user confirmation before saving an OCR result.
"""
import re
import base64
import io
from dataclasses import dataclass
from datetime import date
from typing import Optional

# Soft imports — OCR is optional in V2
try:
    from PIL import Image
    import pytesseract
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False


@dataclass
class OCRResult:
    available: bool
    raw_text: str
    candidates: list[str]    # human-readable date strings found
    best_date: Optional[date]
    confidence: float        # 0.0 – 1.0
    message: str


# ── Date patterns found on medicine cartons ──────────────────────────────────
_PATTERNS = [
    # EXP 10/2027  |  EXP: 10/27
    (re.compile(r"(?:EXP(?:IRY)?[\s:./]+)(\d{1,2})[./\- ](\d{2,4})", re.I), "mm/yyyy"),
    # 03/2028  |  03/28
    (re.compile(r"\b(\d{1,2})[./](\d{4})\b"), "mm/yyyy"),
    (re.compile(r"\b(\d{1,2})[./](\d{2})\b"), "mm/yy"),
    # OCT 2026  |  JUN 27
    (re.compile(r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{2,4})\b", re.I), "mon/y"),
    # 2027-10  |  2027/10
    (re.compile(r"\b(202\d)[./\- ](\d{1,2})\b"), "yyyy/mm"),
    # DD/MM/YYYY
    (re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b"), "dd/mm/yyyy"),
]

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _extract_dates(text: str) -> list[tuple[str, Optional[date]]]:
    """Return list of (display_string, date_object) tuples found in text."""
    found: list[tuple[str, Optional[date]]] = []
    seen: set[str] = set()
    upper = text.upper()

    for pattern, fmt in _PATTERNS:
        for m in pattern.finditer(upper):
            raw = m.group(0).strip()
            if raw in seen:
                continue
            seen.add(raw)
            parsed = _parse_match(m, fmt)
            found.append((raw, parsed))

    return found


def _parse_match(m: re.Match, fmt: str) -> Optional[date]:
    try:
        if fmt == "mm/yyyy":
            mm, yyyy = int(m.group(1)), int(m.group(2))
            if yyyy < 100:
                yyyy += 2000
            return date(yyyy, mm, 1)
        if fmt == "mm/yy":
            mm, yy = int(m.group(1)), int(m.group(2))
            return date(2000 + yy, mm, 1)
        if fmt == "mon/y":
            mon = _MONTHS.get(m.group(1).upper()[:3])
            if not mon:
                return None
            y = int(m.group(2))
            if y < 100:
                y += 2000
            return date(y, mon, 1)
        if fmt == "yyyy/mm":
            yyyy, mm = int(m.group(1)), int(m.group(2))
            return date(yyyy, mm, 1)
        if fmt == "dd/mm/yyyy":
            dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(yyyy, mm, dd)
    except (ValueError, TypeError):
        pass
    return None


def extract_expiry_from_image(image_b64: str) -> OCRResult:
    """
    Accept a base64-encoded JPEG/PNG, run Tesseract, extract expiry candidates.
    Returns an OCRResult with candidates ordered by confidence.
    User must confirm before any date is saved.
    """
    if not _OCR_AVAILABLE:
        return OCRResult(
            available=False,
            raw_text="",
            candidates=[],
            best_date=None,
            confidence=0.0,
            message=(
                "OCR is not available on this server. "
                "Install Tesseract and pytesseract to enable this feature."
            ),
        )

    # Decode image
    try:
        img_bytes = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(img_bytes))
    except Exception as e:
        return OCRResult(
            available=True, raw_text="", candidates=[],
            best_date=None, confidence=0.0,
            message=f"Could not decode image: {e}",
        )

    # Pre-process: convert to grayscale, resize if too small
    img = img.convert("L")
    w, h = img.size
    if w < 400:
        scale = 400 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Run Tesseract
    try:
        raw_text = pytesseract.image_to_string(
            img,
            config="--psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz/:.-() ",
        )
    except Exception as e:
        return OCRResult(
            available=True, raw_text="", candidates=[],
            best_date=None, confidence=0.0,
            message=f"OCR engine error: {e}",
        )

    matches = _extract_dates(raw_text)

    if not matches:
        return OCRResult(
            available=True,
            raw_text=raw_text[:500],
            candidates=[],
            best_date=None,
            confidence=0.0,
            message="No expiry date pattern found in image. Please enter manually.",
        )

    # Sort: prefer future dates (most likely to be a valid expiry)
    today = date.today()
    valid = [(label, d) for label, d in matches if d and d > today]
    ordered = valid if valid else matches

    best_label, best_date_val = ordered[0]
    confidence = min(1.0, 0.5 + 0.1 * len(valid))

    return OCRResult(
        available=True,
        raw_text=raw_text[:500],
        candidates=[lbl for lbl, _ in ordered[:5]],
        best_date=best_date_val,
        confidence=confidence,
        message=f"Found {len(ordered)} candidate date(s). Please confirm before saving.",
    )
