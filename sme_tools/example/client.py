"""HTTP client skeleton for the Example SME.

Replace ``Example`` with your SaaS name everywhere. The pattern below is
the contract every Class 2 SME's domain client should follow:

  - Constructor takes credentials + a ``dry_run`` flag.
  - Optional ``agent_role`` / ``agent_uid`` headers ride along on every
    request so the upstream API can audit which agent acted.
  - Two error classes: ``*ConnectionError`` for transport failures and
    ``*APIError`` for non-2xx responses.
  - A ``_request`` helper centralises retries, error parsing, and the
    dry-run short-circuit.
  - A module-level ``*_client_from_env()`` factory reads the env vars
    that the deploy manifest sets at container start.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


class ExampleConnectionError(RuntimeError):
    """Raised when the upstream API is unreachable or misconfigured."""


class ExampleAPIError(RuntimeError):
    """Raised when the upstream API returns an error response."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"Example API error {status}: {body[:300]}")


class ExampleClient:
    """HTTP client for the Example SaaS API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        agent_role: str | None = None,
        agent_uid: str | None = None,
        dry_run: bool = False,
        timeout: int = 30,
    ) -> None:
        if not base_url or not api_key:
            raise ExampleConnectionError(
                "Example SME not configured. Set EXAMPLE_URL and EXAMPLE_API_KEY env vars."
            )
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._agent_role = agent_role or None
        self._agent_uid = agent_uid or None
        self._dry_run = dry_run
        self._timeout = timeout
        self._session = requests.Session()
        headers = {
            # Most SaaS APIs use either Bearer or a custom header. Pick
            # whichever is correct for your upstream and delete the other.
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # Identity headers: harmless when the upstream doesn't enforce
        # them, required when it does. Send them unconditionally.
        if self._agent_role:
            headers["X-Agent-Role"] = self._agent_role
        if self._agent_uid:
            headers["X-Agent-UID"] = self._agent_uid
        self._session.headers.update(headers)

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    # ── generic request ───────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"

        if self._dry_run and method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            logger.info("[DRY RUN] %s %s body=%s", method.upper(), url, json_body)
            return {"dry_run": True}

        try:
            resp = self._session.request(
                method.upper(),
                url,
                params=params,
                json=json_body,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise ExampleConnectionError(f"Request to {url} failed: {exc}") from exc

        if resp.status_code == 401:
            raise ExampleAPIError(401, "Unauthorized — check EXAMPLE_API_KEY")

        if not resp.ok:
            try:
                body = resp.json()
                err_msg = body.get("error", resp.text)
            except ValueError:
                err_msg = resp.text
            raise ExampleAPIError(resp.status_code, err_msg)

        try:
            return resp.json()
        except ValueError:
            raise ExampleAPIError(
                resp.status_code, f"Non-JSON response: {resp.text[:200]}"
            )

    # ── domain methods ───────────────────────────────────
    #
    # Add one method per upstream endpoint your tools.py needs. Keep them
    # thin: parse args, call _request, return a typed dict / dataclass.

    def ping(self) -> dict[str, Any]:
        """Simple connectivity check — replace with a real endpoint."""
        return self._request("GET", "/ping")


# ── factory ───────────────────────────────────────────


def example_client_from_env() -> ExampleClient:
    """Create an ExampleClient from environment variables.

    Required:
      EXAMPLE_URL      — base URL (e.g. https://api.example.com)
      EXAMPLE_API_KEY  — auth token

    Recommended (used to satisfy upstream role/uid audit):
      AGENT_ROLE       — caller role slug. Should match the role this SME
                         was provisioned under (e.g. ``example_sme``).
      AGENT_UID        — this agent's UUID. Surfaced in upstream logs.

    Optional:
      EXAMPLE_DRY_RUN  — if 'true', log write intent without calling the API.
    """
    base_url = os.getenv("EXAMPLE_URL", "").strip()
    api_key = os.getenv("EXAMPLE_API_KEY", "").strip()
    agent_role = os.getenv("AGENT_ROLE", "").strip() or None
    agent_uid = os.getenv("AGENT_UID", "").strip() or None
    dry_run = os.getenv("EXAMPLE_DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    return ExampleClient(
        base_url=base_url,
        api_key=api_key,
        agent_role=agent_role,
        agent_uid=agent_uid,
        dry_run=dry_run,
    )
