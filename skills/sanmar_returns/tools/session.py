"""Browser session lifecycle for the sanmar_returns skill.

A single Playwright browser/context/page tuple is held at module scope
and reused across tool calls. Storage state (cookies + localStorage) is
persisted to disk so a re-invocation of the skill in the same container
can resume an authenticated session without re-logging-in.

Configuration via environment (operational only — never credentials):

* ``SANMAR_RETURNS_STORAGE_STATE`` — path to the storage_state JSON file.
  Default: ``/tmp/sanmar-returns-storage.json``.
* ``SANMAR_RETURNS_HEADLESS`` — ``"0"`` to run with a visible browser
  for local debugging. Default: headless.
* ``SANMAR_RETURNS_TIMEOUT_MS`` — default per-action timeout in ms.
  Default: ``15000``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

logger = logging.getLogger("sanmar_returns")

DEFAULT_STORAGE_STATE = "/tmp/sanmar-returns-storage.json"
DEFAULT_TIMEOUT_MS = 15_000


class BrowserSession:
    """Module-level singleton wrapping a Playwright browser+page.

    Tools call ``BrowserSession.get()`` to obtain the live session and
    interact with ``session.page``. ``BrowserSession.peek()`` returns
    the singleton if already initialised (used by the retry decorator
    to capture a screenshot without forcing browser startup on cleanup
    paths).
    """

    _instance: Optional["BrowserSession"] = None

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self.storage_state_path = Path(
            os.environ.get("SANMAR_RETURNS_STORAGE_STATE", DEFAULT_STORAGE_STATE)
        )
        self.headless = os.environ.get("SANMAR_RETURNS_HEADLESS", "1") != "0"
        self.default_timeout_ms = int(
            os.environ.get("SANMAR_RETURNS_TIMEOUT_MS", DEFAULT_TIMEOUT_MS)
        )

    @classmethod
    def get(cls) -> "BrowserSession":
        if cls._instance is None:
            cls._instance = cls()
        cls._instance._ensure_started()
        return cls._instance

    @classmethod
    def peek(cls) -> Optional["BrowserSession"]:
        if cls._instance is None or cls._instance._page is None:
            return None
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        if cls._instance is not None:
            cls._instance._teardown()
            cls._instance = None

    @property
    def page(self) -> Page:
        assert self._page is not None, "BrowserSession not started"
        return self._page

    @property
    def context(self) -> BrowserContext:
        assert self._context is not None, "BrowserSession not started"
        return self._context

    def save_storage_state(self) -> None:
        """Persist cookies + localStorage to disk for session reuse."""
        if self._context is None:
            return
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(self.storage_state_path))
        logger.info(
            "session.storage_saved",
            extra={"path": str(self.storage_state_path)},
        )

    def _ensure_started(self) -> None:
        if self._page is not None:
            return
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        context_kwargs: dict = {}
        if self.storage_state_path.exists():
            context_kwargs["storage_state"] = str(self.storage_state_path)
            logger.info(
                "session.storage_loaded",
                extra={"path": str(self.storage_state_path)},
            )
        self._context = self._browser.new_context(**context_kwargs)
        self._context.set_default_timeout(self.default_timeout_ms)
        self._page = self._context.new_page()
        logger.info(
            "session.started",
            extra={
                "headless": self.headless,
                "timeout_ms": self.default_timeout_ms,
            },
        )

    def _teardown(self) -> None:
        try:
            if self._context is not None:
                try:
                    self.save_storage_state()
                except Exception:
                    pass
                self._context.close()
            if self._browser is not None:
                self._browser.close()
            if self._playwright is not None:
                self._playwright.stop()
        finally:
            self._playwright = None
            self._browser = None
            self._context = None
            self._page = None
