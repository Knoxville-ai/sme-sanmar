"""Agent-facing SanMar tools.

Each function here is a deterministic callable that other Knoxville
agents invoke. Inputs are typed, outputs are JSON-serializable dicts,
and errors are normalized via :class:`SanMarError` subclasses.

Read-only tools are clearly distinguished from side-effecting tools
(``sanmar_create_purchase_order``, ``sanmar_cancel_order``). The two
write tools require ``confirm=True`` and otherwise return a dry-run
preview without contacting SanMar.
"""

from __future__ import annotations

import logging
from typing import Any

from skills.sanmar.sanmar_client import (
    SanMarClient,
    SanMarConfigError,
    SanMarError,
    credentials_from_env,
)
from skills.sanmar.schemas import (
    CancelResult,
    CartValidationResult,
    InventoryResult,
    OrderStatusResult,
    PricingLine,
    PricingResult,
    ProductSearchResult,
    PurchaseOrderDraft,
    PurchaseOrderLine,
    PurchaseOrderResult,
    SanMarCredentials,
    ShipTo,
    TrackingResult,
    to_dict,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _client(credentials: SanMarCredentials | None) -> SanMarClient:
    if credentials is None:
        credentials = credentials_from_env()
    return SanMarClient(credentials=credentials)


def _coerce_pricing_line(value: Any) -> PricingLine:
    if isinstance(value, PricingLine):
        return value
    if isinstance(value, dict):
        return PricingLine(
            style=value["style"], color=value["color"], size=value["size"]
        )
    raise TypeError(f"Cannot coerce {value!r} to PricingLine")


def _coerce_po_draft(value: Any) -> PurchaseOrderDraft:
    if isinstance(value, PurchaseOrderDraft):
        return value
    if not isinstance(value, dict):
        raise TypeError(f"Cannot coerce {value!r} to PurchaseOrderDraft")

    ship_to_raw = value.get("ship_to")
    if isinstance(ship_to_raw, ShipTo):
        ship_to = ship_to_raw
    elif isinstance(ship_to_raw, dict):
        ship_to = ShipTo(**ship_to_raw)
    else:
        raise ValueError("purchase_order.ship_to is required")

    lines_raw = value.get("lines") or []
    lines: list[PurchaseOrderLine] = []
    for ln in lines_raw:
        if isinstance(ln, PurchaseOrderLine):
            lines.append(ln)
        elif isinstance(ln, dict):
            lines.append(PurchaseOrderLine(**ln))
        else:
            raise TypeError(f"Cannot coerce PO line {ln!r}")

    if not lines:
        raise ValueError("purchase_order.lines must contain at least one line")

    return PurchaseOrderDraft(
        po_number=value["po_number"], ship_to=ship_to, lines=lines
    )


# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------


def sanmar_search_products(
    style: str,
    color: str | None = None,
    size: str | None = None,
    *,
    credentials: SanMarCredentials | None = None,
) -> dict[str, Any]:
    """Catalog discovery for a SanMar style.

    Wraps ``getProductInfoByStyleColorSize``. Returns title, weight,
    primary image, and the full set of color/size variants found.
    Read-only.
    """

    if not style:
        raise SanMarConfigError("style is required")
    client = _client(credentials)
    result: ProductSearchResult = client.search_products(style=style, color=color, size=size)
    return to_dict(result)


def sanmar_check_inventory(
    style: str,
    color: str,
    size: str,
    *,
    credentials: SanMarCredentials | None = None,
) -> dict[str, Any]:
    """Live inventory for a single style/color/size at SanMar warehouses.

    Note: ``color`` must be the SanMar mainframe color code, not the
    consumer-facing color name. Read-only.
    """

    if not (style and color and size):
        raise SanMarConfigError("style, color, and size are all required")
    client = _client(credentials)
    result: InventoryResult = client.get_inventory(style=style, color=color, size=size)
    return to_dict(result)


def sanmar_get_pricing(
    lines: list[Any],
    *,
    credentials: SanMarCredentials | None = None,
) -> dict[str, Any]:
    """Customer-specific (`myPrice`) and tier pricing for one or more lines.

    Each line is ``{style, color, size}``. The response also includes
    ``inventory_key`` and ``size_index`` per line — pass those into
    :func:`sanmar_create_purchase_order` to enrich PO submit lines.
    Read-only.
    """

    coerced = [_coerce_pricing_line(ln) for ln in lines]
    if not coerced:
        raise SanMarConfigError("at least one pricing line is required")
    client = _client(credentials)
    result: PricingResult = client.get_pricing(lines=coerced)
    return to_dict(result)


def sanmar_validate_cart(
    purchase_order: Any,
    *,
    credentials: SanMarCredentials | None = None,
) -> dict[str, Any]:
    """Pre-submit validation for a draft PO.

    Wraps ``getPreSubmitInfo`` — surfaces per-line inventory and
    validation errors without committing the order. Always safe to
    call. Read-only.
    """

    draft = _coerce_po_draft(purchase_order)
    client = _client(credentials)
    result: CartValidationResult = client.pre_submit_po(draft)
    return to_dict(result)


def sanmar_check_order_status(
    po_number: str,
    *,
    credentials: SanMarCredentials | None = None,
) -> dict[str, Any]:
    """Look up SanMar's sales-order number and shipment progress for a PO.

    Wraps the PromoStandards ``GetOrderShipmentNotificationRequest``.
    Read-only.
    """

    if not po_number:
        raise SanMarConfigError("po_number is required")
    client = _client(credentials)
    result: OrderStatusResult = client.get_order_status(po_number=po_number)
    return to_dict(result)


def sanmar_get_tracking(
    po_number: str,
    *,
    credentials: SanMarCredentials | None = None,
) -> dict[str, Any]:
    """Tracking numbers and normalized carriers for a SanMar PO.

    Returns ``{shipments: [{tracking_number, carrier}]}``. Carrier is
    normalized to ``fedex``/``ups``/``usps`` or ``None``. Read-only.
    """

    if not po_number:
        raise SanMarConfigError("po_number is required")
    client = _client(credentials)
    result: TrackingResult = client.get_tracking(po_number=po_number)
    return to_dict(result)


# ---------------------------------------------------------------------------
# Write tools (high risk)
# ---------------------------------------------------------------------------


def sanmar_create_purchase_order(
    purchase_order: Any,
    *,
    confirm: bool = False,
    credentials: SanMarCredentials | None = None,
) -> dict[str, Any]:
    """Submit a SanMar PO. **HIGH-RISK external write.**

    Behavior:

    - If ``confirm`` is False (default), returns a dry-run preview with
      the SOAP envelope that *would* be sent. No network call to the
      submit endpoint happens.
    - If ``confirm`` is True, transmits the order via ``submitPO``.

    Callers should normally:

    1. Call :func:`sanmar_get_pricing` to obtain ``inventory_key`` and
       ``size_index`` per line and populate them on the draft.
    2. Call :func:`sanmar_validate_cart` and only proceed if ``ok``.
    3. Call this function with ``confirm=True``.
    """

    draft = _coerce_po_draft(purchase_order)
    client = _client(credentials)

    if not confirm:
        preview = client.build_po_envelope(draft, pre_submit=False)
        return to_dict(
            PurchaseOrderResult(
                status="dry_run",
                po_number=draft.po_number,
                sanmar_reference=None,
                raw_payload=preview.decode("utf-8"),
                raw_response=None,
            )
        )

    result: PurchaseOrderResult = client.submit_po(draft)
    return to_dict(result)


def sanmar_cancel_order(
    po_number: str,
    reason: str | None = None,
    *,
    confirm: bool = False,
    credentials: SanMarCredentials | None = None,  # noqa: ARG001 — interface stable
) -> dict[str, Any]:
    """Cancel a SanMar PO. **HIGH-RISK external write — STUB.**

    The reference SanMar SOAP web services and the PromoStandards
    bindings used by this skill do not expose a cancel operation.
    Cancellations today must be performed via SanMar customer service
    or the SanMar account portal.

    The tool surface is reserved so future vendor support can drop in
    without changing callers. Currently always returns a structured
    ``not_implemented`` response.
    """

    if not po_number:
        raise SanMarConfigError("po_number is required")
    return to_dict(
        CancelResult(
            status="not_implemented",
            po_number=po_number,
            message=(
                "SanMar's published web services and PromoStandards "
                "bindings do not currently expose a cancel endpoint. "
                "Cancel via SanMar customer service or the SanMar "
                "account portal. (confirm={confirm}, reason={reason!r})"
            ).format(confirm=confirm, reason=reason),
        )
    )


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------


__all__ = [
    "SanMarError",
    "sanmar_search_products",
    "sanmar_check_inventory",
    "sanmar_get_pricing",
    "sanmar_validate_cart",
    "sanmar_create_purchase_order",
    "sanmar_check_order_status",
    "sanmar_get_tracking",
    "sanmar_cancel_order",
]
