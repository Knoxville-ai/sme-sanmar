# Playbook — SanMar SME

Mutable runtime scratchpad for this Class 2 SanMar SME.

## Where tools live

- Skill contract: `skills/sanmar/SKILL.md` (read on boot)
- Tool entrypoints: `skills.sanmar.sanmar_tools`
- Tool manifest: `skills/sanmar/tools.json`
- Examples: `skills/sanmar/examples.md`
- API domain docs: `skills/sanmar/docs/auth_and_patterns.md`, `skills/sanmar/docs/web_services.md`, `skills/sanmar/docs/ftp_feeds.md`, `skills/sanmar/docs/purchase_orders.md`

## Tool catalog (common actions)

Read-only:

- `sanmar_search_products(style, color?, size?, *, credentials)`
- `sanmar_check_inventory(style, color, size, *, credentials, ftp_credentials?, auto_resolve_color=True)`
- `sanmar_get_pricing(lines, *, credentials, ftp_credentials?, auto_resolve_color=True)`
- `sanmar_validate_cart(purchase_order, *, credentials)`
- `sanmar_check_order_status(po_number, *, credentials)`
- `sanmar_get_tracking(po_number, *, credentials)`
- `sanmar_lookup_mainframe_color(style, color, size?, *, ftp_credentials, force_refresh=False)`
- `sanmar_parse_po_pdf(pdf_path?, pdf_bytes?)`

Write (HIGH-RISK):

- `sanmar_create_purchase_order(purchase_order, *, confirm=False, credentials)`
- `sanmar_cancel_order(...)` — stub; SanMar has no public cancel endpoint.

Credentials (plain string kwargs — the wrappers build typed objects):

- Web services (SOAP/PromoStandards): pass `customer_number`,
  `username`, `password`, and optionally `environment`
  (`"production"` / `"development"`).
- SFTP (SDL CSV): pass `customer_number` and `ftp_password`. The
  FTP password is **separate** from the web-services password.
- The agent collects credentials from the user on first need,
  remembers them for the session, and passes them on every call.

## Default loop

1. Validate sender is agent-only.
2. Map request to one domain:
   - Web services -> `skills/sanmar/docs/web_services.md`
   - FTP feeds -> `skills/sanmar/docs/ftp_feeds.md`
   - Purchase orders -> `skills/sanmar/docs/purchase_orders.md`
3. Pick the corresponding `sanmar_*` tool from the catalog above.
4. Check required inputs, credentials, and policy constraints
   (`dry_run`, `allow_writes`, `max_rows_per_call`).
5. Clarify if missing.
6. Execute `skills.sanmar.sanmar_tools.<tool>(...)`.
7. Return compact JSON with `surface`, `operation`, and (if available) source timestamp.
8. Record reusable integration learnings below.

## Standard clarification template

```json
{"status":"needs_clarification","question":"..."}
```

## Learnings

- Append dated SanMar-specific gotchas discovered in production usage.
