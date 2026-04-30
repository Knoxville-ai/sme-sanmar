"""Env-var loading for the FTP credential helper."""

from __future__ import annotations

import pytest

from skills.sanmar.ftp_resolver import (
    SanMarFTPConfigError,
    ftp_credentials_from_env,
)


def test_credentials_loaded_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANMAR_FTP_USERNAME", "123456")
    monkeypatch.setenv("SANMAR_FTP_PASSWORD", "ftp-secret")
    monkeypatch.delenv("SANMAR_FTP_HOST", raising=False)
    monkeypatch.delenv("SANMAR_FTP_PORT", raising=False)

    creds = ftp_credentials_from_env()
    assert creds.username == "123456"
    assert creds.password == "ftp-secret"
    assert creds.host == "ftp.sanmar.com"
    assert creds.port == 2200


def test_username_falls_back_to_customer_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SANMAR_FTP_USERNAME", raising=False)
    monkeypatch.setenv("SANMAR_CUSTOMER_NUMBER", "654321")
    monkeypatch.setenv("SANMAR_FTP_PASSWORD", "p")

    creds = ftp_credentials_from_env()
    assert creds.username == "654321"


def test_missing_password_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANMAR_FTP_USERNAME", "123456")
    monkeypatch.delenv("SANMAR_FTP_PASSWORD", raising=False)

    with pytest.raises(SanMarFTPConfigError):
        ftp_credentials_from_env()


def test_invalid_port_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANMAR_FTP_USERNAME", "123456")
    monkeypatch.setenv("SANMAR_FTP_PASSWORD", "p")
    monkeypatch.setenv("SANMAR_FTP_PORT", "not-an-int")

    with pytest.raises(SanMarFTPConfigError):
        ftp_credentials_from_env()
