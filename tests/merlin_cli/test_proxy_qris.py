"""QRIS payload tests: CRC vector, TLV parsing, amount stamping, rendering."""

from __future__ import annotations

import pytest

from merlin_cli.proxy import qris

MERCHANT_ACCOUNT = [
    qris.Tlv("26", "0016ID.CO.EXAMPLE.WWW01189360000000000000000215ID1024000000001"),
    qris.Tlv("51", "0016ID.CO.EXAMPLE.WWW01189360000000000000000215ID1024000000002"),
]


def _static(**kwargs) -> str:
    return qris.build_from_parts(
        MERCHANT_ACCOUNT,
        merchant_name_value="EPINOIA HORIZON, Komputer",
        city="Tangerang Selat",
        postal_code="15315",
        **kwargs,
    )


# -- checksum ------------------------------------------------------------------------------
def test_crc_matches_the_published_check_value() -> None:
    # CRC-16/CCITT-FALSE check vector for the ASCII string "123456789".
    assert qris.crc16_ccitt_false("123456789") == "29B1"


def test_payload_crc_round_trips() -> None:
    payload = _static()
    assert qris.validate(payload) is True


def test_validate_rejects_a_broken_crc() -> None:
    payload = _static()
    tampered = payload[:-4] + "0000"
    assert qris.validate(tampered) is False


def test_validate_rejects_garbage() -> None:
    assert qris.validate("") is False
    assert qris.validate("not-a-qris") is False
    assert qris.validate("000201" + "99" + "x") is False


# -- structure -----------------------------------------------------------------------------
def test_static_payload_reports_merchant_and_currency() -> None:
    payload = _static()
    assert qris.merchant_name(payload) == "EPINOIA HORIZON, Komputer"
    assert qris.currency(payload) == qris.CCY_IDR
    assert qris.is_static(payload) is True
    assert qris.amount_of(payload) is None


def test_parse_tlv_keeps_order() -> None:
    tags = [tlv.tag for tlv in qris.parse_tlv(_static())]
    assert tags[:5] == ["00", "01", "26", "51", "52"]
    assert tags[-1] == "63"


# -- amount stamping -----------------------------------------------------------------------
def test_with_amount_inserts_tag_54_and_flips_to_dynamic() -> None:
    dynamic = qris.with_amount(_static(), 25_000)
    assert qris.validate(dynamic) is True
    assert qris.amount_of(dynamic) == "25000"
    assert qris.is_static(dynamic) is False
    assert qris.field(dynamic, "01") == "12"
    tags = [tlv.tag for tlv in qris.parse_tlv(dynamic)]
    assert tags.count("54") == 1
    assert tags.index("54") == tags.index("53") + 1  # EMVCo ordering
    assert tags.index("58") == tags.index("54") + 1


def test_restamping_replaces_the_amount_instead_of_duplicating() -> None:
    once = qris.with_amount(_static(), 10_000)
    twice = qris.with_amount(once, 30_000)
    assert qris.amount_of(twice) == "30000"
    assert [tlv.tag for tlv in qris.parse_tlv(twice)].count("54") == 1
    assert qris.validate(twice) is True


def test_amount_must_be_positive() -> None:
    with pytest.raises(qris.QrisError):
        qris.with_amount(_static(), 0)


def test_payload_without_currency_is_refused() -> None:
    body = "000201" + "010211" + "5802ID" + "5904TEST" + "6004CITY" + "6304"  # no tag 53
    bare = body + qris.crc16_ccitt_false(body)
    assert qris.validate(bare) is True  # structurally fine, just unusable for an amount
    with pytest.raises(qris.QrisError, match="currency"):
        qris.with_amount(bare, 1_000)


# -- rendering & loading -------------------------------------------------------------------
def test_render_png_returns_a_png() -> None:
    png = qris.render_png(qris.with_amount(_static(), 5_000))
    assert png.startswith(b"\x89PNG")


def test_render_svg_returns_svg_markup() -> None:
    svg = qris.render_svg(qris.with_amount(_static(), 5_000))
    assert "<svg" in svg.lower()


def test_load_static_accepts_a_raw_payload_and_a_file(tmp_path) -> None:
    payload = _static()
    assert qris.load_static(payload) == payload
    path = tmp_path / "qris.txt"
    path.write_text(payload + "\n", encoding="utf-8")
    assert qris.load_static(str(path)) == payload


def test_load_static_rejects_an_invalid_payload() -> None:
    with pytest.raises(qris.QrisError):
        qris.load_static("00020101")


def test_describe_summarises_without_leaking_account_data() -> None:
    info = qris.describe(_static())
    assert info["merchant"].startswith("EPINOIA")
    assert info["valid"] is True and info["static"] is True
    assert "26" in info["tags"] and "63" in info["tags"]
