"""OrdersPage — sanmar.com /mysanmar/order-history.

Each order is a ``<tr class="orders-separator">`` containing:

* ``td.col-order-number > span > span > a > strong`` — text is the
  SO-XXXXX number.
* ``td.col-purchase-order > span`` — PO number (customer-side).
* ``td.col-order-date`` — ``MM/DD/YY`` text.
* The "Sanmar Shipped" / status tooltip text inside the first cell.
* A return-icon ``<a>`` whose attribute ``data-bs-content="Return Items"``
  uniquely identifies it within the row.

The id ``returnLinkId-{N}`` on the return link uses a row-index
suffix that is **not** stable across reloads or filter changes, so
this page object never targets it by id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from skills.sanmar_returns.pages.base import BasePage

ORDERS_URL = "https://www.sanmar.com/mysanmar/order-history"


@dataclass
class OrderRow:
    order_number: str
    po_number: str | None
    date: str | None
    status: str | None


class OrdersPage(BasePage):
    def goto(self) -> None:
        self._log("orders.goto", url=ORDERS_URL)
        self.page.goto(ORDERS_URL, wait_until="domcontentloaded")
        self.page.locator("tr.orders-separator").first.wait_for(state="visible")

    def list_orders(self, limit: int = 25) -> list[OrderRow]:
        """Read the visible rows on the current order-history page.

        Returns at most ``limit`` rows. Pagination is not handled here —
        sanmar.com's order history page typically lists recent orders by
        default and the agent rarely needs more than the latest page.
        """
        rows = self.page.locator("tr.orders-separator")
        count = min(rows.count(), limit)
        out: list[OrderRow] = []
        for i in range(count):
            row = rows.nth(i)
            order_number = (
                row.locator("td.col-order-number strong").first.inner_text().strip()
            )
            po = self._optional_text(row, "td.col-purchase-order span")
            date = self._optional_text(row, "td.col-order-date")
            status = self._optional_text(
                row, "div.active-order-tooltiptext span"
            )
            out.append(
                OrderRow(
                    order_number=order_number,
                    po_number=po,
                    date=date,
                    status=status,
                )
            )
        return out

    def find_row(self, order_number: str):
        """Locator for the ``<tr>`` whose order-number cell matches."""
        normalized = order_number.strip()
        return (
            self.page.locator("tr.orders-separator")
            .filter(
                has=self.page.locator("td.col-order-number strong").get_by_text(
                    re.compile(rf"^\s*{re.escape(normalized)}\s*$")
                )
            )
            .first
        )

    def click_return_icon(self, order_number: str) -> None:
        """Fallback path to start a return when a direct deep-link is
        not available. Prefer :class:`ReturnFormPage.goto` with the
        order number, which is more reliable."""
        row = self.find_row(order_number)
        row.wait_for(state="visible")
        row.locator('a[data-bs-content="Return Items"]').first.click()

    def _optional_text(self, scope, selector: str) -> str | None:
        loc = scope.locator(selector).first
        try:
            if loc.count() == 0:
                return None
            return loc.inner_text().strip()
        except Exception:
            return None
