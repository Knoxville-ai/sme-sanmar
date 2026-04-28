"""SanMar-focused HTTP client used by the SME tool layer.

This client intentionally keeps endpoint interactions thin and predictable
for LLM-driven tool calls. Methods map to common integration actions:

- product queries
- inventory checks
- pricing checks
- purchase order submit
- order/tracking/shipping status lookup
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
        super().__init__(f"SanMar API error {status}: {body[:300]}")


class ExampleClient:
    """HTTP client for the SanMar SME integration surface."""

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
                "SanMar SME not configured. Set EXAMPLE_URL and EXAMPLE_API_KEY env vars."
            )
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._agent_role = agent_role or None
        self._agent_uid = agent_uid or None
        self._dry_run = dry_run
        self._timeout = timeout
        self._session = requests.Session()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._agent_role:
            headers["X-Agent-Role"] = self._agent_role
        if self._agent_uid:
            headers["X-Agent-UID"] = self._agent_uid
        self._session.headers.update(headers)

    @property
    def dry_run(self) -> bool:
        return self._dry_run

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
            return {
                "dry_run": True,
                "method": method.upper(),
                "path": path,
                "params": params,
                "json_body": json_body,
            }

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
                err_msg = body.get("error") or body.get("message") or resp.text
            except ValueError:
                err_msg = resp.text
            raise ExampleAPIError(resp.status_code, err_msg)

        if not resp.text.strip():
            return {"status": "ok"}

        try:
            payload = resp.json()
        except ValueError as exc:
            raise ExampleAPIError(
                resp.status_code, f"Non-JSON response: {resp.text[:200]}"
            ) from exc

        if isinstance(payload, dict):
            return payload
        return {"items": payload}

    @staticmethod
    def _compact_params(raw: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in raw.items() if v is not None and v != ""}

    # ---- SanMar common actions ----

    def query_products(
        self,
        *,
        style: str | None = None,
        color: str | None = None,
        size: str | None = None,
        brand: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params = self._compact_params(
            {
                "style": style,
                "color": color,
                "size": size,
                "brand": brand,
                "category": category,
                "limit": limit,
            }
        )
        return self._request("GET", "/sanmar/products", params=params)

    def check_inventory(
        self,
        *,
        style: str,
        color: str | None = None,
        size: str | None = None,
        warehouse: str | None = None,
    ) -> dict[str, Any]:
        params = self._compact_params(
            {
                "style": style,
                "color": color,
                "size": size,
                "warehouse": warehouse,
            }
        )
        return self._request("GET", "/sanmar/inventory", params=params)

    def check_pricing(
        self,
        *,
        style: str,
        color: str | None = None,
        size: str | None = None,
        quantity: int | None = None,
    ) -> dict[str, Any]:
        params = self._compact_params(
            {
                "style": style,
                "color": color,
                "size": size,
                "quantity": quantity,
            }
        )
        return self._request("GET", "/sanmar/pricing", params=params)

    def submit_purchase_order(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/sanmar/purchase-orders", json_body=payload)

    def get_order_status(
        self,
        *,
        po_number: str | None = None,
        sanmar_order_number: str | None = None,
    ) -> dict[str, Any]:
        params = self._compact_params(
            {
                "po_number": po_number,
                "sanmar_order_number": sanmar_order_number,
            }
        )
        return self._request("GET", "/sanmar/orders/status", params=params)

    def get_shipping_status(
        self,
        *,
        po_number: str | None = None,
        sanmar_order_number: str | None = None,
    ) -> dict[str, Any]:
        params = self._compact_params(
            {
                "po_number": po_number,
                "sanmar_order_number": sanmar_order_number,
            }
        )
        return self._request("GET", "/sanmar/orders/shipping-status", params=params)

    def get_tracking(
        self,
        *,
        po_number: str | None = None,
        sanmar_order_number: str | None = None,
        tracking_number: str | None = None,
    ) -> dict[str, Any]:
        params = self._compact_params(
            {
                "po_number": po_number,
                "sanmar_order_number": sanmar_order_number,
                "tracking_number": tracking_number,
            }
        )
        return self._request("GET", "/sanmar/orders/tracking", params=params)


def example_client_from_env() -> ExampleClient:
    """Create an ExampleClient from environment variables.

    Required:
      EXAMPLE_URL      — integration base URL
      EXAMPLE_API_KEY  — auth token

    Optional:
      AGENT_ROLE       — caller role slug
      AGENT_UID        — this agent's UUID
      EXAMPLE_DRY_RUN  — if true, returns write intent without making writes
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
