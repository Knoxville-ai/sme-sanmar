"""SanMar returns automation skill (Playwright-based).

See SKILL.md for the full agent-facing contract. The public surface is
the tool functions re-exported here:

    from skills.sanmar_returns import (
        login,
        find_order,
        initiate_return,
        fill_return_form,
        submit_return,
        take_screenshot,
        run_raw_playwright,
    )
"""

from skills.sanmar_returns.tools.return_tools import (
    fill_return_form,
    find_order,
    initiate_return,
    login,
    run_raw_playwright,
    submit_return,
    take_screenshot,
)
from skills.sanmar_returns.tools.result import ToolResult

__all__ = [
    "ToolResult",
    "fill_return_form",
    "find_order",
    "initiate_return",
    "login",
    "run_raw_playwright",
    "submit_return",
    "take_screenshot",
]
