# SanMar Skill

Deterministic SanMar API toolkit for Class 2 SME agents. Wraps SanMar's
SOAP web services and PromoStandards order-shipment service behind a
small set of typed Python functions.

The skill is self-contained: it does not depend on Odoo, Knoxville's
`agent-core`, or any vendor ORM. It only requires Python 3.11+ and
`requests` (which `agent-core` already pulls in transitively). All
XML parsing and SOAP envelope construction uses the Python stdlib
`xml.etree.ElementTree` — no `lxml` install is required at runtime.

Two optional dependencies enable the PDF and FTP tools:

- `pypdf>=4.0` — required for `sanmar_parse_po_pdf` (PDF text
  extraction). Install if your agent processes uploaded PO PDFs.
- `paramiko>=3.0` — required for `sanmar_lookup_mainframe_color` and
  the auto-resolve fallback in `sanmar_check_inventory` /
  `sanmar_get_pricing`. Install if your agent needs to translate
  marketing colors into SanMar mainframe color codes.

Both are imported lazily, so the skill still loads if they're absent;
the affected tools raise a clear error pointing at `pip install`.

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
- Parsing an uploaded PDF purchase order into a structured draft the
  user can review and approve before submission.
- Translating a marketing color name (e.g. "Athletic Heather") into
  SanMar's mainframe color code (e.g. "ATHHTHR") when an inventory
  or pricing call rejects the consumer-facing color.

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
| `sanmar_parse_po_pdf` | read-only (local file) | implemented |
| `sanmar_lookup_mainframe_color` | read-only (FTP) | implemented |

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

### FTP credentials (separate from web services)

`sanmar_lookup_mainframe_color` and the auto-resolve fallback need
SanMar SFTP access. Per SanMar's FTP Integration Guide v23.1, the
server is `ftp.sanmar.com:2200` over **SFTP** (SSH), and FTP creds are
issued separately from web-service creds — your `sanmar.com` username
will *not* work on the FTP server.

```bash
SANMAR_FTP_USERNAME=<customer_number>   # defaults to SANMAR_CUSTOMER_NUMBER
SANMAR_FTP_PASSWORD=...
SANMAR_FTP_HOST=ftp.sanmar.com           # optional override
SANMAR_FTP_PORT=2200                     # optional override
SANMAR_FTP_CACHE_DIR=/tmp/sme-sanmar-cache  # optional override
```

The SDL CSV (`SanMarPDD/SanMar_SDL_N.csv`) is cached locally for 24h
(SanMar refreshes it nightly). Pass `force_refresh=True` to bypass the
cache.

## PDF purchase-order intake

`sanmar_parse_po_pdf` accepts a PDF path or raw bytes and returns a
best-effort `ParsedPurchaseOrder` with:

- `po_number`, `order_date`, `ship_method`
- `ship_to` (name/address/city/state/zip/email)
- `lines[]` with `style`, `color`, `size`, `quantity`, `unit_price`
- `warnings[]` listing fields the heuristics could not confidently
  extract
- `draft_for_submit` — a ready-to-pass `purchase_order` dict for
  `sanmar_create_purchase_order`, populated only when the parse is
  complete enough.

The agent **must** show the parsed PO back to the user for approval
before calling `sanmar_create_purchase_order`. Parsers cannot
guarantee correctness across every PO layout — treat the output as a
draft, not as authoritative.

## Mainframe color resolution

SanMar's inventory/pricing/PO endpoints query against the *mainframe*
color (an abbreviated code like `ATHHTHR`), not the marketing
`COLOR_NAME` shown in catalogs (`Athletic Heather`). When the agent
queries with a marketing name, SanMar typically returns
`Invalid style specified` or an empty response.

Resolution flow:

1. The agent receives a request that contains a marketing color name.
2. It calls `sanmar_check_inventory` / `sanmar_get_pricing` with that
   color.
3. If SanMar errors out **or** returns an empty response, the tool
   automatically:
   - downloads `SanMarPDD/SanMar_SDL_N.csv` from the SFTP server (or
     uses the cache),
   - looks up the row matching `STYLE#`, `COLOR_NAME`, and `SIZE`,
   - retries the call with the matching `SANMAR_MAINFRAME_COLOR`.
4. If the agent wants explicit control, it can call
   `sanmar_lookup_mainframe_color` directly and pass the resolved code
   into subsequent calls.

Disable the auto-retry by passing `auto_resolve_color=False` when the
caller has already supplied a known mainframe code.

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
