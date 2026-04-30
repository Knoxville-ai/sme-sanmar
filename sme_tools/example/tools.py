"""Tool-discovery entrypoint for the SanMar SME.

This module exists solely because agent-core's runtime introspects
``sme_tools.example.tools`` to register callables with the LLM. The
canonical implementations live in :mod:`skills.sanmar.sanmar_tools` —
this file just re-exports them so the runtime sees them.

**Do not add new logic here.** Add tools to
``skills.sanmar.sanmar_tools`` and re-export them below.

Tools surfaced to the agent:

- ``sanmar_search_products``         (read)
- ``sanmar_check_inventory``         (read; auto-resolves marketing
                                      colors via the SDL CSV)
- ``sanmar_get_pricing``             (read; same auto-resolve)
- ``sanmar_validate_cart``           (read)
- ``sanmar_create_purchase_order``   (HIGH-RISK external write)
- ``sanmar_check_order_status``      (read)
- ``sanmar_get_tracking``            (read)
- ``sanmar_cancel_order``            (stub — SanMar has no public
                                      cancel endpoint)
- ``sanmar_parse_po_pdf``            (read; PDF text extraction)
- ``sanmar_lookup_mainframe_color``  (read; SFTP into ftp.sanmar.com)

Refer to ``skills/sanmar/SKILL.md`` for the full skill contract,
credential policy, and usage examples.
"""

from skills.sanmar.sanmar_tools import (
    sanmar_cancel_order,
    sanmar_check_inventory,
    sanmar_check_order_status,
    sanmar_create_purchase_order,
    sanmar_get_pricing,
    sanmar_get_tracking,
    sanmar_lookup_mainframe_color,
    sanmar_parse_po_pdf,
    sanmar_search_products,
    sanmar_validate_cart,
)

__all__ = [
    "sanmar_cancel_order",
    "sanmar_check_inventory",
    "sanmar_check_order_status",
    "sanmar_create_purchase_order",
    "sanmar_get_pricing",
    "sanmar_get_tracking",
    "sanmar_lookup_mainframe_color",
    "sanmar_parse_po_pdf",
    "sanmar_search_products",
    "sanmar_validate_cart",
]
