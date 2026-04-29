"""Tests for sanmar_check_inventory request build + response parsing."""

from __future__ import annotations

import pytest

from skills.sanmar.sanmar_client import SanMarAPIError


_INVENTORY_OK = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns:getInventoryQtyForStyleColorSizeResponse xmlns:ns="http://webservice.integration.sanmar.com/">
      <return>
        <errorOccurred>false</errorOccurred>
        <listResponse>120</listResponse>
        <listResponse>88</listResponse>
        <listResponse>0</listResponse>
        <listResponse>240</listResponse>
        <listResponse>60</listResponse>
      </return>
    </ns:getInventoryQtyForStyleColorSizeResponse>
  </soap:Body>
</soap:Envelope>"""


_INVENTORY_ERROR = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns:getInventoryQtyForStyleColorSizeResponse xmlns:ns="http://webservice.integration.sanmar.com/">
      <return>
        <errorOccurred>true</errorOccurred>
        <message>Invalid style/color/size combination</message>
      </return>
    </ns:getInventoryQtyForStyleColorSizeResponse>
  </soap:Body>
</soap:Envelope>"""


def test_inventory_request_payload_contains_credentials_and_keys(make_client):
    client, session = make_client(_INVENTORY_OK)
    client.get_inventory(style="PC55", color="Black", size="L")

    assert len(session.calls) == 1
    sent = session.calls[0]
    assert sent["url"].endswith("SanMarWebServicePort")
    assert sent["headers"]["SOAPAction"] == "getInventoryQtyForStyleColorSize"
    body = sent["data"]
    assert "<arg0>123456</arg0>" in body  # customer_number
    assert "<arg1>test_user</arg1>" in body
    assert "<arg2>test_pass</arg2>" in body
    assert "<arg3>PC55</arg3>" in body
    assert "<arg4>Black</arg4>" in body
    assert "<arg5>L</arg5>" in body


def test_inventory_response_parses_warehouse_quantities(make_client):
    client, _ = make_client(_INVENTORY_OK)
    result = client.get_inventory(style="PC55", color="Black", size="L")

    assert result.warehouse_quantities == [120, 88, 0, 240, 60]
    # SanMar ships from a single warehouse: total_available is the max,
    # not the sum, of warehouse quantities.
    assert result.total_available == 240
    assert result.style == "PC55"
    assert result.color == "Black"
    assert result.size == "L"


def test_inventory_zero_when_no_quantities(make_client):
    empty = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body><return><errorOccurred>false</errorOccurred></return></soap:Body>
</soap:Envelope>"""
    client, _ = make_client(empty)
    result = client.get_inventory(style="X", color="Y", size="Z")
    assert result.warehouse_quantities == []
    assert result.total_available == 0


def test_inventory_error_raises_sanmar_api_error(make_client):
    client, _ = make_client(_INVENTORY_ERROR)
    with pytest.raises(SanMarAPIError) as exc_info:
        client.get_inventory(style="BAD", color="x", size="L")
    err = exc_info.value
    assert "Invalid style/color/size combination" in str(err)
    assert err.operation == "getInventoryQtyForStyleColorSize"
    assert err.retryable is False


def test_inventory_tool_returns_dict_payload(make_client, monkeypatch):
    """``sanmar_check_inventory`` should return a JSON-serializable dict."""

    from skills.sanmar import sanmar_tools as tools_mod

    client, _ = make_client(_INVENTORY_OK)
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: client)

    result = tools_mod.sanmar_check_inventory(
        style="PC55", color="Black", size="L", credentials=client.credentials
    )
    assert isinstance(result, dict)
    assert result["total_available"] == 240
    assert result["surface"] == "sanmar_webservice"
    assert result["operation"] == "getInventoryQtyForStyleColorSize"
