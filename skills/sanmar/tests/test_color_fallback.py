"""Mainframe-color auto-resolve fallback for inventory and pricing tools."""

from __future__ import annotations

import pytest

from skills.sanmar import sanmar_tools as tools_mod
from skills.sanmar.sanmar_client import SanMarAPIError
from skills.sanmar.schemas import InventoryResult, PricingItem, PricingResult


def _ok_inventory(style: str, color: str, size: str) -> InventoryResult:
    return InventoryResult(
        style=style,
        color=color,
        size=size,
        warehouse_quantities=[120, 88, 0, 240],
        total_available=240,
    )


def _empty_inventory(style: str, color: str, size: str) -> InventoryResult:
    return InventoryResult(
        style=style,
        color=color,
        size=size,
        warehouse_quantities=[],
        total_available=0,
    )


class _FakeClient:
    def __init__(self, inventory_responses=None, pricing_responses=None):
        self._inv = list(inventory_responses or [])
        self._prc = list(pricing_responses or [])
        self.inventory_calls: list[tuple[str, str, str]] = []
        self.pricing_calls: list[list[tuple[str, str, str]]] = []

    def get_inventory(self, *, style, color, size):
        self.inventory_calls.append((style, color, size))
        item = self._inv.pop(0)
        if isinstance(item, Exception):
            raise item
        return item(style, color, size) if callable(item) else item

    def get_pricing(self, *, lines):
        self.pricing_calls.append([(ln.style, ln.color, ln.size) for ln in lines])
        item = self._prc.pop(0)
        if isinstance(item, Exception):
            raise item
        return item(lines) if callable(item) else item


def test_inventory_falls_back_to_mainframe_color_on_api_error(monkeypatch):
    err = SanMarAPIError("Invalid style/color/size combination")
    err.operation = "getInventoryQtyForStyleColorSize"
    fake = _FakeClient(inventory_responses=[err, _ok_inventory])
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: fake)
    monkeypatch.setattr(
        tools_mod,
        "_resolve_mainframe_color_or_none",
        lambda style, color, size, ftp_credentials: "ATHHTHR",
    )

    result = tools_mod.sanmar_check_inventory(
        style="PC55", color="Athletic Heather", size="L"
    )
    assert result["total_available"] == 240
    assert result["color"] == "ATHHTHR"
    assert fake.inventory_calls == [
        ("PC55", "Athletic Heather", "L"),
        ("PC55", "ATHHTHR", "L"),
    ]


def test_inventory_falls_back_when_response_is_empty(monkeypatch):
    fake = _FakeClient(inventory_responses=[_empty_inventory, _ok_inventory])
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: fake)
    monkeypatch.setattr(
        tools_mod,
        "_resolve_mainframe_color_or_none",
        lambda style, color, size, ftp_credentials: "ATHHTHR",
    )

    result = tools_mod.sanmar_check_inventory(
        style="PC55", color="Athletic Heather", size="L"
    )
    assert result["total_available"] == 240
    assert len(fake.inventory_calls) == 2


def test_inventory_does_not_fall_back_when_disabled(monkeypatch):
    err = SanMarAPIError("Invalid style/color/size combination")
    err.operation = "getInventoryQtyForStyleColorSize"
    fake = _FakeClient(inventory_responses=[err])
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: fake)
    sentinel = {"called": False}

    def _should_not_be_called(*_a, **_k):
        sentinel["called"] = True
        return "ATHHTHR"

    monkeypatch.setattr(
        tools_mod, "_resolve_mainframe_color_or_none", _should_not_be_called
    )

    with pytest.raises(SanMarAPIError):
        tools_mod.sanmar_check_inventory(
            style="PC55", color="Athletic Heather", size="L", auto_resolve_color=False
        )
    assert sentinel["called"] is False


def test_pricing_retries_missing_lines_with_mainframe_color(monkeypatch):
    requested = [
        {"style": "PC55", "color": "Athletic Heather", "size": "L"},
        {"style": "PC55", "color": "Black", "size": "L"},
    ]
    first = PricingResult(
        items=[
            PricingItem(
                style="PC55", color="Black", size="L", piece_price=7.52, my_price=6.75
            )
        ]
    )
    second = PricingResult(
        items=[
            PricingItem(
                style="PC55",
                color="ATHHTHR",
                size="L",
                piece_price=7.52,
                my_price=6.75,
            )
        ]
    )
    fake = _FakeClient(pricing_responses=[first, second])
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: fake)
    monkeypatch.setattr(
        tools_mod,
        "_resolve_mainframe_color_or_none",
        lambda style, color, size, ftp_credentials: (
            "ATHHTHR" if color == "Athletic Heather" else None
        ),
    )

    result = tools_mod.sanmar_get_pricing(lines=requested)
    items = result["items"]
    by_color = {it["color"]: it for it in items}
    assert "Black" in by_color
    assert "ATHHTHR" in by_color
    # Two pricing calls: original then retry containing only the missing line
    assert len(fake.pricing_calls) == 2
    assert fake.pricing_calls[1] == [("PC55", "ATHHTHR", "L")]


def test_pricing_no_retry_when_all_lines_returned(monkeypatch):
    requested = [{"style": "PC55", "color": "Black", "size": "L"}]
    single = PricingResult(
        items=[PricingItem(style="PC55", color="Black", size="L", piece_price=7.52)]
    )
    fake = _FakeClient(pricing_responses=[single])
    monkeypatch.setattr(tools_mod, "_client", lambda credentials: fake)

    sentinel = {"resolved": 0}

    def resolver(*_a, **_k):
        sentinel["resolved"] += 1
        return None

    monkeypatch.setattr(tools_mod, "_resolve_mainframe_color_or_none", resolver)

    tools_mod.sanmar_get_pricing(lines=requested)
    assert len(fake.pricing_calls) == 1
    assert sentinel["resolved"] == 0
