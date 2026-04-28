# Playbook — SanMar SME

Mutable runtime scratchpad for this Class 2 SanMar SME.

## Where tools live

- Tool entrypoints: `sme_tools.example.tools`
- Upstream client methods: `sme_tools.example.client.ExampleClient`
- API domain docs: `api_docs/auth_and_patterns.md`, `api_docs/web_services.md`, `api_docs/ftp_feeds.md`, `api_docs/purchase_orders.md`

## Tool catalog (common actions)

- All tool calls auto-attach SOAP auth fields from env: `sanMarCustomerNumber`, `userName`, `password`.
- `query_products(style?, color?, size?, brand?, category?, limit?)`
- `check_inventory(style, color?, size?, warehouse?)`
- `check_pricing(style, color?, size?, quantity?)`
- `submit_purchase_order(payload)`
- `get_order_status(po_number?, sanmar_order_number?)`
- `get_shipping_status(po_number?, sanmar_order_number?)`
- `get_tracking(po_number?, sanmar_order_number?, tracking_number?)`

## Default loop

1. Validate sender is agent-only.
2. Map request to one domain:
   - Web services -> `api_docs/web_services.md`
   - FTP feeds -> `api_docs/ftp_feeds.md`
   - Purchase orders -> `api_docs/purchase_orders.md`
3. Pick the corresponding tool from the catalog above.
4. Check required inputs and policy constraints (`dry_run`, `allow_writes`, `max_rows_per_call`).
5. Clarify if missing.
6. Execute `sme_tools.example.tools.*`.
7. Return compact JSON with `surface`, `operation`, and (if available) source timestamp.
8. Record reusable integration learnings below.

## Standard clarification template

```json
{"status":"needs_clarification","question":"..."}
```

## Learnings

- Append dated SanMar-specific gotchas discovered in production usage.
