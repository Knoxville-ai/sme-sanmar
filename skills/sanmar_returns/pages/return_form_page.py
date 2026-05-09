"""ReturnFormPage — sanmar.com /mysanmar/returns/initiate.

Direct deep-link pattern (preferred):
    https://www.sanmar.com/mysanmar/returns/initiate?salesOrderNumber={SO}

The page renders one ``<tr class="order-history-details-items">`` per
shippable line item. Within each row:

* Checkbox: ``input[name=select-checkbox]`` (id pattern
  ``select-item-{N}``, where N is the row index, but we scope by row
  rather than by id).
* Style number: ``span.style-number`` (text is the SKU, e.g. ``112PL``).
* Color name:   ``td.column-color span.name``.
* Size:         ``td.column-size`` (desktop cell — there's a duplicate
  ``d-lg-none`` mobile cell with the same text).
* Original quantity: ``td.column-pieces`` text.
* Quantity input:    ``td.column-quantity input[type=number]``.
* Reason ``<select>``: ``td.column-select-reason select`` — option
  values are ``SAMPLES``, ``UNWANTED``, ``ORDER_INCORRECT``,
  ``DEFECTIVE_DAMAGED``, ``INCORRECT_PRODUCT``.

When a reason that requires extra input is selected, an additional
``<tr class="return-info-row">`` is inserted as the immediate next
sibling of the item row. That follow-up row may contain (depending on
reason):

* a ``<textarea>`` for free-text details (required),
* a pair of ``<input type=radio>`` for "need replacement?" (required),
* an optional ``<input type=file>`` for image upload (Defective only).

The id prefixes (``defective-*`` vs ``incorrect-*``) differ per reason
but the relative DOM position does not, so this page object treats the
expanded row uniformly.

------------------------------------------------------------------
TODO(item-8b): submission confirmation + RMA extraction
------------------------------------------------------------------
The submit button ("Continue") clicks fine, but we have not yet
captured the post-submit page (URL, success banner, RMA-number element)
because no real submission has been performed against the live site.
:meth:`wait_for_confirmation` raises NotImplementedError and
:meth:`extract_rma_number` returns ``None`` until those selectors are
filled in. Search this file for ``TODO(item-8b)`` to find every spot
that needs an update once the live confirmation HTML is captured.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from playwright.sync_api import Locator

from skills.sanmar_returns.pages.base import BasePage

logger = logging.getLogger("sanmar_returns")

RETURN_FORM_BASE = "https://www.sanmar.com/mysanmar/returns/initiate"

ReturnReason = Literal[
    "SAMPLES",
    "UNWANTED",
    "ORDER_INCORRECT",
    "DEFECTIVE_DAMAGED",
    "INCORRECT_PRODUCT",
]

REASONS_REQUIRING_DETAILS = {
    "ORDER_INCORRECT",
    "DEFECTIVE_DAMAGED",
    "INCORRECT_PRODUCT",
}


@dataclass
class ReturnLine:
    """One item to mark for return.

    ``style_number`` plus ``color`` plus ``size`` together identify a
    row. ``style_number`` alone is usually unique within an order, but
    multi-color/size orders need the disambiguators.
    """

    style_number: str
    quantity: int
    reason: ReturnReason
    color: str | None = None
    size: str | None = None
    details: str | None = None  # required for ORDER_INCORRECT / DEFECTIVE_DAMAGED / INCORRECT_PRODUCT
    needs_replacement: bool | None = None  # required for the same three
    image_path: str | None = None  # optional, DEFECTIVE_DAMAGED only


class ReturnFormPage(BasePage):
    def goto(self, order_number: str) -> None:
        url = f"{RETURN_FORM_BASE}?salesOrderNumber={order_number}"
        self._log("return_form.goto", url=url)
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.locator("tr.order-history-details-items").first.wait_for(
            state="visible"
        )

    # ------------------------------------------------------------------
    # Item selection / form filling
    # ------------------------------------------------------------------

    def find_item_row(
        self,
        style_number: str,
        color: str | None = None,
        size: str | None = None,
    ) -> Locator:
        """Locate the item row whose visible columns match the given
        attributes. ``color`` and ``size`` are optional disambiguators."""
        rows = self.page.locator("tr.order-history-details-items")
        candidates = rows.filter(
            has=self.page.locator("span.style-number").get_by_text(
                re.compile(rf"^\s*{re.escape(style_number)}\s*$")
            )
        )
        if color:
            candidates = candidates.filter(
                has=self.page.locator("td.column-color span.name").get_by_text(
                    re.compile(rf"^\s*{re.escape(color)}\s*$")
                )
            )
        if size:
            candidates = candidates.filter(
                has=self.page.locator(
                    "td.column-size.d-none.d-lg-table-cell"
                ).get_by_text(re.compile(rf"^\s*{re.escape(size)}\s*$"))
            )
        if candidates.count() == 0:
            raise LookupError(
                f"No return-form row matched style={style_number!r} "
                f"color={color!r} size={size!r}"
            )
        return candidates.first

    def fill_line(self, line: ReturnLine) -> None:
        """Check the row, set quantity, choose reason, and (if the
        reason demands it) populate the expanded sub-row."""
        row = self.find_item_row(line.style_number, line.color, line.size)
        row.wait_for(state="visible")

        # 1. Tick the checkbox. Use .check() (idempotent) rather than
        #    .click() so re-runs on the same row are safe.
        row.locator('input[name="select-checkbox"]').check()

        # 2. Quantity. The input has min=1, max=<original-pieces>. Let
        #    Playwright fill it; sanmar will validate on submit.
        row.locator("td.column-quantity input[type=number]").fill(str(line.quantity))

        # 3. Reason dropdown. Use option *value* not label — values are
        #    documented and stable; labels could be re-cased upstream.
        row.locator("td.column-select-reason select").select_option(
            value=line.reason
        )

        # 4. Reasons that need no follow-up are done.
        if line.reason not in REASONS_REQUIRING_DETAILS:
            return

        # 5. Expanded follow-up row appears as the immediate next
        #    sibling. Locate it relative to the item row.
        details_row = row.locator(
            "xpath=following-sibling::tr[contains(@class, 'return-info-row')][1]"
        )
        details_row.wait_for(state="visible")

        if line.details is None:
            raise ValueError(
                f"Reason {line.reason} requires non-empty 'details'"
            )
        details_row.locator("textarea").first.fill(line.details)

        if line.needs_replacement is None:
            raise ValueError(
                f"Reason {line.reason} requires 'needs_replacement' to be set"
            )
        radio_value = "true" if line.needs_replacement else "false"
        details_row.locator(f'input[type=radio][value="{radio_value}"]').check()

        # 6. Optional file upload — only meaningful for DEFECTIVE_DAMAGED,
        #    but we attach if a path was provided regardless of reason
        #    so the field is set in whichever variant exposes it.
        if line.image_path:
            file_input = details_row.locator('input[type=file]')
            if file_input.count() > 0:
                file_input.first.set_input_files(line.image_path)
            else:
                logger.warning(
                    "return_form.image_field_missing",
                    extra={"reason": line.reason},
                )

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def click_continue(self) -> None:
        """Click the form's "Continue" button. Does NOT verify success —
        callers must invoke :meth:`wait_for_confirmation` separately."""
        self._log("return_form.continue")
        self.page.get_by_role("button", name="Continue").click()

    def wait_for_confirmation(self) -> None:  # TODO(item-8b)
        """Wait for the post-submit confirmation page to render.

        TODO(item-8b): replace this stub with a wait on the actual
        success-page URL and/or success-banner element. Until that is
        done the submit_return tool reports
        ``confirmation_pending=True`` and does not assert success.
        """
        raise NotImplementedError(
            "Confirmation page selectors have not been captured yet. "
            "See TODO(item-8b) in pages/return_form_page.py."
        )

    def extract_rma_number(self) -> str | None:  # TODO(item-8b)
        """Read the RMA number from the confirmation page.

        TODO(item-8b): once the confirmation HTML is known, locate the
        RMA element (likely something like
        ``page.get_by_text(re.compile(r"RMA-?\\d+"))`` or a dedicated
        ``<span class="rma-number">``) and return its text.
        """
        logger.warning(
            "return_form.rma_extraction_not_configured",
            extra={"hint": "TODO(item-8b)"},
        )
        return None
