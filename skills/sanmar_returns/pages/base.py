"""BasePage — small mixin of helpers shared by every page object.

Page objects encapsulate selectors and interactions for a single page
of sanmar.com. They never call ``time.sleep()``; every wait is explicit
(``wait_for_url``, ``locator.wait_for``).
"""

from __future__ import annotations

import logging
from typing import Any

from playwright.sync_api import Page

logger = logging.getLogger("sanmar_returns")


class BasePage:
    """Common scaffolding for page objects."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def _log(self, action: str, **fields: Any) -> None:
        """Structured log helper. Never logs credential fields."""
        safe = {k: v for k, v in fields.items() if k not in {"username", "password"}}
        logger.info(action, extra={"page": type(self).__name__, **safe})
