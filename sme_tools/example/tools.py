"""OpenClaw skill entrypoints for the SanMar SME.

Public functions here are the tool contract that other Knoxville agents
use. Keep signatures LLM-friendly and return compact JSON.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any

from sme_tools.example.client import (
    ExampleAPIError,
    ExampleConnectionError,
    example_client_from_env,
)

logger = logging.getLogger(__name__)


def _to_json(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _to_json(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [_to_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_json(v) for k, v in value.items()}
    return value


def _client():
    return example_client_from_env()


def _wrap_call(name: str, fn):
    try:
        result = fn()
        logger.info("%s -> keys=%s", name, list(result.keys()) if isinstance(result, dict) else type(result))
        return _to_json(result)
    except (ExampleAPIError, ExampleConnectionError) as exc:
        raise RuntimeError(f"{name} failed: {exc}") from exc


# ---- Product / inventory / pricing ----


def query_products(
    style: str | None = None,
    color: str | None = None,
    size: str | None = None,
    brand: str | None = None,
    category: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Query SanMar products by style/color/size and/or brand/category.

    Args:
      style: Optional style code (e.g. PC55).
      color: Optional color name/code.
      size: Optional size.
      brand: Optional brand filter.
      category: Optional category filter.
      limit: Max rows requested from upstream.

    Returns:
      JSON dict from the product query endpoint.
    """

    client = _client()
    return _wrap_call(
        "query_products",
        lambda: client.query_products(
            style=style,
            color=color,
            size=size,
            brand=brand,
            category=category,
            limit=limit,
        ),
    )


def check_inventory(
    style: str,
    color: str | None = None,
    size: str | None = None,
    warehouse: str | None = None,
) -> dict[str, Any]:
    """Check SanMar inventory for a style (optionally color/size/warehouse)."""

    client = _client()
    return _wrap_call(
        "check_inventory",
        lambda: client.check_inventory(
            style=style,
            color=color,
            size=size,
            warehouse=warehouse,
        ),
    )


def check_pricing(
    style: str,
    color: str | None = None,
    size: str | None = None,
    quantity: int | None = None,
) -> dict[str, Any]:
    """Check SanMar pricing tiers for a style (optional color/size/qty)."""

    client = _client()
    return _wrap_call(
        "check_pricing",
        lambda: client.check_pricing(
            style=style,
            color=color,
            size=size,
            quantity=quantity,
        ),
    )


# ---- Purchase order workflows ----


def submit_purchase_order(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit a SanMar purchase order payload.

    The caller should provide a validated payload including account,
    ship-to, shipping method, and line items.
    """

    client = _client()
    return _wrap_call(
        "submit_purchase_order",
        lambda: client.submit_purchase_order(payload=payload),
    )


def get_order_status(
    po_number: str | None = None,
    sanmar_order_number: str | None = None,
) -> dict[str, Any]:
    """Fetch order status by PO number and/or SanMar order number."""

    if not po_number and not sanmar_order_number:
        raise RuntimeError(
            "get_order_status requires po_number or sanmar_order_number"
        )

    client = _client()
    return _wrap_call(
        "get_order_status",
        lambda: client.get_order_status(
            po_number=po_number,
            sanmar_order_number=sanmar_order_number,
        ),
    )


def get_shipping_status(
    po_number: str | None = None,
    sanmar_order_number: str | None = None,
) -> dict[str, Any]:
    """Fetch shipping status by PO number and/or SanMar order number."""

    if not po_number and not sanmar_order_number:
        raise RuntimeError(
            "get_shipping_status requires po_number or sanmar_order_number"
        )

    client = _client()
    return _wrap_call(
        "get_shipping_status",
        lambda: client.get_shipping_status(
            po_number=po_number,
            sanmar_order_number=sanmar_order_number,
        ),
    )


def get_tracking(
    po_number: str | None = None,
    sanmar_order_number: str | None = None,
    tracking_number: str | None = None,
) -> dict[str, Any]:
    """Fetch tracking events by PO/order/tracking number."""

    if not po_number and not sanmar_order_number and not tracking_number:
        raise RuntimeError(
            "get_tracking requires po_number, sanmar_order_number, or tracking_number"
        )

    client = _client()
    return _wrap_call(
        "get_tracking",
        lambda: client.get_tracking(
            po_number=po_number,
            sanmar_order_number=sanmar_order_number,
            tracking_number=tracking_number,
        ),
    )


# ---- Health ----


def ping() -> dict[str, Any]:
    """Lightweight health check using product query endpoint with a tiny limit."""

    client = _client()
    return _wrap_call(
        "ping",
        lambda: client.query_products(limit=1),
    )


# ---- Extended SanMar skill tools ----
#
# These wrappers expose the typed SanMar skill in `skills.sanmar.sanmar_tools`
# through this module so the agent-core runtime, which introspects
# `sme_tools.example.tools`, registers them in the agent's tool catalog.
# Each wrapper accepts credentials as plain kwargs (the agent collects
# them from the user) and converts them into the typed credential
# objects the underlying tools expect.


def sanmar_lookup_mainframe_color(
    style: str,
    color: str,
    size: str | None = None,
    *,
    customer_number: str | None = None,
    ftp_password: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Resolve a marketing color name to SanMar's mainframe color code.

    Pulls ``SanMarPDD/SanMar_SDL_N.csv`` from ``ftp.sanmar.com:2200``
    over SFTP (cached locally for 24h) and returns the matching
    ``SANMAR_MAINFRAME_COLOR`` for the given ``style``/``color`` plus
    optional ``size``.

    Args:
      style: SanMar mill style number, e.g. "CSF300".
      color: Marketing color name, e.g. "Safety Yellow".
      size: Optional size to disambiguate matches, e.g. "3XL".
      customer_number: SanMar customer number (used as the SFTP
        username). Pass when the SANMAR_FTP_USERNAME env var is unset.
      ftp_password: FTP-specific password (NOT the sanmar.com /
        web-services password). Pass when the SANMAR_FTP_PASSWORD env
        var is unset.
      force_refresh: Bypass the local cache and re-download the CSV.

    Returns:
      ``{status, style, requested_color, size, matches[], source_file, as_of}``
      with ``status`` one of ``matched | ambiguous | not_found``.
    """

    from skills.sanmar.sanmar_tools import sanmar_lookup_mainframe_color as _impl
    from skills.sanmar.schemas import SanMarFTPCredentials

    ftp_creds = None
    if customer_number and ftp_password:
        ftp_creds = SanMarFTPCredentials(username=customer_number, password=ftp_password)
    return _impl(
        style=style,
        color=color,
        size=size,
        ftp_credentials=ftp_creds,
        force_refresh=force_refresh,
    )


def sanmar_parse_po_pdf(
    pdf_path: str | None = None,
    pdf_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Extract a draft purchase order from an uploaded PDF.

    Returns a ``ParsedPurchaseOrder`` dict (po_number, ship_to,
    lines, warnings, draft_for_submit). The agent must show the
    parsed values back to the user for approval before submitting
    via ``submit_purchase_order``.

    Args:
      pdf_path: Filesystem path to the PDF (provide one of pdf_path
        or pdf_bytes).
      pdf_bytes: Raw PDF content.
    """

    from skills.sanmar.sanmar_tools import sanmar_parse_po_pdf as _impl

    return _impl(pdf_path=pdf_path, pdf_bytes=pdf_bytes)
