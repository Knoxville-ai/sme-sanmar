"""OpenClaw skill entrypoints for the Example SME.

Thin wrappers the agent's LLM can invoke as tools. Each function takes
simple scalar / JSON args, calls into the domain modules
(:mod:`sme_tools.example.client` and any per-domain helpers you add), and
returns a JSON-serializable result.

Implementation rules:
  - One public function per tool. No classes.
  - Arguments must be scalars, lists, or dicts of scalars (LLM-friendly).
  - Return a JSON-serializable value (dict / list / scalar). Never a
    bare dataclass instance — convert with ``dataclasses.asdict`` first.
  - Log every call with the inputs and a count of items returned.
  - Catch domain errors at this layer and re-raise as plain exceptions
    with a short, caller-facing message.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any

from sme_tools.example.client import example_client_from_env

logger = logging.getLogger(__name__)


def _to_json(value: Any) -> Any:
    """Recursively convert dataclasses to dicts for JSON serialization."""
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _to_json(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [_to_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_json(v) for k, v in value.items()}
    return value


# ── reference implementation ──────────────────────────────────────


def ping() -> dict[str, Any]:
    """Connectivity check against the upstream API.

    Reference implementation showing the full pattern: build a client
    from env, make a single call, log, return JSON. Replace with real
    tools as you wire up the SME.
    """
    client = example_client_from_env()
    result = client.ping()
    logger.info("ping -> %s", result)
    return _to_json(result)


# ── stubs ────────────────────────────────────────────────────
#
# Add one stub per planned tool. Each stub should:
#   - Have a docstring describing the contract (args, return shape).
#   - Raise NotImplementedError with a one-line note pointing at the
#     module/method that should back it.
# Fill them in as downstream task-agent callers come online.


def list_records(filter_by: str | None = None) -> list[dict[str, Any]]:
    """List records from the upstream SaaS, optionally filtered.

    TODO: wire to ``sme_tools.example.client.ExampleClient.list_records``.
    """
    raise NotImplementedError(
        "list_records: call ExampleClient.list_records(filter_by=filter_by)"
    )


def create_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a record in the upstream SaaS.

    TODO: wire to ``sme_tools.example.client.ExampleClient.create_record``.
    Respect the ``allow_writes`` and ``dry_run`` policies before calling.
    """
    raise NotImplementedError(
        "create_record: call ExampleClient.create_record(payload=payload)"
    )
