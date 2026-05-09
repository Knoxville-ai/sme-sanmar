"""Agent-facing tool functions for the sanmar_returns skill.

Each tool returns a :class:`ToolResult`. None raise to the caller —
failures are surfaced via ``success=False`` plus an ``observation``
string and (when available) a screenshot of the page state at the
moment of failure.

Granularity is one tool per workflow step so the calling agent can
decide when to stop, inspect a screenshot, or branch on intermediate
data:

1. ``login`` — authenticate and persist storage_state.
2. ``find_order`` — confirm an order is visible in the order-history
   list and return its summary fields.
3. ``initiate_return`` — navigate to the return form for a given SO.
4. ``fill_return_form`` — check items, set quantities, pick reasons,
   populate sub-row fields.
5. ``submit_return`` — click Continue. Currently does not verify the
   confirmation page (see TODO(item-8b)).
6. ``take_screenshot`` — capture the current page on demand.
7. ``run_raw_playwright`` — escape hatch; executes a string of code
   against a scoped local namespace. Use only when the workflow tools
   cannot express what the agent needs.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Iterable

from skills.sanmar_returns.pages.login_page import LoginPage
from skills.sanmar_returns.pages.orders_page import OrdersPage, OrderRow
from skills.sanmar_returns.pages.return_form_page import (
    REASONS_REQUIRING_DETAILS,
    ReturnFormPage,
    ReturnLine,
)
from skills.sanmar_returns.tools.result import ToolResult
from skills.sanmar_returns.tools.retry import with_retry
from skills.sanmar_returns.tools.session import BrowserSession

logger = logging.getLogger("sanmar_returns")


# ----------------------------------------------------------------------
# 1. login
# ----------------------------------------------------------------------


@with_retry()
def login(username: str, password: str, *, force: bool = False) -> ToolResult:
    """Authenticate against sanmar.com.

    Parameters
    ----------
    username, password:
        Required. Passed in by the calling agent — never read from the
        environment. Both values are excluded from structured logs.
    force:
        If ``True``, log in even if the persisted ``storage_state``
        already has a valid session. Default ``False`` (skip the form
        submit when the welcome banner is already visible).

    Returns
    -------
    ToolResult with ``data = {"already_authenticated": bool}``.
    """
    if not username or not password:
        return ToolResult(
            success=False,
            observation="login requires non-empty username and password.",
        )

    session = BrowserSession.get()
    page = LoginPage(session.page)

    if not force:
        try:
            page.page.goto("https://www.sanmar.com/", wait_until="domcontentloaded")
            if page.is_logged_in():
                session.save_storage_state()
                return ToolResult(
                    success=True,
                    observation="Already authenticated; reused stored session.",
                    data={"already_authenticated": True},
                )
        except Exception:
            pass  # fall through to a fresh login

    page.goto()
    page.submit(username, password)
    session.save_storage_state()
    return ToolResult(
        success=True,
        observation="Logged in. Stored session at "
        f"{session.storage_state_path}.",
        data={"already_authenticated": False},
    )


# ----------------------------------------------------------------------
# 2. find_order
# ----------------------------------------------------------------------


@with_retry()
def find_order(order_number: str) -> ToolResult:
    """Confirm an SO appears on the order-history page.

    Returns row metadata (PO number, order date, status). Useful as a
    pre-flight before ``initiate_return`` so the agent can verify the
    order exists, has shipped, and matches the user's expectation
    before any state-changing action.
    """
    if not order_number:
        return ToolResult(
            success=False, observation="find_order requires order_number."
        )

    session = BrowserSession.get()
    page = OrdersPage(session.page)
    page.goto()
    rows = page.list_orders(limit=100)
    match = next(
        (r for r in rows if r.order_number.strip() == order_number.strip()),
        None,
    )
    if match is None:
        return ToolResult(
            success=False,
            observation=(
                f"Order {order_number} not visible on the first 100 rows of "
                "order history. The order may be older than the default "
                "window or the SO number may be wrong."
            ),
            data={"visible_orders": [asdict(r) for r in rows[:10]]},
        )
    return ToolResult(
        success=True,
        observation=f"Found {match.order_number} (status: {match.status}).",
        data=asdict(match),
    )


# ----------------------------------------------------------------------
# 3. initiate_return
# ----------------------------------------------------------------------


@with_retry()
def initiate_return(order_number: str) -> ToolResult:
    """Navigate to the return form for a given SO.

    Uses the deep-link pattern
    ``/mysanmar/returns/initiate?salesOrderNumber=<SO>``. On success the
    skill is ready to receive a ``fill_return_form`` call.
    """
    if not order_number:
        return ToolResult(
            success=False, observation="initiate_return requires order_number."
        )

    session = BrowserSession.get()
    page = ReturnFormPage(session.page)
    page.goto(order_number)
    return ToolResult(
        success=True,
        observation=f"Return form loaded for {order_number}.",
        data={"order_number": order_number},
    )


# ----------------------------------------------------------------------
# 4. fill_return_form
# ----------------------------------------------------------------------


@with_retry()
def fill_return_form(items: Iterable[dict[str, Any]]) -> ToolResult:
    """Mark each requested line item for return.

    ``items`` is an iterable of dicts with keys:

    * ``style_number`` (str, required) — e.g. ``"112PL"``.
    * ``quantity`` (int, required) — must be ``>= 1`` and
      ``<= original_pieces``.
    * ``reason`` (str, required) — one of the documented values
      (``SAMPLES``, ``UNWANTED``, ``ORDER_INCORRECT``,
      ``DEFECTIVE_DAMAGED``, ``INCORRECT_PRODUCT``).
    * ``color`` (str, optional) — disambiguator when the order has
      multiple colors of the same style.
    * ``size`` (str, optional) — disambiguator.
    * ``details`` (str, required for ORDER_INCORRECT, DEFECTIVE_DAMAGED,
      and INCORRECT_PRODUCT) — free-text description.
    * ``needs_replacement`` (bool, required for the same three reasons).
    * ``image_path`` (str, optional, DEFECTIVE_DAMAGED only) — local
      file path to attach.
    """
    items = list(items)
    if not items:
        return ToolResult(
            success=False,
            observation="fill_return_form requires at least one item.",
        )

    session = BrowserSession.get()
    page = ReturnFormPage(session.page)

    filled: list[dict[str, Any]] = []
    for raw in items:
        try:
            line = ReturnLine(
                style_number=raw["style_number"],
                quantity=int(raw["quantity"]),
                reason=raw["reason"],
                color=raw.get("color"),
                size=raw.get("size"),
                details=raw.get("details"),
                needs_replacement=raw.get("needs_replacement"),
                image_path=raw.get("image_path"),
            )
        except KeyError as exc:
            return ToolResult(
                success=False,
                observation=f"Item missing required field: {exc}",
                data={"filled_so_far": filled, "offending_item": raw},
            )

        if (
            line.reason in REASONS_REQUIRING_DETAILS
            and (line.details is None or line.needs_replacement is None)
        ):
            return ToolResult(
                success=False,
                observation=(
                    f"Reason {line.reason} requires both 'details' and "
                    "'needs_replacement'."
                ),
                data={"filled_so_far": filled, "offending_item": raw},
            )

        page.fill_line(line)
        filled.append(asdict(line))

    return ToolResult(
        success=True,
        observation=f"Filled {len(filled)} item(s) on the return form.",
        data={"filled": filled},
    )


# ----------------------------------------------------------------------
# 5. submit_return
# ----------------------------------------------------------------------


@with_retry()
def submit_return() -> ToolResult:
    """Click the form's Continue button.

    .. warning::
       Confirmation parsing is not yet implemented (see TODO(item-8b)
       in ``pages/return_form_page.py``). This tool currently returns
       ``success=True`` after the click lands without raising, but it
       does **not** assert that the submission was accepted by sanmar
       and does not extract an RMA number. Treat the result as
       "submission attempted" rather than "submission confirmed" until
       the confirmation HTML is captured and the stubs are filled in.
    """
    session = BrowserSession.get()
    page = ReturnFormPage(session.page)

    page.click_continue()

    rma_number: str | None = None
    confirmation_pending = True
    try:
        page.wait_for_confirmation()
        rma_number = page.extract_rma_number()
        confirmation_pending = False
    except NotImplementedError:
        # Stub still in place. Submission was clicked but we cannot
        # programmatically verify success.
        pass

    if confirmation_pending:
        return ToolResult(
            success=True,
            observation=(
                "Continue button clicked. Confirmation parsing not yet "
                "configured (see TODO(item-8b)). The agent should "
                "screenshot the page and verify the RMA visually before "
                "reporting success to the user."
            ),
            data={"rma_number": None, "confirmation_pending": True},
        )

    return ToolResult(
        success=True,
        observation=(
            f"Return submitted. RMA: {rma_number}"
            if rma_number
            else "Return submitted; RMA number not located on confirmation page."
        ),
        data={"rma_number": rma_number, "confirmation_pending": False},
    )


# ----------------------------------------------------------------------
# 6. take_screenshot
# ----------------------------------------------------------------------


@with_retry()
def take_screenshot(*, full_page: bool = True) -> ToolResult:
    """Capture the current page as a base64-encoded PNG."""
    session = BrowserSession.get()
    png = session.page.screenshot(full_page=full_page)
    return ToolResult(
        success=True,
        observation=f"Captured screenshot of {session.page.url}.",
        screenshot=ToolResult.encode_screenshot(png),
        data={"url": session.page.url},
    )


# ----------------------------------------------------------------------
# 7. run_raw_playwright (escape hatch)
# ----------------------------------------------------------------------


def run_raw_playwright(code: str) -> ToolResult:
    """Execute a snippet of Python against the live Playwright ``page``.

    The snippet runs with two locals available:

    * ``page`` — the active ``playwright.sync_api.Page``.
    * ``result`` — the snippet should assign a JSON-serialisable value
      to this name; it will be returned as ``data["result"]``.

    Use this only when the workflow tools cannot express what the agent
    needs. There is **no retry** wrapper on this tool — failures
    surface immediately.

    .. warning::
       Executes arbitrary Python in this process. Only suitable inside
       a class-2 SME container where the calling agent is trusted.
    """
    if not code or not code.strip():
        return ToolResult(
            success=False, observation="run_raw_playwright requires non-empty code."
        )

    session = BrowserSession.get()
    locals_: dict[str, Any] = {"page": session.page, "result": None}
    try:
        exec(compile(code, "<raw_playwright>", "exec"), {}, locals_)
    except Exception as exc:
        png = None
        try:
            png = ToolResult.encode_screenshot(session.page.screenshot(full_page=True))
        except Exception:
            pass
        return ToolResult(
            success=False,
            observation=f"run_raw_playwright raised {type(exc).__name__}: {exc}",
            screenshot=png,
        )

    raw_result = locals_.get("result")
    return ToolResult(
        success=True,
        observation="run_raw_playwright completed.",
        data={"result": _json_safe(raw_result)},
    )


def _json_safe(value: Any) -> Any:
    """Coerce ``value`` to something JSON-serialisable; fall back to repr."""
    import json

    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


__all__ = [
    "login",
    "find_order",
    "initiate_return",
    "fill_return_form",
    "submit_return",
    "take_screenshot",
    "run_raw_playwright",
]
