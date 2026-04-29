"""Shared fixtures and stub helpers for the SanMar skill tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from skills.sanmar.sanmar_client import SanMarClient
from skills.sanmar.schemas import SanMarCredentials


@dataclass
class StubResponse:
    text: str
    status_code: int = 200
    ok: bool = True


@dataclass
class StubSession:
    """Minimal stand-in for ``requests.Session`` used by the client."""

    response_text: str = ""
    status_code: int = 200
    raise_exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def post(
        self,
        url: str,
        data: bytes | str,
        headers: dict[str, str],
        timeout: int,
    ) -> StubResponse:
        self.calls.append(
            {"url": url, "data": data, "headers": headers, "timeout": timeout}
        )
        if self.raise_exc:
            raise self.raise_exc
        return StubResponse(
            text=self.response_text,
            status_code=self.status_code,
            ok=200 <= self.status_code < 400,
        )


@pytest.fixture
def credentials() -> SanMarCredentials:
    return SanMarCredentials(
        customer_number="123456",
        username="test_user",
        password="test_pass",
        environment="production",
    )


@pytest.fixture
def make_client(credentials):
    """Factory: build a SanMarClient backed by a StubSession.

    Returns ``(client, session)`` so tests can both invoke the client
    and inspect what was sent.
    """

    def _make(response_text: str = "", status_code: int = 200) -> tuple[SanMarClient, StubSession]:
        session = StubSession(response_text=response_text, status_code=status_code)
        client = SanMarClient(credentials=credentials, session=session)
        return client, session

    return _make
