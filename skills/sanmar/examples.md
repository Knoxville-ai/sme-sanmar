# SanMar skill — agent examples

Realistic prompts other Knoxville agents send to the SanMar SME, and
the deterministic tool calls the SME should make. Each block shows:

1. Inbound agent prompt.
2. The single tool call to make (or the clarification to return).
3. The JSON shape the SME should return upstream.

Credentials are always pulled from the runtime environment unless the
caller explicitly passes a `credentials` object.

---

## 1. Catalog discovery by style

**Prompt:** "What colors and sizes does style PC55 come in?"

**Tool call:**

```python
sanmar_search_products(style="PC55")
```

**Response upstream:**

```json
{
  "style": "PC55",
  "title": "Port & Company Core Blend Tee",
  "weight": 5.0,
  "image": "https://cdn.sanmar.com/.../PC55.jpg",
  "colors": ["Athletic Heather", "Black", "Jet Black", "Navy"],
  "sizes": ["S", "M", "L", "XL", "2XL", "3XL", "4XL"],
  "variants": [
    {"style": "PC55", "color": "Black", "size": "L",
     "unique_key": "...", "inventory_key": "...", "size_index": "3",
     "image": "...", "piece_price": 7.52}
  ],
  "surface": "sanmar_webservice",
  "operation": "getProductInfoByStyleColorSize"
}
```

---

## 2. Live inventory check

**Prompt:** "Is PC55 in Black, size L, in stock right now?"

**Tool call:**

```python
sanmar_check_inventory(style="PC55", color="Black", size="L")
```

**Response upstream:**

```json
{
  "style": "PC55",
  "color": "Black",
  "size": "L",
  "warehouse_quantities": [120, 88, 0, 240, 60],
  "total_available": 240,
  "surface": "sanmar_webservice",
  "operation": "getInventoryQtyForStyleColorSize"
}
```

`total_available` is the maximum single-warehouse quantity, matching
SanMar shipping semantics: an order ships from one warehouse, so
ability-to-ship is bounded by the largest warehouse quantity, not the
sum.

---

## 3. Pricing for a planned order

**Prompt:** "What's our myPrice on PC55 Black size L and PC55 Navy
size XL?"

**Tool call:**

```python
sanmar_get_pricing(lines=[
    {"style": "PC55", "color": "Black", "size": "L"},
    {"style": "PC55", "color": "Navy", "size": "XL"},
])
```

**Response upstream:**

```json
{
  "items": [
    {"style": "PC55", "color": "Black", "size": "L",
     "inventory_key": "12345", "size_index": "3",
     "piece_price": 7.52, "dozen_price": 7.02, "case_price": 6.52,
     "my_price": 6.75, "sale_piece_price": null,
     "sale_dozen_price": null, "sale_case_price": null},
    {"style": "PC55", "color": "Navy", "size": "XL",
     "inventory_key": "12346", "size_index": "4",
     "piece_price": 7.52, "dozen_price": 7.02, "case_price": 6.52,
     "my_price": 6.75, "sale_piece_price": null,
     "sale_dozen_price": null, "sale_case_price": null}
  ],
  "surface": "sanmar_webservice",
  "operation": "getPricing"
}
```

The agent should keep `inventory_key` and `size_index` per line — they
are required when calling `sanmar_create_purchase_order`.

---

## 4. Pre-submit cart validation

**Prompt:** "Validate this draft PO before I send it."

**Tool call:**

```python
sanmar_validate_cart(purchase_order={
    "po_number": "PO-1042",
    "ship_to": {
        "name": "BaconCo Receiving",
        "address1": "123 Print Way",
        "city": "Memphis", "state": "TN", "zip": "38103",
        "ship_method": "UPS", "email": "purchasing@example.com",
    },
    "lines": [
        {"style": "PC55", "color": "Black", "size": "L", "quantity": 24},
        {"style": "PC55", "color": "Navy", "size": "XL", "quantity": 12},
    ],
})
```

**Response upstream (happy path):**

```json
{
  "ok": true,
  "errored_lines": [],
  "warnings": [],
  "surface": "sanmar_webservice",
  "operation": "getPreSubmitInfo"
}
```

