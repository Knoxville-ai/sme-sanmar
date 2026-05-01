"""Tool-discovery entrypoint for the SanMar SME.

This module exists because agent-core's runtime introspects
``sme_tools.example.tools`` to register callables with the LLM. The
canonical implementations live in :mod:`skills.sanmar.sanmar_tools`;
each function below is a thin wrapper that accepts **plain-string**
credential kwargs (the LLM-friendly shape) and builds the typed
:class:`SanMarCredentials` / :class:`SanMarFTPCredentials` objects
internally before forwarding to the underlying tool.

This keeps the LLM out of the business of constructing dataclasses —
the agent collects credentials from the user as plain strings and
passes them directly. Web-services credentials and FTP credentials
are kept distinct (the FTP password is separate from the
sanmar.com / web-services password).

Refer to ``skills/sanmar/SKILL.md`` for the full skill contract,
credential policy, and usage examples. **Do not** add domain logic
to this file — extend ``skills.sanmar.sanmar_tools`` and add a new
wrapper here.
"""

from __future__ import annotations

from typing import Any

from skills.sanmar.sanmar_tools import (
    sanmar_cancel_order as _impl_cancel_order,
    sanmar_check_inventory as _impl_check_inventory,
    sanmar_check_order_status as _impl_check_order_status,
    sanmar_create_purchase_order as _impl_create_purchase_order,
    sanmar_get_pricing as _impl_get_pricing,
    sanmar_get_tracking as _impl_get_tracking,
    sanmar_lookup_mainframe_color as _impl_lookup_mainframe_color,
    sanmar_parse_po_pdf as _impl_parse_po_pdf,
    sanmar_search_products as _impl_search_products,
    sanmar_validate_cart as _impl_validate_cart,
)
from skills.sanmar.schemas import SanMarCredentials, SanMarFTPCredentials


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------


def _ws_creds(
    customer_number: str | None,
    username: str | None,
    password: str | None,
    environment: str,
) -> SanMarCredentials | None:
    if not (customer_number and username and password):
        return None
    return SanMarCredentials(
        customer_number=customer_number,
        username=username,
        password=password,
        environment=environment,
    )


def _ftp_creds(
    customer_number: str | None,
    ftp_password: str | None,
) -> SanMarFTPCredentials | None:
    if not (customer_number and ftp_password):
        return None
    return SanMarFTPCredentials(username=customer_number, password=ftp_password)


# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------


def sanmar_search_products(
    style: str,
    color: str | None = None,
    size: str | None = None,
    *,
    customer_number: str | None = None,
    username: str | None = None,
    password: str | None = None,
    environment: str = "production",
) -> dict[str, Any]:
    """Catalog discovery for a SanMar style. Read-only."""

    return _impl_search_products(
        style=style,
        color=color,
        size=size,
        credentials=_ws_creds(customer_number, username, password, environment),
    )


def sanmar_check_inventory(
    style: str,
    color: str,
    size: str,
    *,
    customer_number: str | None = None,
    username: str | None = None,
    password: str | None = None,
    environment: str = "production",
    ftp_password: str | None = None,
    auto_resolve_color: bool = True,
) -> dict[str, Any]:
    """Live inventory for a single style/color/size at SanMar warehouses.

    When ``auto_resolve_color`` is true (default), if SanMar rejects
    the color or returns empty, the tool downloads the SDL CSV from
    SanMar's SFTP server and retries with the resolved mainframe
    color. The FTP password (``ftp_password``) is required for the
    fallback and is **separate** from the web-services password.
    Read-only.
    """

    return _impl_check_inventory(
        style=style,
        color=color,
        size=size,
        credentials=_ws_creds(customer_number, username, password, environment),
        ftp_credentials=_ftp_creds(customer_number, ftp_password),
        auto_resolve_color=auto_resolve_color,
    )


def sanmar_get_pricing(
    lines: list[dict[str, Any]],
    *,
    customer_number: str | None = None,
    username: str | None = None,
    password: str | None = None,
    environment: str = "production",
    ftp_password: str | None = None,
    auto_resolve_color: bool = True,
) -> dict[str, Any]:
    """Customer-specific (myPrice) and tier pricing for one or more lines.

    Each line is ``{"style": ..., "color": ..., "size": ...}``. Same
    auto-resolve fallback as ``sanmar_check_inventory``: if the
    response is missing some lines (a typical signal that a marketing
    color name was used), the tool resolves each missing line to its
    mainframe color via the SDL CSV and retries. Read-only.
    """

    return _impl_get_pricing(
        lines=lines,
        credentials=_ws_creds(customer_number, username, password, environment),
        ftp_credentials=_ftp_creds(customer_number, ftp_password),
        auto_resolve_color=auto_resolve_color,
    )


