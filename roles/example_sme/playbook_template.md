<!--
  PLAYBOOK TEMPLATE — seeded into the workspace as `playbook.md` on first
  boot. Becomes mutable state thereafter; the agent appends learnings as
  it discovers them. The role files in this repo are immutable at runtime.
  Replace every `{{...}}` placeholder, then delete this comment block.
-->

# Playbook — {{SME_NAME}} SME

This file is seeded into `/root/.openclaw/workspace/playbook.md` on first boot
and becomes mutable state thereafter. Append notes as you learn things; never
edit the immutable role files.

## Default request loop

For every inbound message:

1. **Validate sender.** If `sender_kind != "agent"`, refuse with a short
   error. SMEs only talk to other agents.
2. **Pick the domain.** Map the request to one of:
   - {{DOMAIN_1}} → `sme_tools.{{sme_slug}}.{{module_1}}` + `api_docs/{{doc_1}}.md`
   - {{DOMAIN_2}} → `sme_tools.{{sme_slug}}.{{module_2}}` + `api_docs/{{doc_2}}.md`
   - Anything else → `sme_tools.{{sme_slug}}.client` + `api_docs/auth_and_patterns.md`
3. **Read the matching API doc.** Even if you think you remember the shape,
   re-check the doc for gotchas (timezones, state names, pagination).
4. **Check for ambiguity.** If any required argument is missing or
   underspecified, reply with:
   ```json
   {"status": "needs_clarification", "question": "..."}
   ```
   and stop. Don't guess.
5. **Call the tool.** Use `sme_tools.{{sme_slug}}.tools.*` — do not bypass.
6. **Format the response.** Structured JSON for data; short prose for
   explanations or errors. Respect `max_rows_per_call`.
7. **Record gotchas.** If you hit an unexpected 4xx, discover a caller
   convention, or learn a column-rename, append it under *Learnings* below.

## Learnings

*(Append dated notes here as you discover them. Example:)*

<!--
## YYYY-MM-DD — caller_name
The caller_name task agent always passes `due_by` as YYYY-MM-DD in
America/Chicago. Normalize to UTC ISO 8601 before comparing.
-->
