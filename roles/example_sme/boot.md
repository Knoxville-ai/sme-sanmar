<!--
  BOOT — minimal "what to know on first turn" notes.
  Mention:
    - Where API docs live (`/app/api_docs/`)
    - Which tool modules are available
    - That sender_kind will always be `agent`
  Replace every `{{...}}` placeholder, then delete this comment block.
-->

# Boot

On first boot:

- API reference docs live at `/app/api_docs/`. Read the relevant page
  *before* calling any tool — each page documents models, query patterns,
  and gotchas the `sme_tools.{{sme_slug}}.*` layer doesn't hide.
- Available tool modules: `sme_tools.{{sme_slug}}.tools` (skill entrypoints),
  backed by `client.py` and any per-domain modules you add.
- You do not talk to users. Your only input channel is other agents;
  your `sender_kind` will be `agent` on every inbound message.
