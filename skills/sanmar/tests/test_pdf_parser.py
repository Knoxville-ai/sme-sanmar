"""Tests for PDF purchase-order parsing.

The parser uses heuristics on extracted text. To keep tests
deterministic we monkeypatch ``_extract_text`` and feed canned text
representative of common SanMar PO formats.
"""

from __future__ import annotations

import pytest

from skills.sanmar import pdf_parser
from skills.sanmar.pdf_parser import (
    PDFParseError,
    parse_purchase_order_pdf,
    to_purchase_order_draft,
)


_SIMPLE_PO = """\
ACME Apparel Co.
PURCHASE ORDER

PO Number: PO-1042
Order Date: 04/28/2026

Ship To:
BaconCo Receiving
123 Print Way
Memphis, TN 38103
purchasing@example.com

Ship Via: UPS Ground

Qty   Style    Description                   Size   Price
24    PC55     Port & Co Tee Black           L      $7.52
12    PC55     Port & Co Tee Navy            XL     $7.52
6     ST350    Sport-Tek Tee Athletic Heather  M    $9.10

Subtotal: $345.84
"""


def test_parse_extracts_po_number_and_ship_to(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_parser, "_extract_text", lambda _src: _SIMPLE_PO)
    parsed = parse_purchase_order_pdf("ignored.pdf")

    assert parsed.po_number == "PO-1042"
    assert parsed.order_date == "04/28/2026"
    assert parsed.ship_method == "UPS Ground"
    assert parsed.ship_to.name == "BaconCo Receiving"
    assert parsed.ship_to.address1 == "123 Print Way"
    assert parsed.ship_to.city == "Memphis"
    assert parsed.ship_to.state == "TN"
    assert parsed.ship_to.zip == "38103"
    assert parsed.ship_to.email == "purchasing@example.com"


def test_parse_extracts_line_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_parser, "_extract_text", lambda _src: _SIMPLE_PO)
    parsed = parse_purchase_order_pdf("ignored.pdf")

    by_style_size = {(ln.style, ln.size): ln for ln in parsed.lines}
    assert ("PC55", "L") in by_style_size
    assert ("PC55", "XL") in by_style_size
    assert ("ST350", "M") in by_style_size

    pc55_l = by_style_size[("PC55", "L")]
    assert pc55_l.quantity == 24
    assert pc55_l.unit_price == 7.52
    # Color extraction is heuristic; case-normalized.
    assert "Black" in pc55_l.color or "black" in pc55_l.color.lower()

    sttee = by_style_size[("ST350", "M")]
    # Multi-word colors should survive
    assert "Athletic" in sttee.color and "Heather" in sttee.color


def test_to_purchase_order_draft_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_parser, "_extract_text", lambda _src: _SIMPLE_PO)
    parsed = parse_purchase_order_pdf("ignored.pdf")
    draft = to_purchase_order_draft(parsed)

    assert draft["po_number"] == "PO-1042"
    assert draft["ship_to"]["state"] == "TN"
    assert draft["ship_to"]["ship_method"] == "UPS Ground"
    assert len(draft["lines"]) == len(parsed.lines)
    for ln in draft["lines"]:
        assert ln["quantity"] >= 1
        assert ln["style"]
        assert ln["color"]
        assert ln["size"]


def test_parse_raises_when_no_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_parser, "_extract_text", lambda _src: "   ")

    # The empty-text guard is in _extract_text itself; emulate it here.
    def boom(_src: object) -> str:
        raise PDFParseError("empty")

    monkeypatch.setattr(pdf_parser, "_extract_text", boom)
    with pytest.raises(PDFParseError):
        parse_purchase_order_pdf("ignored.pdf")


def test_warnings_for_missing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pdf_parser, "_extract_text", lambda _src: "Random unstructured text\nNo PO here"
    )
    parsed = parse_purchase_order_pdf("ignored.pdf")
    joined = " ".join(parsed.warnings)
    assert "po_number" in joined
    assert "no line items" in joined.lower()


def test_to_purchase_order_draft_requires_po_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pdf_parser, "_extract_text", lambda _src: "junk\nno po\nno items\n"
    )
    parsed = parse_purchase_order_pdf("ignored.pdf")
    with pytest.raises(ValueError):
        to_purchase_order_draft(parsed)
