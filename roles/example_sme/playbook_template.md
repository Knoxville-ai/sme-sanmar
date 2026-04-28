# Playbook — SanMar SME

Mutable runtime scratchpad for this Class 2 SanMar SME.

## Default loop

1. Validate sender is agent-only.
2. Map request to one domain:
   - Web services -> `api_docs/web_services.md`
   - FTP feeds -> `api_docs/ftp_feeds.md`
   - Purchase orders -> `api_docs/purchase_orders.md`
3. Check required inputs.
4. Clarify if missing.
5. Execute `sme_tools.example.tools.*`.
6. Return compact JSON.
7. Record reusable integration learnings below.

## Standard clarification template

```json
{"status":"needs_clarification","question":"..."}
```

## Learnings

- Append dated SanMar-specific gotchas discovered in production usage.