**Response upstream (inventory shortfall):**

```json
{
  "ok": false,
  "errored_lines": [
    {"style": "PC55", "color": "Navy", "size": "XL",
     "message": "Insufficient inventory in any warehouse"}
  ],
  "warnings": [],
  "surface": "sanmar_webservice",
  "operation": "getPreSubmitInfo"
}
```

Agents should refuse to call `sanmar_create_purchase_order` until
`ok` is true.

---

## 5. Submit a purchase order (high risk)

**Prompt:** "Send PO-1042 to SanMar."

The agent must:

1. Have already pulled `inventory_key` and `size_index` per line via
   `sanmar_get_pricing` and merged them onto each `lines[i]`.
2. Have called `sanmar_validate_cart` and confirmed `ok=true`.
3. Confirm with the human/operator that `confirm=True` is intended.

**Dry-run preview (default):**

```python
sanmar_create_purchase_order(purchase_order=draft, confirm=False)
```

```json
{
  "status": "dry_run",
  "po_number": "PO-1042",
  "sanmar_reference": null,
  "raw_payload": "<?xml version='1.0' encoding='UTF-8'?>\n<soapenv:Envelope ...>",
  "raw_response": null,
  "surface": "sanmar_webservice",
  "operation": "submitPO"
}
```

**Live submit:**

```python
sanmar_create_purchase_order(purchase_order=draft, confirm=True)
```

```json
{
  "status": "submitted",
  "po_number": "PO-1042",
  "sanmar_reference": "PO-1042",
  "raw_payload": "...",
  "raw_response": "<soap:Envelope ...>",
  "surface": "sanmar_webservice",
  "operation": "submitPO"
}
```

If SanMar returns `errorOccurred=true` the tool raises
`SanMarAPIError` which the SME maps into the standard error envelope:

```json
{
  "status": "error",
  "surface": "sanmar_webservice",
  "operation": "submitPO",
  "message": "<verbatim SanMar message>",
  "retryable": false
}
```

---

## 6. Order status / tracking after submission

**Prompt:** "What's the status of PO-1042?"

```python
sanmar_check_order_status(po_number="PO-1042")
```

```json
{
  "po_number": "PO-1042",
  "sanmar_order_number": "9876543",
  "shipment_count": 2,
  "status": "shipped",
  "surface": "sanmar_promostandards",
  "operation": "GetOrderShipmentNotificationRequest"
}
```

**Prompt:** "Get tracking numbers for PO-1042."

```python
sanmar_get_tracking(po_number="PO-1042")
```

```json
{
  "po_number": "PO-1042",
  "shipments": [
    {"tracking_number": "1Z999AA10123456784", "carrier": "ups"},
    {"tracking_number": "9622012345678901234567", "carrier": "fedex"}
  ],
  "surface": "sanmar_promostandards",
  "operation": "GetOrderShipmentNotificationRequest"
}
```

---

## 7. Cancellation request — currently unsupported

**Prompt:** "Cancel PO-1042."

```python
sanmar_cancel_order(po_number="PO-1042", reason="duplicate", confirm=True)
```

```json
{
  "status": "not_implemented",
  "po_number": "PO-1042",
  "message": "SanMar's published web services... Cancel via SanMar customer service.",
  "surface": "sanmar_webservice",
  "operation": "cancelPO"
}
```

The SME should pass this verbatim back to the calling agent and
recommend the operator open a SanMar customer-service ticket.

---

## 8. Parse a PDF purchase order uploaded by the user

**Prompt:** "Here's the PO PDF — can you place it for us?"

The agent must parse the PDF, present the extracted values for
approval, then submit. Never auto-submit without user confirmation.

**Tool call (parse):**

```python
sanmar_parse_po_pdf(pdf_path="/uploads/po-1042.pdf")
```

**Response upstream:**

