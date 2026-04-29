"""Tests for the purchase-order envelope, validate-cart, and submit flows."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from skills.sanmar.sanmar_client import SanMarAPIError
from skills.sanmar.schemas import (
    PurchaseOrderDraft,
    PurchaseOrderLine,
    ShipTo,
)


def _draft() -> PurchaseOrderDraft:
    return PurchaseOrderDraft(
        po_number="PO-1042",
        ship_to=ShipTo(
            name="BaconCo Receiving",
            address1="123 Print Way",
            city="Memphis",
            state="TN",
            zip="38103",
            email="purchasing@example.com",
            ship_method="UPS",
        ),
        lines=[
            PurchaseOrderLine(
                style="PC55", color="Black", size="L", quantity=24,
                inventory_key="12345", size_index="3",
            ),
            PurchaseOrderLine(
                style="PC55", color="Navy", size="XL", quantity=12,
                inventory_key="12346", size_index="4",
            ),
        ],
    )


_PRE_SUBMIT_OK = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <return>
      <errorOccurred>false</errorOccurred>
      <webServicePoDetailList>
        <style>PC55</style><color>Black</color><size>L</size>
        <errorOccured>false</errorOccured>
      </webServicePoDetailList>
      <webServicePoDetailList>
        <style>PC55</style><color>Navy</color><size>XL</size>
        <errorOccured>false</errorOccured>
      </webServicePoDetailList>
    </return>
  </soap:Body>
</soap:Envelope>"""


_PRE_SUBMIT_LINE_ERROR = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <return>
      <errorOccurred>false</errorOccurred>
      <webServicePoDetailList>
        <style>PC55</style><color>Black</color><size>L</size>
        <errorOccured>false</errorOccured>
      </webServicePoDetailList>
      <webServicePoDetailList>
        <style>PC55</style><color>Navy</color><size>XL</size>
        <errorOccured>true</errorOccured>
        <message>Insufficient inventory in any warehouse</message>
      </webServicePoDetailList>
    </return>
  </soap:Body>
</soap:Envelope>"""


_SUBMIT_OK = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <return>
      <errorOccurred>false</errorOccurred>
      <poNum>PO-1042</poNum>
    </return>
  </soap:Body>
</soap:Envelope>"""


_SUBMIT_TOP_ERROR = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <return>
      <errorOccurred>true</errorOccurred>
      <message>Duplicate PO number</message>
    </return>
  </soap:Body>
