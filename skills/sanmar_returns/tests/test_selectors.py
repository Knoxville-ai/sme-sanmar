"""Selector-validation harness — run these locally against the live site.

These are **not** unit tests against a fixture; they are end-to-end
smoke tests that drive a real browser against sanmar.com. They exist
so you can verify each page object's selectors still match production
HTML before relying on the skill in an agent.

Usage:

.. code-block:: bash

    # Set credentials in your shell, then run an individual test:
    export SANMAR_TEST_USERNAME=...
    export SANMAR_TEST_PASSWORD=...
    export SANMAR_TEST_ORDER=SO-160940237   # an order in your history
    export SANMAR_TEST_STYLE=112PL          # a SKU in that order

    # Run with a visible browser so you can watch:
    SANMAR_RETURNS_HEADLESS=0 python -m pytest \
        skills/sanmar_returns/tests/test_selectors.py -s -v

Each test is independently invokable via ``pytest -k <name>``. They are
gated by the ``SMOKE`` environment variable so they don't run in CI by
default — set ``SMOKE=1`` to opt in.

Skipped tests print exactly which env var is missing.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SMOKE") != "1",
    reason="Live-site smoke tests; set SMOKE=1 to enable.",
)


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        pytest.skip(f"{name} env var not set")
    return val


@pytest.fixture(scope="module")
def authed_session():
    """Module-scoped authenticated browser session."""
    from skills.sanmar_returns.tools.return_tools import login
    from skills.sanmar_returns.tools.session import BrowserSession

    username = _require("SANMAR_TEST_USERNAME")
    password = _require("SANMAR_TEST_PASSWORD")

    result = login(username=username, password=password)
    assert result.success, result.observation
    yield BrowserSession.get()
    BrowserSession.reset()


def test_login_page_selectors(authed_session) -> None:
    """LoginPage selectors found the username/password/submit elements
    and the post-login welcome banner became visible."""
    # If the fixture set up cleanly we're already past login. Spot-check
    # the welcome element so a missing class change is obvious.
    page = authed_session.page
    page.goto("https://www.sanmar.com/", wait_until="domcontentloaded")
    welcome = page.locator("div.customer-info").get_by_text("Welcome,")
    welcome.wait_for(state="visible")


def test_orders_page_lists_rows(authed_session) -> None:
    """OrdersPage.list_orders returns at least one row with a populated
    order_number."""
    from skills.sanmar_returns.pages.orders_page import OrdersPage

    orders = OrdersPage(authed_session.page)
    orders.goto()
    rows = orders.list_orders(limit=10)
    assert rows, "expected at least one order row"
    assert all(r.order_number.startswith("SO-") for r in rows), [
        r.order_number for r in rows
    ]


def test_orders_page_finds_specific_row(authed_session) -> None:
    """find_row resolves to a single matching <tr> for a known SO."""
    from skills.sanmar_returns.pages.orders_page import OrdersPage

    order_number = _require("SANMAR_TEST_ORDER")
    orders = OrdersPage(authed_session.page)
    orders.goto()
    row = orders.find_row(order_number)
    row.wait_for(state="visible", timeout=5_000)
    assert row.locator("td.col-order-number strong").inner_text().strip() == order_number


def test_return_form_loads_via_deeplink(authed_session) -> None:
    """ReturnFormPage.goto navigates and at least one item row is visible."""
    from skills.sanmar_returns.pages.return_form_page import ReturnFormPage

    order_number = _require("SANMAR_TEST_ORDER")
    rf = ReturnFormPage(authed_session.page)
    rf.goto(order_number)
    rows = authed_session.page.locator("tr.order-history-details-items")
    assert rows.count() >= 1, "expected at least one return-form item row"


def test_return_form_finds_item_row(authed_session) -> None:
    """find_item_row matches a known style number in the loaded order."""
    from skills.sanmar_returns.pages.return_form_page import ReturnFormPage

    order_number = _require("SANMAR_TEST_ORDER")
    style_number = _require("SANMAR_TEST_STYLE")
    rf = ReturnFormPage(authed_session.page)
    rf.goto(order_number)
    row = rf.find_item_row(style_number)
    row.wait_for(state="visible", timeout=5_000)


def test_return_form_reason_select_options(authed_session) -> None:
    """The reason ``<select>`` exposes the documented option values."""
    from skills.sanmar_returns.pages.return_form_page import ReturnFormPage

    order_number = _require("SANMAR_TEST_ORDER")
    rf = ReturnFormPage(authed_session.page)
    rf.goto(order_number)
    first_row = authed_session.page.locator(
        "tr.order-history-details-items"
    ).first
    select = first_row.locator("td.column-select-reason select")
    values = select.locator("option").evaluate_all(
        "els => els.map(e => e.value)"
    )
    expected = {
        "",
        "SAMPLES",
        "UNWANTED",
        "ORDER_INCORRECT",
        "DEFECTIVE_DAMAGED",
        "INCORRECT_PRODUCT",
    }
    assert expected.issubset(set(values)), values