```json
{
  "po_number": "PO-1042",
  "order_date": "04/28/2026",
  "ship_method": "UPS Ground",
  "ship_to": {
    "name": "BaconCo Receiving",
    "address1": "123 Print Way",
    "address2": "",
    "city": "Memphis",
    "state": "TN",
    "zip": "38103",
    "email": "purchasing@example.com"
  },
  "lines": [
    {"style": "PC55", "color": "Black", "size": "L",
     "quantity": 24, "unit_price": 7.52, "description": "Port & Co Tee Black"},
    {"style": "PC55", "color": "Navy", "size": "XL",
     "quantity": 12, "unit_price": 7.52, "description": "Port & Co Tee Navy"}
  ],
  "warnings": [],
  "draft_for_submit": {
    "po_number": "PO-1042",
    "ship_to": {"name": "BaconCo Receiving", "address1": "123 Print Way",
                "city": "Memphis", "state": "TN", "zip": "38103",
                "email": "purchasing@example.com", "ship_method": "UPS Ground"},
    "lines": [
      {"style": "PC55", "color": "Black", "size": "L", "quantity": 24},
      {"style": "PC55", "color": "Navy", "size": "XL", "quantity": 12}
    ]
  },
  "surface": "sanmar_pdf_parser",
  "operation": "parse_po_pdf"
}
```

**Agent flow:**

1. Show the parsed PO back to the user (especially `warnings`).
2. After user approval, call `sanmar_get_pricing` to enrich each line
   with `inventory_key` / `size_index`.
3. Call `sanmar_validate_cart` and confirm `ok: true`.
4. Call `sanmar_create_purchase_order(purchase_order=draft_for_submit, confirm=True)`.

If `warnings` flags missing fields, ask the user to fill them in
rather than guessing.

---

## 9. Resolve a marketing color to its SanMar mainframe color

**Prompt:** "Inventory check for PC55 in Athletic Heather size L."

The agent first tries the marketing name. If SanMar rejects it or
returns nothing, the tool automatically falls back to the SDL CSV
on SanMar's FTP server and retries — no explicit lookup needed.

**Tool call (typical):**

```python
sanmar_check_inventory(style="PC55", color="Athletic Heather", size="L")
```

**Behind the scenes:**

1. Initial SOAP call with `color="Athletic Heather"` errors out
   (`Invalid style/color/size combination`).
2. Tool downloads `SanMarPDD/SanMar_SDL_N.csv` from
   `ftp.sanmar.com:2200` (or uses the local 24h cache).
3. Finds the row with `STYLE#=PC55`, `COLOR_NAME=Athletic Heather`,
   `SIZE=L` and reads `SANMAR_MAINFRAME_COLOR=ATHHTHR`.
4. Retries the inventory call with `color="ATHHTHR"`.
5. Returns the normal `InventoryResult`, with `color` set to the
   resolved mainframe code so the agent can carry it through to
   pricing and PO submission.

**Explicit lookup** (when the agent wants the code without making the
inventory/pricing call yet):

```python
sanmar_lookup_mainframe_color(style="PC55", color="Athletic Heather", size="L")
```

```json
{
  "status": "matched",
  "style": "PC55",
  "requested_color": "Athletic Heather",
  "size": "L",
  "matches": [
    {"style": "PC55", "requested_color": "Athletic Heather", "size": "L",
     "mainframe_color": "ATHHTHR", "color_name": "Athletic Heather",
     "inventory_key": "12345", "size_index": "3", "unique_key": "12345_3"}
  ],
  "source_file": "SanMarPDD/SanMar_SDL_N.csv",
  "as_of": "2026-04-30T06:02:11+00:00",
  "surface": "sanmar_ftp",
  "operation": "lookup_mainframe_color"
}
```

If `status` is `ambiguous`, the agent should ask the user to pick
between the listed `matches`. If `not_found`, surface that to the
user verbatim — do not guess.

---

## 10. Missing credentials → clarification

If the runtime environment has no `SANMAR_*` vars and the caller has
not passed an explicit `credentials=`, the tool raises
`SanMarConfigError`. The SME's policy is:

```json
{
  "status": "needs_clarification",
  "question": "SanMar credentials are not configured. Provide sanMarCustomerNumber, userName, and password (or set SANMAR_CUSTOMER_NUMBER / SANMAR_USERNAME / SANMAR_PASSWORD)."
}
```

Never guess or fall back to other vendors.