</soap:Envelope>"""


def test_pre_submit_envelope_omits_inventory_keys(make_client):
    client, _ = make_client("")
    payload = client.build_po_envelope(_draft(), pre_submit=True).decode("utf-8")

    root = ET.fromstring(payload)
    # The pre-submit op tag is getPreSubmitInfo, not submitPO.
    assert root.find(".//{http://webservice.integration.sanmar.com/}getPreSubmitInfo") is not None
    assert root.find(".//{http://webservice.integration.sanmar.com/}submitPO") is None

    # Pre-submit should not include inventoryKey/sizeIndex per line
    assert "<inventoryKey>" not in payload
    assert "<sizeIndex>" not in payload

    details = root.findall(".//webServicePoDetailList")
    assert len(details) == 2
    assert details[0].find("style").text == "PC55"
    assert details[0].find("quantity").text == "24"


def test_submit_envelope_includes_inventory_keys_and_ship_fields(make_client):
    client, _ = make_client("")
    payload = client.build_po_envelope(_draft(), pre_submit=False).decode("utf-8")

    root = ET.fromstring(payload)
    assert root.find(".//{http://webservice.integration.sanmar.com/}submitPO") is not None

    arg0 = root.find(".//arg0")
    assert arg0.find("poNum").text == "PO-1042"
    assert arg0.find("shipTo").text == "BaconCo Receiving"
    assert arg0.find("shipAddress1").text == "123 Print Way"
    assert arg0.find("shipCity").text == "Memphis"
    assert arg0.find("shipState").text == "TN"
    assert arg0.find("shipZip").text == "38103"
    assert arg0.find("shipMethod").text == "UPS"
    assert arg0.find("residence").text == "N"

    details = root.findall(".//webServicePoDetailList")
    assert details[0].find("inventoryKey").text == "12345"
    assert details[0].find("sizeIndex").text == "3"
    assert details[0].find("quantity").text == "24"

    # Auth fields go in arg1
    arg1 = root.find(".//arg1")
    assert arg1.find("sanMarCustomerNumber").text == "123456"
    assert arg1.find("sanMarUserName").text == "test_user"
    assert arg1.find("sanMarUserPassword").text == "test_pass"


def test_pre_submit_ok_response(make_client):
    client, session = make_client(_PRE_SUBMIT_OK)
    result = client.pre_submit_po(_draft())
    assert result.ok is True
    assert result.errored_lines == []
    assert session.calls[0]["headers"]["SOAPAction"] == "getPreSubmitInfo"


def test_pre_submit_per_line_error(make_client):
    client, _ = make_client(_PRE_SUBMIT_LINE_ERROR)
    result = client.pre_submit_po(_draft())
    assert result.ok is False
    assert len(result.errored_lines) == 1
    assert result.errored_lines[0].color == "Navy"
    assert "Insufficient inventory" in result.errored_lines[0].message


def test_submit_ok_returns_sanmar_reference(make_client):
    client, session = make_client(_SUBMIT_OK)
    result = client.submit_po(_draft())
    assert result.status == "submitted"
    assert result.po_number == "PO-1042"
    assert result.sanmar_reference == "PO-1042"
    assert session.calls[0]["headers"]["SOAPAction"] == "submitPO"


def test_submit_top_level_error_raises(make_client):
    client, _ = make_client(_SUBMIT_TOP_ERROR)
    with pytest.raises(SanMarAPIError) as exc_info:
        client.submit_po(_draft())
    assert "Duplicate PO number" in str(exc_info.value)
    assert exc_info.value.operation == "submitPO"


def test_create_po_dry_run_does_not_call_session(make_client, monkeypatch):
    """confirm=False must NOT post to SanMar."""

    from skills.sanmar import sanmar_tools as tools_mod

    client, session = make_client(_SUBMIT_OK)
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: client)

    draft_dict = {
        "po_number": "PO-1042",
        "ship_to": {
            "name": "BaconCo", "address1": "123 Print Way",
            "city": "Memphis", "state": "TN", "zip": "38103",
        },
        "lines": [
            {"style": "PC55", "color": "Black", "size": "L", "quantity": 24,
             "inventory_key": "12345", "size_index": "3"},
        ],
    }

    result = tools_mod.sanmar_create_purchase_order(
        purchase_order=draft_dict, confirm=False, credentials=client.credentials
    )

    assert result["status"] == "dry_run"
    assert result["po_number"] == "PO-1042"
    assert "<submitPO" not in result["raw_payload"]  # uses ns prefix
    assert "submitPO" in result["raw_payload"]
    assert session.calls == []  # no live call


def test_create_po_confirmed_posts_envelope(make_client, monkeypatch):
    from skills.sanmar import sanmar_tools as tools_mod

    client, session = make_client(_SUBMIT_OK)
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: client)

    draft_dict = {
        "po_number": "PO-1042",
        "ship_to": {
            "name": "BaconCo", "address1": "123 Print Way",
            "city": "Memphis", "state": "TN", "zip": "38103",
        },
        "lines": [
            {"style": "PC55", "color": "Black", "size": "L", "quantity": 24,
             "inventory_key": "12345", "size_index": "3"},
        ],
    }

    result = tools_mod.sanmar_create_purchase_order(
        purchase_order=draft_dict, confirm=True, credentials=client.credentials
    )

    assert result["status"] == "submitted"
    assert result["sanmar_reference"] == "PO-1042"
    assert len(session.calls) == 1
    assert session.calls[0]["headers"]["SOAPAction"] == "submitPO"
