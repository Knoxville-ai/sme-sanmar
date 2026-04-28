# sme-sanmar

Class 2 SME agent repository for **SanMar API integrations** on the Knoxville AI platform.

This agent is intentionally narrow in scope:

- SanMar SOAP web services
- SanMar FTP product/inventory/pricing/invoice feeds
- SanMar purchase-order integration workflows

It is designed to be called by other task agents and return structured, reliable SanMar-specific outputs.

## Repository focus

- `api_docs/` contains the SanMar integration documentation used at runtime by the agent.
- `roles/example_sme/` contains role instructions now aligned to the SanMar SME mission.
- `sme_tools/example/` is the tool surface that should implement SanMar operations.

## Runtime expectations

- Agent handles only `sender_kind=agent` traffic.
- Tool calls should be grounded in `api_docs/*.md`.
- Write operations (especially PO submission) must enforce clarification and policy checks.

## Source references

Primary SanMar reference PDFs are retained in `api_docs/` for traceability and future doc updates.
