"""Retry decorator for Playwright-backed tool functions.

Catches Playwright's ``TimeoutError`` (raised when a selector or
navigation wait exceeds its budget) and any subclass of the generic
``PlaywrightError``, retries with exponential backoff, and on final
failure produces a ``ToolResult`` carrying a screenshot of the page in
its broken state.
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from skills.sanmar_returns.tools.result import ToolResult
from skills.sanmar_returns.tools.session import BrowserSession

logger = logging.getLogger("sanmar_returns")


def with_retry(
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> Callable[[Callable[..., ToolResult]], Callable[..., ToolResult]]:
    """Wrap a tool function with retry + screenshot-on-failure semantics.

    On each failed attempt the page is screenshotted and the failure is
    logged. If all attempts fail the most recent screenshot is attached
    to the returned ``ToolResult``. Backoff is ``base_delay * 2**(n-1)``.
    """

    def decorator(fn: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> ToolResult:
            tool_name = fn.__name__
            last_screenshot: str | None = None
            last_error: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                t0 = time.monotonic()
                try:
                    result = fn(*args, **kwargs)
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    logger.info(
                        "tool.complete",
                        extra={
                            "tool": tool_name,
                            "attempt": attempt,
                            "duration_ms": duration_ms,
                            "success": result.success,
                        },
                    )
                    return result
                except (PlaywrightTimeoutError, PlaywrightError) as exc:
                    last_error = exc
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    last_screenshot = _safe_screenshot()
                    logger.warning(
                        "tool.attempt_failed",
                        extra={
                            "tool": tool_name,
                            "attempt": attempt,
                            "duration_ms": duration_ms,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                    )
                    if attempt < max_attempts:
                        delay = base_delay * (2 ** (attempt - 1))
                        time.sleep(delay)
                        continue
            return ToolResult(
                success=False,
                observation=(
                    f"{tool_name} failed after {max_attempts} attempts: "
                    f"{type(last_error).__name__}: {last_error}"
                ),
                screenshot=last_screenshot,
                metadata={"tool": tool_name, "attempts": max_attempts},
            )

        return wrapper

    return decorator


def _safe_screenshot() -> str | None:
    """Best-effort screenshot capture; never raises."""
    try:
        session = BrowserSession.peek()
        if session is None:
            return None
        png = session.page.screenshot(full_page=True)
        return ToolResult.encode_screenshot(png)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("screenshot.failed", extra={"error": str(exc)})
        return None
