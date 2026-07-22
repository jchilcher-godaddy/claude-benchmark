"""Tests for proxy cert-based JWT authentication."""

from __future__ import annotations

import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from claude_benchmark.execution.proxy_auth import (
    ProxyTokenManager,
    _parse_jwt_exp,
    is_proxy_configured,
    reset_token_manager,
    validate_proxy_env,
)


def _make_jwt(exp: float) -> str:
    """Create a minimal JWT with the given exp claim."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=")
    signature = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.{signature.decode()}"


class TestParseJwtExp:
    def test_valid_jwt(self):
        exp = time.time() + 3600
        token = _make_jwt(exp)
        assert _parse_jwt_exp(token) == exp

    def test_invalid_jwt(self):
        assert _parse_jwt_exp("not.a.jwt") is None
        assert _parse_jwt_exp("") is None
        assert _parse_jwt_exp("single") is None


class TestProxyTokenManager:
    def test_fetch_token(self):
        exp = time.time() + 3600
        token = _make_jwt(exp)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": token}
        mock_resp.raise_for_status = MagicMock()

        with patch("claude_benchmark.execution.proxy_auth.requests.post", return_value=mock_resp):
            mgr = ProxyTokenManager("/path/cert.crt", "/path/cert.key", "dev")
            result = mgr.get_token()
            assert result == token

    def test_caching(self):
        exp = time.time() + 3600
        token = _make_jwt(exp)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": token}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "claude_benchmark.execution.proxy_auth.requests.post", return_value=mock_resp
        ) as mock_post:
            mgr = ProxyTokenManager("/path/cert.crt", "/path/cert.key", "dev")
            mgr.get_token()
            mgr.get_token()
            assert mock_post.call_count == 1

    def test_refresh_on_expiry(self):
        expired_token = _make_jwt(time.time() - 100)
        fresh_token = _make_jwt(time.time() + 3600)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                mock_resp.json.return_value = {"data": expired_token}
            else:
                mock_resp.json.return_value = {"data": fresh_token}
            return mock_resp

        with patch(
            "claude_benchmark.execution.proxy_auth.requests.post", side_effect=side_effect
        ):
            mgr = ProxyTokenManager("/path/cert.crt", "/path/cert.key", "dev")
            first = mgr.get_token()
            assert first == expired_token
            second = mgr.get_token()
            assert second == fresh_token

    def test_invalidate(self):
        exp = time.time() + 3600
        token1 = _make_jwt(exp)
        token2 = _make_jwt(exp + 100)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                mock_resp.json.return_value = {"data": token1}
            else:
                mock_resp.json.return_value = {"data": token2}
            return mock_resp

        with patch(
            "claude_benchmark.execution.proxy_auth.requests.post", side_effect=side_effect
        ):
            mgr = ProxyTokenManager("/path/cert.crt", "/path/cert.key", "dev")
            assert mgr.get_token() == token1
            mgr.invalidate()
            assert mgr.get_token() == token2

    def test_base_url(self, monkeypatch):
        monkeypatch.setenv("PROXY_API_URL_DEV", "https://api.dev.example.com/v1")
        monkeypatch.setenv("PROXY_API_URL_PROD", "https://api.prod.example.com/v1")
        # Re-import to pick up env changes in module-level dict
        import importlib
        import claude_benchmark.execution.proxy_auth as mod
        importlib.reload(mod)
        mgr = mod.ProxyTokenManager("/c", "/k", "dev")
        assert "dev" in mgr.base_url
        mgr_prod = mod.ProxyTokenManager("/c", "/k", "prod")
        assert "prod" in mgr_prod.base_url
        assert "dev" not in mgr_prod.base_url


class TestValidation:
    def test_validate_proxy_env_missing(self, monkeypatch):
        monkeypatch.delenv("PROXY_CERT_PATH", raising=False)
        monkeypatch.delenv("PROXY_KEY_PATH", raising=False)
        missing = validate_proxy_env()
        assert "PROXY_CERT_PATH" in missing
        assert "PROXY_KEY_PATH" in missing

    def test_validate_proxy_env_present(self, monkeypatch):
        monkeypatch.setenv("PROXY_CERT_PATH", "/cert")
        monkeypatch.setenv("PROXY_KEY_PATH", "/key")
        assert validate_proxy_env() == []

    def test_is_proxy_configured_false(self, monkeypatch):
        monkeypatch.delenv("PROXY_CERT_PATH", raising=False)
        monkeypatch.delenv("PROXY_KEY_PATH", raising=False)
        assert is_proxy_configured() is False

    def test_is_proxy_configured_true(self, monkeypatch):
        monkeypatch.setenv("PROXY_CERT_PATH", "/cert")
        monkeypatch.setenv("PROXY_KEY_PATH", "/key")
        assert is_proxy_configured() is True


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the token manager singleton between tests."""
    reset_token_manager()
    yield
    reset_token_manager()
