# sme-sanmar

Class 2 SME agent repository for **SanMar API integrations** on the Knoxville AI platform.

This agent is intentionally narrow in scope:

- SanMar SOAP web services
- SanMar FTP product/inventory/pricing/invoice feeds
- SanMar purchase-order integration workflows

It is designed to be called by other task agents and return structured, reliable SanMar-specific outputs.

## Repository focus

- `skills/sanmar/` is the canonical home for everything SanMar:
  the skill contract (`SKILL.md`), tool catalog (`sanmar_tools.py`,
  `tools.json`), typed schemas (`schemas.py`), the SOAP/PromoStandards
  client (`sanmar_client.py`), the PDF PO parser (`pdf_parser.py`),
  the SDL FTP color resolver (`ftp_resolver.py`), worked examples
  (`examples.md`), and tests.
- `api_docs/` contains the SanMar integration reference documentation
  the agent reads before tool calls (auth, web services, FTP feeds,
  purchase orders).
- `roles/example_sme/` contains the role instructions that boot the
  agent into the SanMar SME mission and point it at `skills/sanmar/`.

## Runtime expectations

- Agent handles only `sender_kind=agent` traffic.
- Tool calls should be grounded in `api_docs/*.md`.
- Write operations (especially PO submission) must enforce clarification and policy checks.

## Source references

Primary SanMar reference PDFs are retained in `api_docs/` for traceability and future doc updates.
