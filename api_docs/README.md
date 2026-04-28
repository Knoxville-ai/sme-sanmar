# API reference — index

These docs are this SME's operator manual. The agent is instructed (in
its role's `system_prompt.md` and `playbook_template.md`) to open the
matching page **before** calling any tool. Keep them short, concrete,
and code-sample-heavy — the audience is the LLM, not humans.

## What goes in here

One markdown file per logical surface area of the upstream SaaS:

| Page | Covers |
| --- | --- |
| `auth_and_patterns.md` | Base URL, auth header, pagination, error shape, anything that applies across endpoints |
| `<domain>.md` | Per-domain reference — one file per upstream module the SME exposes (e.g. `customers.md`, `invoices.md`, `webhooks.md`) |

For sme-odoo this index ended up as `auth_and_patterns.md`,
`mrp_batches.md`, `stock_moves.md`, `invoices.md` — pattern your repo
the same way: one cross-cutting page plus one page per domain module
under `sme_tools/`.

## Style guide

- **Audience: the LLM.** Skip exposition; give it the facts it needs to
  call the API correctly on the first try.
- **Code samples > prose.** Show the request shape, the response shape,
  and one realistic example.
- **Document gotchas.** Pagination quirks, timezone defaults, state-name
  mismatches, soft-delete semantics — anything that has burned you once
  belongs here.
- **Don't document the tool layer.** The agent reads `sme_tools/*` source
  directly; these docs are for the underlying API.

## Updating

Whenever you (or the agent) learn a new gotcha that isn't covered, push
it as an edit to the relevant page. The agent's playbook is a *runtime*
scratchpad and resets on redeploy; these docs ship from the image and
are the durable source of truth.
