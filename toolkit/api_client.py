"""HTTP API client for School Tool backend.

Thin httpx wrapper around the Cloudflare Workers API.  All public methods raise
``ApiError`` on 4xx/5xx responses and on network failures so callers can show a
friendly offline banner without catching httpx internals.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

import app_metadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class ApiError(Exception):
    """Raised by ApiClient for any non-2xx response or network failure."""

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        super().__init__(f"HTTP {status_code}: {body}")
        self.status_code = status_code
        self.body = body


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ApiClient:
    """Thin httpx wrapper around the SFT backend API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = (base_url or app_metadata.API_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._token: str | None = None
        self._client = httpx.Client(timeout=self._timeout)

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def set_token(self, token: str | None) -> None:
        """Set (or clear) the Bearer token used for authenticated requests."""
        self._token = token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        hdrs: dict[str, str] = {"Content-Type": "application/json"}
        if self._token is not None:
            hdrs["Authorization"] = f"Bearer {self._token}"
        return hdrs

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            response = self._client.request(
                method,
                url,
                headers=self._headers(),
                json=json,
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            logger.warning("Network error contacting %s: %s", url, exc)
            raise ApiError(0, {"error": "network"}) from exc

        if response.is_error:
            try:
                body: dict[str, Any] = response.json()
            except Exception:
                body = {"error": response.text}
            logger.warning("API error %d from %s %s", response.status_code, method, path)
            raise ApiError(response.status_code, body)

        # 204 No Content and similar
        if not response.content:
            return {}

        result: dict[str, Any] = response.json()
        return result

    # ------------------------------------------------------------------
    # Auth endpoints
    # ------------------------------------------------------------------

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /v1/auth/register"""
        return self._request("POST", "/v1/auth/register", json=payload)

    def verify_email(self, token: str) -> dict[str, Any]:
        """POST /v1/auth/verify-email"""
        return self._request("POST", "/v1/auth/verify-email", json={"token": token})

    def login(self, email: str, password: str, device_id: str) -> dict[str, Any]:
        """POST /v1/auth/login — returns {access_token, user}"""
        return self._request(
            "POST",
            "/v1/auth/login",
            json={"email": email, "password": password, "device_id": device_id},
        )

    def password_reset_request(self, email: str) -> None:
        """POST /v1/auth/password-reset/request"""
        self._request("POST", "/v1/auth/password-reset/request", json={"email": email})

    def password_reset_confirm(self, token: str, new_password: str) -> None:
        """POST /v1/auth/password-reset/confirm"""
        self._request(
            "POST",
            "/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": new_password},
        )

    def change_password(self, old_password: str, new_password: str) -> None:
        """POST /v1/auth/password/change — requires auth token"""
        self._request(
            "POST",
            "/v1/auth/password/change",
            json={"old_password": old_password, "new_password": new_password},
        )

    # ------------------------------------------------------------------
    # User / school
    # ------------------------------------------------------------------

    def me(self) -> dict[str, Any]:
        """GET /v1/me"""
        return self._request("GET", "/v1/me")

    def create_school(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /v1/schools"""
        return self._request("POST", "/v1/schools", json=payload)

    # ------------------------------------------------------------------
    # Licence
    # ------------------------------------------------------------------

    def activate_licence(
        self,
        device_id: str,
        os_info: str,
        app_version: str,
    ) -> dict[str, Any]:
        """POST /v1/licences/activate"""
        return self._request(
            "POST",
            "/v1/licences/activate",
            json={"device_id": device_id, "os_info": os_info, "app_version": app_version},
        )

    def refresh_licence(
        self,
        device_id: str,
        os_info: str,
        app_version: str,
    ) -> dict[str, Any]:
        """POST /v1/licences/refresh — idempotent"""
        return self._request(
            "POST",
            "/v1/licences/refresh",
            json={"device_id": device_id, "os_info": os_info, "app_version": app_version},
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default: ApiClient | None = None


def default_client() -> ApiClient:
    """Return the module-level singleton ApiClient.

    Tests may replace it via ``set_default_client``.
    """
    global _default  # noqa: PLW0603
    if _default is None:
        _default = ApiClient()
    return _default


def set_default_client(client: ApiClient | None) -> None:
    """Override the module-level singleton (use in tests)."""
    global _default  # noqa: PLW0603
    _default = client
