"""Tests for sanmar_get_pricing payload + response parsing."""

from __future__ import annotations

import pytest

from skills.sanmar.sanmar_client import SanMarAPIError
from skills.sanmar.schemas import PricingLine


_PRICING_OK = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns:getPricingResponse xmlns:ns="http://impl.webservice.integration.sanmar.com/">
      <return>
        <errorOccurred>false</errorOccurred>
        <listResponse>
          <style>PC55</style>
          <color>Black</color>
          <size>L</size>
          <inventoryKey>12345</inventoryKey>
          <sizeIndex>3</sizeIndex>
          <piecePrice>7.52</piecePrice>
          <dozenPrice>7.02</dozenPrice>
          <casePrice>6.52</casePrice>
          <myPrice>6.75</myPrice>
        </listResponse>
        <listResponse>
          <style>PC55</style>
          <color>Navy</color>
          <size>XL</size>
          <inventoryKey>12346</inventoryKey>
          <sizeIndex>4</sizeIndex>
          <piecePrice>7.52</piecePrice>
          <dozenPrice>7.02</dozenPrice>
          <casePrice>6.52</casePrice>
          <myPrice>6.75</myPrice>
        </listResponse>
      </return>
    </ns:getPricingResponse>
  </soap:Body>
</soap:Envelope>"""


_PRICING_ERROR = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body><return>
    <errorOccurred>true</errorOccurred>
    <message>Authentication failed</message>
  </return></soap:Body>
</soap:Envelope>"""


def test_pricing_request_includes_one_arg0_per_line(make_client):
    client, session = make_client(_PRICING_OK)
    client.get_pricing(
        lines=[
            PricingLine(style="PC55", color="Black", size="L"),
            PricingLine(style="PC55", color="Navy", size="XL"),
        ]
    )

    body = session.calls[0]["data"]
    assert body.count("<arg0>") == 2
    assert "<style>PC55</style>" in body
    assert "<color>Black</color>" in body
    assert "<color>Navy</color>" in body
    assert "<size>L</size>" in body
    assert "<size>XL</size>" in body
    assert "<sanMarCustomerNumber>123456</sanMarCustomerNumber>" in body
    assert "<sanMarUserName>test_user</sanMarUserName>" in body
    assert "<sanMarUserPassword>test_pass</sanMarUserPassword>" in body
    assert session.calls[0]["headers"]["SOAPAction"] == "getPricing"


def test_pricing_response_parses_all_fields(make_client):
    client, _ = make_client(_PRICING_OK)
    result = client.get_pricing(
        lines=[PricingLine(style="PC55", color="Black", size="L")]
    )
    assert len(result.items) == 2

    item = result.items[0]
    assert item.style == "PC55"
    assert item.color == "Black"
    assert item.size == "L"
    assert item.inventory_key == "12345"
    assert item.size_index == "3"
    assert item.piece_price == 7.52
    assert item.dozen_price == 7.02
    assert item.case_price == 6.52
    assert item.my_price == 6.75


def test_empty_pricing_lines_returns_empty_result_without_call(make_client):
    client, session = make_client("")
    result = client.get_pricing(lines=[])
    assert result.items == []
    assert session.calls == []  # short-circuited


def test_pricing_auth_error(make_client):
    client, _ = make_client(_PRICING_ERROR)
    with pytest.raises(SanMarAPIError) as exc_info:
        client.get_pricing(
            lines=[PricingLine(style="PC55", color="Black", size="L")]
        )
    assert "Authentication failed" in str(exc_info.value)
    assert exc_info.value.operation == "getPricing"


def test_pricing_tool_layer_serializes(make_client, monkeypatch):
    from skills.sanmar import sanmar_tools as tools_mod

    client, _ = make_client(_PRICING_OK)
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: client)

    result = tools_mod.sanmar_get_pricing(
        lines=[
            {"style": "PC55", "color": "Black", "size": "L"},
            {"style": "PC55", "color": "Navy", "size": "XL"},
        ],
        credentials=client.credentials,
    )
    assert isinstance(result, dict)
    assert len(result["items"]) == 2
    assert result["items"][0]["my_price"] == 6.75
    assert result["operation"] == "getPricing"
