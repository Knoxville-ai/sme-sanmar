# SanMar SME API docs index

This directory contains runtime documentation for the **Class 2 SanMar SME agent**.

The SME must read the relevant page before tool execution. These docs are written for LLM/tooling correctness (not end-user marketing prose).

## Core markdown docs

- `auth_and_patterns.md` — cross-cutting onboarding, auth, endpoint, transport, and error patterns.
- `web_services.md` — SanMar SOAP web-services operations and response normalization guidance.
- `ftp_feeds.md` — FTP feed families, file conventions, join keys, and cadence expectations.
- `purchase_orders.md` — PO submission/validation workflow and operational safeguards.

## Source PDFs retained for traceability

- `SanMarWebServicesIntegrationGuide-v16.10.pdf`
- `SanMar-FTP-Integration-Guide-v23.1.pdf`
- `SanMar-FTP-Integration-Guide-v18 (4).pdf`
- `SanMar-Purchase-Order-Integration-Guide-24.1.pdf`

## Authoring standard for future updates

When new SanMar behavior is discovered:

1. Update the closest topical markdown file above.
2. Prefer concrete field names, operation names, and payload examples.
3. Document edge cases that can cause bad writes or silent data drift.
4. Keep this index aligned if a new domain markdown file is added.


## Tool usage linkage

The agent tool entrypoints live in `skills/sanmar/sanmar_tools.py`,
contracted by `skills/sanmar/SKILL.md`, with a machine-readable
manifest in `skills/sanmar/tools.json`. Common action mapping:

- Product queries -> `sanmar_search_products`
- Inventory checks -> `sanmar_check_inventory`
- Pricing checks -> `sanmar_get_pricing`
- Pre-submit cart validation -> `sanmar_validate_cart`
- PO submission -> `sanmar_create_purchase_order`
- Order status -> `sanmar_check_order_status`
- Tracking / shipping status -> `sanmar_get_tracking`
- PDF PO intake -> `sanmar_parse_po_pdf`
- Marketing-color → mainframe-color resolution (SDL CSV over SFTP) ->
  `sanmar_lookup_mainframe_color`
