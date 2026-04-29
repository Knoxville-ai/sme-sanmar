"""Tests for order-status, tracking, carrier normalization, and the cancel stub."""

from __future__ import annotations

import pytest

from skills.sanmar.sanmar_client import normalize_carrier


_SHIPMENT_OK = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns2:GetOrderShipmentNotificationResponse
        xmlns:ns2="http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/">
      <ns2:salesOrderNumber>9876543</ns2:salesOrderNumber>
      <ns2:Shipment>
        <ns2:Package>
          <ns2:trackingNumber>1Z999AA10123456784</ns2:trackingNumber>
          <ns2:carrier>UPS Ground</ns2:carrier>
        </ns2:Package>
        <ns2:Package>
          <ns2:trackingNumber>9622012345678901234567</ns2:trackingNumber>
          <ns2:carrier>FedEx Ground</ns2:carrier>
        </ns2:Package>
      </ns2:Shipment>
    </ns2:GetOrderShipmentNotificationResponse>
  </soap:Body>
</soap:Envelope>"""


_SHIPMENT_SERVICE_ERROR = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns2:GetOrderShipmentNotificationResponse
        xmlns:ns2="http://www.promostandards.org/WSDL/OrderShipmentNotificationService/1.0.0/">
      <ns2:errorMessage>No shipment notification found for reference</ns2:errorMessage>
    </ns2:GetOrderShipmentNotificationResponse>
  </soap:Body>
</soap:Envelope>"""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("UPS Ground", "ups"),
        ("FedEx Ground", "fedex"),
        ("Fed Ex Express", "fedex"),
        ("USPS First-Class", "usps"),
        ("United States Postal Service", "usps"),
        ("DHL", None),
        (None, None),
        ("", None),
    ],
)
def test_normalize_carrier(raw, expected):
    assert normalize_carrier(raw) == expected


def test_get_tracking_parses_packages(make_client):
    client, session = make_client(_SHIPMENT_OK)
    result = client.get_tracking("PO-1042")

    assert result.po_number == "PO-1042"
    assert len(result.shipments) == 2
    assert result.shipments[0].tracking_number == "1Z999AA10123456784"
    assert result.shipments[0].carrier == "ups"
    assert result.shipments[1].tracking_number == "9622012345678901234567"
    assert result.shipments[1].carrier == "fedex"

    sent = session.calls[0]
    assert sent["url"].endswith("OrderShipmentNotificationServiceBinding")
    body = sent["data"]
    assert "<shar:id>test_user</shar:id>" in body
    assert "<shar:password>test_pass</shar:password>" in body
    assert "<ns:referenceNumber>PO-1042</ns:referenceNumber>" in body


def test_get_order_status_extracts_sales_order_number(make_client):
    client, _ = make_client(_SHIPMENT_OK)
    result = client.get_order_status("PO-1042")
    assert result.sanmar_order_number == "9876543"
    assert result.shipment_count == 2
    assert result.status == "shipped"


def test_service_error_yields_empty_results(make_client):
    client, _ = make_client(_SHIPMENT_SERVICE_ERROR)

    tracking = client.get_tracking("PO-NOT-FOUND")
    assert tracking.shipments == []

    status = client.get_order_status("PO-NOT-FOUND")
    assert status.sanmar_order_number is None
    assert status.shipment_count == 0
    assert status.status == "unknown"


def test_cancel_order_stub_returns_not_implemented():
    from skills.sanmar import sanmar_tools as tools_mod

    result = tools_mod.sanmar_cancel_order(
        po_number="PO-1042", reason="duplicate", confirm=True
    )
    assert result["status"] == "not_implemented"
    assert result["po_number"] == "PO-1042"
    assert "customer service" in result["message"].lower()


def test_tool_layer_check_order_status(make_client, monkeypatch):
    from skills.sanmar import sanmar_tools as tools_mod

    client, _ = make_client(_SHIPMENT_OK)
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: client)

    result = tools_mod.sanmar_check_order_status(
        po_number="PO-1042", credentials=client.credentials
    )
    assert isinstance(result, dict)
    assert result["sanmar_order_number"] == "9876543"
    assert result["shipment_count"] == 2
    assert result["status"] == "shipped"
    assert result["surface"] == "sanmar_promostandards"
