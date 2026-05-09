# SanMar SME runtime docs index

This directory holds the runtime API reference the **SanMar Class 2 SME**
reads before tool calls. Files here travel with the skill (under
`skills/sanmar/`) so they're installed into the OpenClaw workspace
alongside `SKILL.md` on every boot — the agent reaches them at
workspace-relative paths like `skills/sanmar/docs/web_services.md`.

Docs are written for LLM/tooling correctness, not end-user marketing
prose.

## Pages

- `auth_and_patterns.md` — cross-cutting onboarding, auth, endpoint, transport, and error patterns.
- `web_services.md` — SanMar SOAP web-services operations and response normalization guidance.
- `ftp_feeds.md` — FTP feed families, file conventions, join keys, and cadence expectations.
- `purchase_orders.md` — PO submission/validation workflow and operational safeguards.

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

## Source PDFs

The original vendor PDFs (`SanMarWebServicesIntegrationGuide-v16.10.pdf`,
`SanMar-FTP-Integration-Guide-v23.1.pdf`,
`SanMar-FTP-Integration-Guide-v18 (4).pdf`,
`SanMar-Purchase-Order-Integration-Guide-24.1.pdf`) are retained at
the repo root under `api_docs/` for traceability. They are **not**
copied into the agent's runtime workspace — the markdown pages here
are the operational reference. Refresh those markdown pages when a
new vendor guide arrives.

## Authoring standard for future updates

When new SanMar behavior is discovered:

1. Update the closest topical markdown file above.
2. Prefer concrete field names, operation names, and payload examples.
3. Document edge cases that can cause bad writes or silent data drift.
4. Keep this index aligned if a new domain markdown file is added.