def sanmar_validate_cart(
    purchase_order: dict[str, Any],
    *,
    customer_number: str | None = None,
    username: str | None = None,
    password: str | None = None,
    environment: str = "production",
) -> dict[str, Any]:
    """Pre-submit validation for a draft PO. Read-only."""

    return _impl_validate_cart(
        purchase_order=purchase_order,
        credentials=_ws_creds(customer_number, username, password, environment),
    )


def sanmar_check_order_status(
    po_number: str,
    *,
    customer_number: str | None = None,
    username: str | None = None,
    password: str | None = None,
    environment: str = "production",
) -> dict[str, Any]:
    """SanMar's sales-order number and shipment progress for a PO. Read-only."""

    return _impl_check_order_status(
        po_number=po_number,
        credentials=_ws_creds(customer_number, username, password, environment),
    )


def sanmar_get_tracking(
    po_number: str,
    *,
    customer_number: str | None = None,
    username: str | None = None,
    password: str | None = None,
    environment: str = "production",
) -> dict[str, Any]:
    """Tracking numbers and normalized carriers for a SanMar PO. Read-only."""

    return _impl_get_tracking(
        po_number=po_number,
        credentials=_ws_creds(customer_number, username, password, environment),
    )


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
    ``SANMAR_MAINFRAME_COLOR`` for the given style/color (and
    optional size).

    Args:
      style: SanMar mill style number, e.g. "CSF300".
      color: Marketing color name as shown in the catalog or PO,
        e.g. "Safety Yellow".
      size: Optional size to disambiguate matches, e.g. "3XL".
      customer_number: SanMar customer number (used as the SFTP
        username).
      ftp_password: FTP-specific password — distinct from the
        sanmar.com / web-services password.
      force_refresh: Bypass the local cache and re-download the CSV.

    Returns ``{status, style, requested_color, size, matches[],
    source_file, as_of}`` with ``status`` one of
    ``matched | ambiguous | not_found``.
    """

    return _impl_lookup_mainframe_color(
        style=style,
        color=color,
        size=size,
        ftp_credentials=_ftp_creds(customer_number, ftp_password),
        force_refresh=force_refresh,
    )


def sanmar_parse_po_pdf(
    pdf_path: str | None = None,
    pdf_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Extract a draft purchase order from an uploaded PDF.

    Returns a ``ParsedPurchaseOrder`` dict (po_number, ship_to,
    lines, warnings, draft_for_submit). Always show the parsed
    values back to the user for approval before submitting via
    ``sanmar_create_purchase_order``.
    """

    return _impl_parse_po_pdf(pdf_path=pdf_path, pdf_bytes=pdf_bytes)


# ---------------------------------------------------------------------------
# Write tools (HIGH-RISK)
# ---------------------------------------------------------------------------


def sanmar_create_purchase_order(
    purchase_order: dict[str, Any],
    *,
    confirm: bool = False,
    customer_number: str | None = None,
    username: str | None = None,
    password: str | None = None,
    environment: str = "production",
) -> dict[str, Any]:
    """Submit a SanMar PO. **HIGH-RISK external write.**

    With ``confirm=False`` (default) the tool returns a dry-run
    preview of the SOAP envelope without contacting SanMar. Set
    ``confirm=True`` only after ``sanmar_validate_cart`` returned
    ``ok=true`` and the user has approved the draft.
    """

    return _impl_create_purchase_order(
        purchase_order=purchase_order,
        confirm=confirm,
        credentials=_ws_creds(customer_number, username, password, environment),
    )


def sanmar_cancel_order(
    po_number: str,
    reason: str | None = None,
    *,
    confirm: bool = False,
    customer_number: str | None = None,
    username: str | None = None,
    password: str | None = None,
    environment: str = "production",
) -> dict[str, Any]:
    """Cancel a SanMar PO. **STUB — SanMar has no public cancel endpoint.**

    Always returns a structured ``not_implemented`` response. Tell
    the caller to open a SanMar customer-service ticket.
    """

    return _impl_cancel_order(
        po_number=po_number,
        reason=reason,
        confirm=confirm,
        credentials=_ws_creds(customer_number, username, password, environment),
    )


__all__ = [
    "sanmar_cancel_order",
    "sanmar_check_inventory",
    "sanmar_check_order_status",
    "sanmar_create_purchase_order",
    "sanmar_get_pricing",
    "sanmar_get_tracking",
    "sanmar_lookup_mainframe_color",
    "sanmar_parse_po_pdf",
    "sanmar_search_products",
    "sanmar_validate_cart",
]
