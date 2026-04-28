# SanMar SME API docs index

This directory contains runtime documentation for the **Class 2 SanMar SME agent**.

The SME must read the relevant page before tool execution. These docs are written for LLM/tooling correctness (not end-user marketing prose).

## Core markdown docs

- `auth_and_patterns.md` — cross-cutting onboarding, auth, endpoint, transport, and error patterns.
- `web_services.md` — SanMar SOAP web-services operations and response normalization guidance.
- `ftp_feeds.md` — FTP feed families, file conventions, join keys, and cadence expectations.
- `purchase_orders.md` — PO submission/validation workflow and operational safeguards.

## Source PDFs retained for traceability

- `SanMarWebServicesIntegrationGuide-v16.10.pdf`
- `SanMar-FTP-Integration-Guide-v23.1.pdf`
- `SanMar-FTP-Integration-Guide-v18 (4).pdf`
- `SanMar-Purchase-Order-Integration-Guide-24.1.pdf`

## Authoring standard for future updates

When new SanMar behavior is discovered:

1. Update the closest topical markdown file above.
2. Prefer concrete field names, operation names, and payload examples.
3. Document edge cases that can cause bad writes or silent data drift.
4. Keep this index aligned if a new domain markdown file is added.
