"""QRIS (EMVCo MPM) payload surgery: read a static merchant QR and stamp a per-invoice amount.

A static QRIS carries no amount (tag 54 absent) and is reusable; to bill a specific top-up you build
a *dynamic* payload: set the point-of-initiation method to dynamic (tag 01 = ``12``), insert
``54`` with the amount, and recompute the CRC16-CCITT-FALSE trailer (tag 63).

Everything here is pure stdlib except :func:`render_png`/:func:`render_svg`, which need ``segno``
(the dashboard degrades to a link when it is unavailable).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

MANDATORY_PREFIX = "000201"
CCY_IDR = "360"


class QrisError(ValueError):
    """Raised when a payload is not a usable EMVCo/QRIS string."""


def crc16_ccitt_false(data: str) -> str:
    """CRC-16/CCITT-FALSE as uppercase hex — the EMVCo tag-63 checksum."""
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


@dataclass(frozen=True)
class Tlv:
    tag: str
    value: str

    def encode(self) -> str:
        if len(self.value) > 99:  # EMVCo's 2-digit length field cannot express more
            raise QrisError(f"tag {self.tag} value is too long ({len(self.value)} chars)")
        return f"{self.tag}{len(self.value):02d}{self.value}"


def parse_tlv(payload: str) -> list[Tlv]:
    """Ordered tag/value pairs; raises on a malformed or over-long payload."""
    payload = (payload or "").strip()
    if not payload:
        raise QrisError("empty QRIS payload")
    items: list[Tlv] = []
    index = 0
    while index < len(payload):
        if index + 4 > len(payload):
            raise QrisError(f"truncated TLV header at offset {index}")
        tag = payload[index : index + 2]
        length_field = payload[index + 2 : index + 4]
        if not tag.isdigit() or not length_field.isdigit():
            raise QrisError(f"non-numeric TLV header {payload[index:index + 4]!r} at offset {index}")
        length = int(length_field)
        start = index + 4
        end = start + length
        if end > len(payload):
            raise QrisError(f"tag {tag} claims {length} chars but the payload ends early")
        items.append(Tlv(tag, payload[start:end]))
        index = end
    return items


def validate(payload: str) -> bool:
    """True when the payload parses, starts like EMVCo, and its tag-63 CRC matches."""
    try:
        items = parse_tlv(payload)
    except QrisError:
        return False
    if not payload.strip().startswith(MANDATORY_PREFIX):
        return False
    crc_items = [item for item in items if item.tag == "63"]
    if len(crc_items) != 1:
        return False
    body = payload.strip()[: payload.strip().rfind("6304") + 4]
    return crc16_ccitt_false(body).upper() == crc_items[0].value.upper()


def field(payload: str, tag: str, default: str = "") -> str:
    for item in parse_tlv(payload):
        if item.tag == tag:
            return item.value
    return default


def merchant_name(payload: str) -> str:
    return field(payload, "59")


def currency(payload: str) -> str:
    return field(payload, "53")


def is_static(payload: str) -> bool:
    """Tag 01: ``11`` static (reusable, no amount), ``12`` dynamic (single use)."""
    return field(payload, "01", "11") in {"", "11"}


def amount_of(payload: str) -> Optional[str]:
    value = field(payload, "54")
    return value or None


def with_amount(payload: str, amount_idr: int, *, dynamic: bool = True) -> str:
    """Return a copy of ``payload`` carrying ``amount_idr`` as tag 54, CRC recomputed.

    Tag order follows EMVCo: 54 sits right after 53 (currency) and before 58 (country). An existing
    amount is replaced, never duplicated, and the trailing CRC is always rebuilt from scratch.
    """
    if amount_idr <= 0:
        raise QrisError("amount must be a positive number of rupiah")
    items = parse_tlv(payload)
    if not any(item.tag == "53" for item in items):
        raise QrisError("payload has no currency (tag 53); refusing to stamp an amount")

    amount_text = str(int(amount_idr))
    rebuilt: list[Tlv] = []
    inserted = False
    for item in items:
        if item.tag == "63":  # CRC is appended last, always
            continue
        if item.tag == "54":  # drop any previous amount
            continue
        if item.tag == "01" and dynamic:
            rebuilt.append(Tlv("01", "12"))
            continue
        rebuilt.append(item)
        if item.tag == "53" and not inserted:
            rebuilt.append(Tlv("54", amount_text))
            inserted = True
    if not inserted:  # no currency tag seen (already rejected above) — defensive
        rebuilt.append(Tlv("54", amount_text))

    body = "".join(item.encode() for item in rebuilt) + "6304"
    return body + crc16_ccitt_false(body)


def build_from_parts(
    merchant_account: Iterable[Tlv],
    *,
    merchant_name_value: str,
    city: str,
    postal_code: str = "",
    mcc: str = "5734",
) -> str:
    """Assemble a payload from scratch (used by tests and by operators without an issuer QR)."""
    items: list[Tlv] = [Tlv("00", "01"), Tlv("01", "11")]
    items.extend(merchant_account)
    items.append(Tlv("52", mcc))
    items.append(Tlv("53", CCY_IDR))
    items.append(Tlv("58", "ID"))
    items.append(Tlv("59", merchant_name_value[:25]))
    items.append(Tlv("60", city[:15]))
    if postal_code:
        items.append(Tlv("61", postal_code[:10]))
    body = "".join(item.encode() for item in items) + "6304"
    return body + crc16_ccitt_false(body)


def render_png(payload: str, scale: int = 8, border: int = 2) -> bytes:
    """PNG bytes for the payload (requires ``segno``)."""
    import io

    try:
        import segno
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise QrisError("PNG rendering needs the 'segno' package") from exc
    buffer = io.BytesIO()
    segno.make(payload, error="m").save(buffer, kind="png", scale=scale, border=border)
    return buffer.getvalue()


def render_svg(payload: str, scale: int = 8, border: int = 2) -> str:
    """SVG markup for the payload (requires ``segno``)."""
    try:
        import segno
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise QrisError("SVG rendering needs the 'segno' package") from exc
    return segno.make(payload, error="m").svg_inline(scale=scale, border=border)


def describe(payload: str) -> dict:
    """Human-facing summary of a merchant payload (never includes the raw merchant account data)."""
    items = parse_tlv(payload)
    return {
        "valid": validate(payload),
        "static": is_static(payload),
        "amount": amount_of(payload),
        "merchant": merchant_name(payload),
        "city": field(payload, "60"),
        "currency": currency(payload),
        "tags": [item.tag for item in items],
        "crc": field(payload, "63"),
    }


def load_static(source: str) -> str:
    """Resolve a static QRIS payload from a raw string, a text file, or a QR image.

    Images need ``opencv-python-headless`` (``cv2.QRCodeDetector``); that keeps the common case
    zero-dependency and the "scan my screenshot" case one optional install away.
    """
    source = (source or "").strip()
    if not source:
        raise QrisError("no QRIS source given")
    path = Path(source)
    if path.exists():
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            try:
                import cv2
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise QrisError("reading a QR image needs 'opencv-python-headless'") from exc
            image = cv2.imread(str(path))
            if image is None:
                raise QrisError(f"cannot read image {path}")
            data, _points, _ = cv2.QRCodeDetector().detectAndDecode(image)
            if not data:
                raise QrisError(f"no QR code found in {path}")
            return _checked(data)
        return _checked(path.read_text(encoding="utf-8-sig"))
    return _checked(source)


def _checked(payload: str) -> str:
    payload = payload.strip()
    if not validate(payload):
        raise QrisError("payload is not a valid QRIS string (bad TLV or CRC)")
    return payload


__all__ = [
    "QrisError",
    "Tlv",
    "crc16_ccitt_false",
    "parse_tlv",
    "validate",
    "field",
    "merchant_name",
    "currency",
    "is_static",
    "amount_of",
    "with_amount",
    "build_from_parts",
    "render_png",
    "render_svg",
    "describe",
    "load_static",
]
