# SanMar Skill

Deterministic SanMar API toolkit for Class 2 SME agents. Wraps SanMar's
SOAP web services and PromoStandards order-shipment service behind a
small set of typed Python functions.

The skill is self-contained: it does not depend on Odoo, Knoxville's
`agent-core`, or any vendor ORM. It only requires Python 3.11+ and
`requests`.

## When to use this skill

Invoke a `sanmar_*` tool when the caller's request involves any of:

- Looking up SanMar product styles, colors, sizes, or images.
- Checking real-time inventory at SanMar warehouses for a given
  style/color/size.
- Pulling customer-specific (`myPrice`) pricing for a SKU.
- Validating a draft cart of style/color/size lines before placing an
  order.
- Submitting a SanMar purchase order via web service.
- Polling SanMar order status, shipment notifications, or tracking
  numbers tied to a PO.
- Cancelling a previously submitted SanMar order.

Do **not** use this skill for unrelated apparel vendors (S&S, Alpha,
etc.), and never invent SanMar request shapes from prose — call the
deterministic tools.

## Available tools

All callables live in `sanmar_tools.py` and are described in
`tools.json`. `examples.md` shows realistic agent prompts.

| Tool | Risk | Status |
| --- | --- | --- |
| `sanmar_search_products` | read-only | implemented |
| `sanmar_check_inventory` | read-only | implemented |
| `sanmar_get_pricing` | read-only | implemented |
| `sanmar_validate_cart` | read-only | implemented (uses pre-submit) |
| `sanmar_create_purchase_order` | **high — external write** | implemented |
| `sanmar_check_order_status` | read-only | implemented |
| `sanmar_get_tracking` | read-only | implemented |
| `sanmar_cancel_order` | **high — external write** | stub (SanMar does not expose a public cancel endpoint) |

Every tool takes typed inputs (see `schemas.py`), returns a structured
JSON-serializable dict, and raises `SanMarError` subclasses for
predictable error handling.

## Authentication

SanMar SOAP requests carry three fields inside the request body:

- `sanMarCustomerNumber`
- `sanMarUserName`
- `sanMarUserPassword`

PromoStandards (order shipment notification) uses `shar:id` and
`shar:password` in the SOAP header objects, typically the same
username/password.

The skill never hardcodes credentials. Two ways to provide them:

1. **Environment variables** (recommended at runtime):

   ```bash
   SANMAR_CUSTOMER_NUMBER=...
   SANMAR_USERNAME=...
   SANMAR_PASSWORD=...
   SANMAR_ENV=production    # or "development" — flips PO endpoint to test-ws
   ```

2. **Explicit credentials object** passed into every tool call:

   ```python
   from skills.sanmar.schemas import SanMarCredentials
   creds = SanMarCredentials(customer_number=..., username=..., password=...)
   sanmar_check_inventory(style="PC55", color="Black", size="L", credentials=creds)
   ```

If credentials are missing, the skill raises `SanMarConfigError` and the
caller agent must respond with `needs_clarification` and request the
credentials from the operator. Do not guess defaults.

## Endpoints used

Production (default):

- Pricing — `SanMarWebService/SanMarPricingServicePort`
- Product info — `SanMarWebService/SanMarProductInfoServicePort`
- Inventory — `SanMarWebService/SanMarWebServicePort`
- PO submit — `SanMarWebService/SanMarPOServicePort`
- Order shipment — `promostandards/OrderShipmentNotificationServiceBinding`

Development PO endpoint (when `SANMAR_ENV=development`):

- `https://test-ws.sanmar.com:8080/SanMarWebService/SanMarPOServicePort`

Network reachability requires SanMar to allowlist the calling IP. A
connection timeout is most often a missing IP allowlist entry, not an
auth problem.

## Risk and side effects

`sanmar_create_purchase_order` and `sanmar_cancel_order` are the only
side-effecting tools. They:

- emit live calls to SanMar with billable consequences,
- have no automatic idempotency on SanMar's side beyond `poNum`
  uniqueness,
- require `confirm=True` in the input payload — without it the tool
  returns a dry-run preview of the SOAP envelope.

All other tools are pure reads.

## Error normalization

The client maps SanMar SOAP faults and the typo'd `errorOccured`
element into a single `SanMarAPIError` shape with:

```json
{
  "status": "error",
  "surface": "sanmar_webservice|sanmar_promostandards",
  "operation": "<soap_action>",
  "message": "<upstream message>",
  "retryable": true|false
}
```

`retryable=true` for network/timeouts and 5xx responses,
`retryable=false` for auth, schema, and invalid-style errors.

## Testing

```bash
cd skills/sanmar
python -m pytest tests/
```

Tests use stubbed HTTP responses and never hit SanMar.

## Discovery

Runtime agents should locate this skill by reading
`skills/sanmar/SKILL.md` from the workspace root, then importing
`skills.sanmar.sanmar_tools`. The legacy `sme_tools/example/tools.py`
shim still works for callers that haven't migrated.
