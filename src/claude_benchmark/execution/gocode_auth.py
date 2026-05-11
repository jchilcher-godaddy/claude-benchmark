"""Cert-based JWT authentication for an OpenAI-compatible API proxy.

Handles token acquisition, caching, and automatic refresh before expiry.
Uses mTLS certs to obtain short-lived JWTs from an SSO endpoint.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time

import requests

logger = logging.getLogger(__name__)

_SSO_URLS: dict[str, str] = {
    "dev": os.environ.get("GOCODE_SSO_URL_DEV", "https://sso.example.com/v1/secure/api/token"),
    "test": os.environ.get("GOCODE_SSO_URL_TEST", "https://sso.example.com/v1/secure/api/token"),
    "prod": os.environ.get("GOCODE_SSO_URL_PROD", "https://sso.example.com/v1/secure/api/token"),
}

_GOCODE_BASE_URLS: dict[str, str] = {
    "dev": os.environ.get("GOCODE_API_URL_DEV", "https://api.example.com/v1"),
    "test": os.environ.get("GOCODE_API_URL_TEST", "https://api.example.com/v1"),
    "prod": os.environ.get("GOCODE_API_URL_PROD", "https://api.example.com/v1"),
}

_REFRESH_BUFFER_SECONDS = 60


def _parse_jwt_exp(token: str) -> float | None:
    """Extract expiry timestamp from a JWT without verifying signature."""
    try:
        payload_b64 = token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return float(payload["exp"])
    except (IndexError, KeyError, ValueError, json.JSONDecodeError):
        return None


class GoCodeTokenManager:
    """Manages cert-based JWT tokens for GoCode API access.

    Thread-safe: multiple workers can call get_token() concurrently.
    """

    def __init__(self, cert_path: str, key_path: str, env: str = "dev") -> None:
        self._cert_path = cert_path
        self._key_path = key_path
        self._env = env
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    @property
    def base_url(self) -> str:
        return _GOCODE_BASE_URLS[self._env]

    def get_token(self) -> str:
        """Return a valid JWT token, refreshing if expired or about to expire."""
        with self._lock:
            if self._token and time.time() < (self._expires_at - _REFRESH_BUFFER_SECONDS):
                return self._token
            self._token = self._fetch_token()
            exp = _parse_jwt_exp(self._token)
            if exp:
                self._expires_at = exp
            else:
                self._expires_at = time.time() + 3000
            return self._token

    def invalidate(self) -> None:
        """Force re-fetch on next get_token() call."""
        with self._lock:
            self._expires_at = 0.0

    def _fetch_token(self) -> str:
        """Fetch fresh JWT from SSO using mTLS cert auth."""
        sso_url = _SSO_URLS[self._env]
        resp = requests.post(
            sso_url,
            data={"realm": "cert"},
            cert=(self._cert_path, self._key_path),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("data")
        if not token:
            raise RuntimeError(f"GoCode SSO returned no token: {data}")
        return token


_token_manager: GoCodeTokenManager | None = None
_manager_lock = threading.Lock()


def get_token_manager() -> GoCodeTokenManager:
    """Return the module-level singleton GoCodeTokenManager.

    Reads GOCODE_CERT_PATH, GOCODE_KEY_PATH, and GOCODE_ENV from environment.
    Optionally reads GOCODE_SSO_URL_{DEV,TEST,PROD} and GOCODE_API_URL_{DEV,TEST,PROD}
    to override the default placeholder endpoints.
    """
    global _token_manager
    with _manager_lock:
        if _token_manager is None:
            cert_path = os.environ["GOCODE_CERT_PATH"]
            key_path = os.environ["GOCODE_KEY_PATH"]
            env = os.environ.get("GOCODE_ENV", "dev")
            _token_manager = GoCodeTokenManager(cert_path, key_path, env)
        return _token_manager


def reset_token_manager() -> None:
    """Reset the singleton (for testing)."""
    global _token_manager
    with _manager_lock:
        _token_manager = None


def is_gocode_configured() -> bool:
    """Check if GoCode cert env vars are set."""
    return bool(os.environ.get("GOCODE_CERT_PATH") and os.environ.get("GOCODE_KEY_PATH"))


def validate_gocode_env() -> list[str]:
    """Check required GoCode environment variables.

    Returns list of missing variable names (empty if all present).
    """
    missing = []
    if not os.environ.get("GOCODE_CERT_PATH"):
        missing.append("GOCODE_CERT_PATH")
    if not os.environ.get("GOCODE_KEY_PATH"):
        missing.append("GOCODE_KEY_PATH")
    return missing


def validate_gocode_credentials() -> str | None:
    """Attempt to fetch a GoCode JWT token.

    Returns None on success, or an error message string.
    """
    try:
        cert_path = os.environ.get("GOCODE_CERT_PATH", "")
        key_path = os.environ.get("GOCODE_KEY_PATH", "")
        env = os.environ.get("GOCODE_ENV", "dev")
        mgr = GoCodeTokenManager(cert_path, key_path, env)
        mgr.get_token()
        return None
    except Exception as exc:
        return str(exc)
