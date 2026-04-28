<!--
  AUTH AND PATTERNS — cross-cutting reference for this SME's upstream API.
  Replace every `{{...}}` placeholder with the real values for your SaaS.
  Delete this comment block when you're done.
-->

# {{SME_NAME}} API — auth and patterns

Reference for the cross-cutting bits of the {{SME_NAME}} HTTP API: where the
base URL points, how requests are authenticated, how pagination works,
and what an error response looks like.

## Base URL

Read from the `{{ENV_PREFIX}}_URL` env var. Examples:

- Production: `https://api.{{example}}.com`
- Staging: `https://staging.api.{{example}}.com`

All paths in this doc set are relative to that base URL.

## Auth

Every request carries:

| Header | Source | Notes |
| --- | --- | --- |
| `Authorization: Bearer <token>` | `{{ENV_PREFIX}}_API_KEY` | The SaaS's API token. |
| `X-Agent-Role` | `AGENT_ROLE` env var | Caller's role slug; used by upstream audit. |
| `X-Agent-UID` | `AGENT_UID` env var | This agent's UUID; used by upstream audit. |

The two `X-Agent-*` headers are sent unconditionally — they're a no-op
if the upstream doesn't enforce them.

## Pagination

*(Document the upstream's pagination model here. Common shapes:)*

- **Cursor-based.** Response includes `next_cursor`; pass it as
  `?cursor=<value>` on the next call. Stop when the field is null.
- **Offset/limit.** Pass `?limit=<n>&offset=<n>`. Server caps `limit`
  at *N*; if you need more, loop.
- **Page/per_page.** Pass `?page=<n>&per_page=<n>`. Response includes
  `total_pages`.

Whichever model applies, the tool layer should hide it from the agent
— functions in `tools.py` return the full collection (subject to the
`max_rows_per_call` policy).

## Error shape

Non-2xx responses look like:

```json
{
  "error": "human-readable message",
  "code": "machine_readable_slug",
  "request_id": "req_abc123"
}
```

The `client.py` `_request` helper extracts `error` and raises it as
`{{SME_Name}}APIError`. Surface the message verbatim when relaying back
to the caller; never invent a friendlier version.

## Rate limits

*(Document the upstream's rate limit policy here. e.g. "100 req/min per
API key, returns HTTP 429 with `Retry-After` header.")*
