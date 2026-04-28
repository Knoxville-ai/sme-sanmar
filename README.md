# sme-template

**Baseline scaffold for Class 2 SME agents on the Knoxville AI platform.**

A Class 2 SME is a hyper-focused agent that speaks exactly one SaaS API.
It does not drive end-to-end business playbooks. It is called by Class 1
task agents (production scheduling, sales, AP, etc.) when they need data
from — or want to write changes into — a specific upstream system.

This repo is a fully working skeleton: fork it, run a handful of
search-and-replaces, fill in your domain code, and you have a deployable
SME. All the cross-cutting machinery (Docker base image, GHCR build &
publish, console redeploy webhook, role bootstrap, messaging endpoint,
JWT auth, Supabase sync) is inherited from
[`agent-core`](https://github.com/knoxville-ai/agent-core) and needs
no changes here.

---

## How a Class 2 SME fits together

- Inherits from `ghcr.io/knoxville-ai/agent-core:0.2` — supervisord,
  OpenClaw gateway, Flask messaging API, JWT auth, Supabase sync, and
  role bootstrap are all baked in. Pinned to the minor (`:0.2`) so
  patch-level agent-core releases flow in on the next rebuild without
  edits here; bumps to `:0.3` / `:1.0` are explicit.
- Adds three things on top of that base:
  - **`sme_tools/<domain>/`** — the Python domain layer: HTTP client(s),
    helpers, and the OpenClaw skill entrypoints in `tools.py`.
  - **`roles/<slug>/`** — the role definition (system prompt, identity,
    boot, playbook template, policies + schema).
  - **`api_docs/`** — markdown reference the role's playbook reads
    before calling any tool.
- Disables `OLLAMA_ENABLED` and `REMBG_ENABLED` — SMEs don't run local
  LLM inference or background-removal.

Incoming traffic: task agents call this SME over the Supabase
conversation pipe; the Flask endpoint
`/api/v1/conversations/<id>/messages` (provided by `agent_core.messaging`)
validates an agent-service JWT, checks `public.agent_connections`, and
hands the request to the local OpenClaw gateway.

---

## Repo layout

```
.
├── Dockerfile                     # inherits agent-core, copies repo + roles, sets ENV
├── pyproject.toml                 # `sme-<slug>` package; rename on fork
├── .github/workflows/docker.yml   # build + push to GHCR; ping console webhook
├── .gitignore  .dockerignore
├── api_docs/                      # markdown reference the LLM reads at runtime
│   ├── README.md                  # how to write API docs
│   └── auth_and_patterns.md       # cross-cutting reference (template)
├── roles/
│   └── example_sme/               # the role; rename to <your_slug>_sme
│       ├── VERSION                # bump when policy/prompt schema changes
│       ├── identity.md            # who I am
│       ├── boot.md                # what I should know on first turn
│       ├── system_prompt.md       # durable instructions (most important file)
│       ├── playbook_template.md   # seeded into mutable workspace state
│       ├── default_policies.json  # dry_run / max_rows / allow_writes
│       └── policy_schema.json     # JSON-Schema validating the above
└── sme_tools/                     # importable as `sme_tools.*` inside the container
    ├── __init__.py
    └── example/                   # one package per SaaS domain; rename
        ├── __init__.py            # re-exports the public client surface
        ├── client.py              # HTTP client (skeleton, ready to fill in)
        └── tools.py               # OpenClaw skill entrypoints
```

---

## Quickstart: spinning up a new SME from this template

The template ships with a working "example" placeholder so the repo
builds cleanly out of the box. Replacing it with your real SME is
mechanical:

### 1. Fork the repo

Create `knoxville-ai/sme-<your_slug>` from this template (use GitHub's
"Use this template" button, or `gh repo create --template`). The image
in the GH workflow auto-derives from the repo name, so no edit needed
there.

Pick a short, lowercase slug — `salesforce`, `stripe`, `hubspot`,
`zendesk`. The same slug is used throughout.

### 2. Rename the package

```bash
SLUG=salesforce              # your slug
NAME="Salesforce"            # human name
ROLE="${SLUG}_sme"           # role slug (matches Knoxville console)

git mv sme_tools/example "sme_tools/${SLUG}"
git mv "roles/example_sme" "roles/${ROLE}"
```

### 3. Find-and-replace placeholders

Inside `roles/${ROLE}/*.md` and `api_docs/*.md`, replace:

| Placeholder | Example value | Notes |
| --- | --- | --- |
| `{{SME_NAME}}` | `Salesforce` | Human-readable name. |
| `{{sme_slug}}` | `salesforce` | Lowercase slug; matches the `sme_tools/<slug>/` directory. |
| `{{ENV_PREFIX}}` | `SALESFORCE` | Prefix for env vars (`SALESFORCE_URL`, `SALESFORCE_API_KEY`). |
| `{{EXAMPLE_CALLER_*}}` | `production_scheduler` | Names of the task agents that will call this SME. |
| `{{DOMAIN_*}}` / `{{module_*}}` / `{{doc_*}}` | per your repo | The domains your SME exposes. |

Inside `sme_tools/${SLUG}/`, do a case-sensitive rename of `Example` →
`<YourName>` and `example` → `<your_slug>` across `client.py`, `tools.py`,
and `__init__.py`. The class names should follow the pattern:
`<Name>Client`, `<Name>APIError`, `<Name>ConnectionError`,
`<name>_client_from_env()`.

In `pyproject.toml`, set `name = "sme-<slug>"`.

In `roles/${ROLE}/policy_schema.json`, update `title` to match.

### 4. Fill in the domain code

This is the only non-mechanical step. See *Where SME-specific code goes*
below.

### 5. Push to `main`

The `docker.yml` workflow will:

1. Build `ghcr.io/knoxville-ai/sme-<slug>:latest` on every push to `main`.
2. Tag `vX.Y.Z` builds when you push a `v*` git tag.
3. Ping the console's `/api/internal/sme-rebuilt` webhook so every
   active Railway service tied to this repo redeploys automatically.

No manual Railway clicks. No console UI work for the rebuild itself —
that only matters for first-time provisioning (next section).

### 6. Provision in the console

Once the image is published:

1. **Roles → New role** — create your role with:
   - `kind = sme`
   - `capability_tag = <slug>`
   - `source_repo = knoxville-ai/sme-<slug>`
2. **Agents → Provision** — pick the role and the target org. The
   console writes the Supabase rows, mints the agent-service JWT
   secret, and kicks the first Railway deploy.
3. **Connections** — allowlist the task agents that should be permitted
   to call this SME (rows in `public.agent_connections`).

---

## Where SME-specific code goes

Three places, in the order you'll typically touch them:

### `sme_tools/<slug>/` — the Python domain layer

Where the upstream API actually gets called.

- **`client.py`** — HTTP client. The skeleton in `sme_tools/example/client.py`
  shows the contract: env-driven config, `dry_run` flag, `_request`
  helper that handles errors uniformly, identity headers
  (`X-Agent-Role` / `X-Agent-UID`) on every call, a `*_from_env()`
  factory. Add one method per upstream endpoint you need to hit.
- **Per-domain modules** — split out as the surface grows. sme-odoo
  ended up with `mrp.py`, `inventory.py`, `ap_client.py` alongside
  the base `client.py`. Same pattern works for any SaaS — group by
  upstream module.
- **`tools.py`** — OpenClaw skill entrypoints. **One public function
  per tool the LLM can call.** Rules:
  - Arguments are scalars / lists / dicts of scalars (LLM-friendly).
  - Return JSON-serializable values (use the `_to_json` helper to
    flatten dataclasses).
  - Catch domain errors at this layer.
  - Stub un-built tools with `NotImplementedError` and a one-line
    comment pointing at the method that should back it. This keeps
    the surface visible to callers without forcing premature
    implementation.

### `roles/<slug>_sme/` — the role definition

What the LLM sees on every turn. Read top-to-bottom by `agent-core`'s
bootstrap and seeded into the OpenClaw workspace.

- **`identity.md`** — first-person blurb, 3–6 sentences. Establishes
  scope (one SaaS, called by other agents only).
- **`boot.md`** — what to know on first turn. Where docs live, which
  modules exist, that `sender_kind` is always `agent`.
- **`system_prompt.md`** — *the* durable instruction set. Concrete and
  rule-based. Covers: who calls this SME, which tools to use,
  clarification protocol, response format, workflow per request,
  policies. This is the single highest-leverage file in the repo.
- **`playbook_template.md`** — seeded into the workspace as
  `playbook.md` on first boot, then **mutable** at runtime. The agent
  appends learnings here. The role files in this repo never change at
  runtime.
- **`default_policies.json`** — runtime policies (`dry_run`,
  `max_rows_per_call`, `allow_writes`). Validated against
  `policy_schema.json` on boot. Operators override per-deploy via the
  console.
- **`policy_schema.json`** — JSON-Schema describing the policy shape.
  Update when you add new policy keys.
- **`VERSION`** — integer. Bump on any breaking change to the role
  shape (added/removed policy key, changed prompt contract). The
  console reads this to decide whether re-provisioning is needed.

### `api_docs/` — markdown reference for the LLM at runtime

Short, concrete, code-sample-heavy pages. Audience is the LLM, not
humans. Pattern your file set as one cross-cutting page
(`auth_and_patterns.md`) plus one page per upstream module the SME
exposes. The agent's playbook explicitly tells it to open the relevant
page before calling any tool — these docs encode the gotchas the tool
layer doesn't hide.

See `api_docs/README.md` for the style guide.

---

## Build locally

```bash
docker build -t sme-<slug>:dev .
```

The base image is public on GHCR, so no `docker login` is needed for
local builds. `OLLAMA_ENABLED=false` and `REMBG_ENABLED=false` are baked
in by the Dockerfile — no env file needed at build time.

---

## Runtime env vars

These come from the console's deploy manifest, not from a local `.env`.

### Inherited from `agent-core` (set the same on every SME)

| Var | Purpose |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key for the messaging pipe |
| `SUPABASE_JWT_SECRET` | Shared secret used to verify agent-service JWTs |
| `AGENT_ORG` | Tenant/organization id |
| `AGENT_UID` | This agent's UUID (from the console) |
| `AGENT_ROLE` | This SME's role slug (must match `roles/<slug>_sme/`) |
| `LLM_PROVIDER` | `anthropic`, `openai`, etc. — picks the OpenClaw LLM |
| `LLM_MODEL` | Model id for the chosen provider |
| `LLM_API_KEY` | API key for the chosen provider |

### SME-specific (defined by you)

Convention: prefix with the upstream's name. The example client uses
`EXAMPLE_URL`, `EXAMPLE_API_KEY`, `EXAMPLE_DRY_RUN`. Match that pattern
— a Stripe SME would expose `STRIPE_URL`, `STRIPE_API_KEY`,
`STRIPE_DRY_RUN`. Document them all in this README under a "Runtime env
vars" section so the operator provisioning the agent in the console
knows what to fill in.

---

## Versioning and the `agent-core` contract

- The `FROM ghcr.io/knoxville-ai/agent-core:0.2` line in the Dockerfile
  pins to the **minor** version. Patch releases of agent-core flow in
  automatically on the next image rebuild (the agent-core release
  workflow dispatches every downstream SME repo's `docker.yml`).
- Bump to `:0.3` / `:1.0` explicitly when a minor or major lands —
  those are the changes likely to break the SME contract.
- Tag this repo's releases with `v0.1.0`, `v0.2.0`, etc. The
  console can pin Railway services to a specific tag if you need
  one SME held back from `:latest`.

---

## Phase context

This template is part of **Phase 2** of the SME architecture rollout:

- Phase 1: `agent-core` publishes a shared runtime and messaging API.
- **Phase 2: stand up Class 2 SMEs (one repo per SaaS, this template).**
- Phase 3: remove per-SaaS code from `agent-core` once all callers have
  switched to `agent_core.messaging.ask_sme`.

The first concrete instance of this template in production is
[`sme-odoo`](https://github.com/knoxville-ai/sme-odoo) — read it
alongside this template if you want to see what a fully fleshed-out
SME looks like.
