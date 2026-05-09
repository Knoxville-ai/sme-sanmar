"""Structured tool-result type returned by every sanmar_returns tool.

Tools never raise to the caller; they always return a ``ToolResult`` so
the calling agent can branch on ``success`` and surface a screenshot
when present.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Uniform return shape for every tool function in this skill.

    Attributes
    ----------
    success:
        ``True`` if the tool completed its intended action. ``False`` for
        any failure mode (timeout, missing element, validation error,
        unexpected page state).
    observation:
        Short human-readable string the agent can quote back to the
        user. Always populated. On failure, describes what went wrong
        and which step it happened at.
    data:
        Optional structured payload (RMA number, order rows, extracted
        fields). Schema is per-tool; see each tool's docstring.
    screenshot:
        Optional base64-encoded PNG of the page at the moment the tool
        returned. Populated on every failure and optionally on success
        when ``include_screenshot=True`` is passed to the tool.
    """

    success: bool
    observation: str
    data: dict[str, Any] | None = None
    screenshot: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def encode_screenshot(png_bytes: bytes) -> str:
        return base64.b64encode(png_bytes).decode("ascii")
