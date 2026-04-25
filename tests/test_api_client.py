"""Tests for toolkit.api_client.ApiClient.

Uses httpx.MockTransport to stub server responses — no real network calls.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from toolkit.api_client import ApiClient, ApiError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_response(body: Any, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )


def _make_client(handler: httpx.MockTransport) -> ApiClient:
    """Build an ApiClient backed by a MockTransport."""
    client = ApiClient(base_url="https://test.example")
    client._client = httpx.Client(transport=handler, timeout=5.0)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_login_success_returns_token() -> None:
    """Successful login returns access_token from the server body."""
    payload = {"access_token": "tok_abc", "user": {"id": "usr_1", "email": "a@b.com"}}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/auth/login"
        body = json.loads(request.content)
        assert body["email"] == "a@b.com"
        return _json_response(payload)

    client = _make_client(httpx.MockTransport(handler))
    result = client.login("a@b.com", "secret", "dev-1")
    assert result["access_token"] == "tok_abc"


def test_login_401_raises_api_error() -> None:
    """A 401 response must raise ApiError with status_code=401."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"error": "invalid_credentials"}, status_code=401)

    client = _make_client(httpx.MockTransport(handler))
    with pytest.raises(ApiError) as exc_info:
        client.login("a@b.com", "wrong", "dev-1")
    assert exc_info.value.status_code == 401
    assert exc_info.value.body == {"error": "invalid_credentials"}


def test_network_error_raises_api_error_status_zero() -> None:
    """A network-level failure must raise ApiError(0, {"error": "network"})."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _make_client(httpx.MockTransport(handler))
    with pytest.raises(ApiError) as exc_info:
        client.login("a@b.com", "pass", "dev-1")
    assert exc_info.value.status_code == 0
    assert exc_info.value.body == {"error": "network"}


def test_register_success() -> None:
    """register() sends the correct payload and returns the server body."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/auth/register"
        body = json.loads(request.content)
        assert body["email"] == "new@school.edu.au"
        return _json_response({"ok": True})

    client = _make_client(httpx.MockTransport(handler))
    result = client.register(
        {
            "email": "new@school.edu.au",
            "password": "password123",
            "first_name": "Alice",
            "last_name": "Smith",
            "school_name": "Test Secondary College",
            "abn": "12345678901",
        }
    )
    assert result == {"ok": True}


def test_verify_email() -> None:
    """verify_email() POSTs to /v1/auth/verify-email with the token."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/auth/verify-email"
        body = json.loads(request.content)
        assert body["token"] == "verification_tok"
        return _json_response({"ok": True})

    client = _make_client(httpx.MockTransport(handler))
    result = client.verify_email("verification_tok")
    assert result == {"ok": True}


def test_me_sends_bearer_token() -> None:
    """me() includes the Authorization header when a token is set."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/me"
        assert "Bearer tok_xyz" in request.headers.get("Authorization", "")
        return _json_response({"email": "user@school.edu.au"})

    client = _make_client(httpx.MockTransport(handler))
    client.set_token("tok_xyz")
    result = client.me()
    assert result["email"] == "user@school.edu.au"


def test_me_without_token_no_auth_header() -> None:
    """me() omits the Authorization header when no token is set."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return _json_response({"email": None})

    client = _make_client(httpx.MockTransport(handler))
    result = client.me()
    assert result == {"email": None}


def test_server_500_raises_api_error() -> None:
    """Any 5xx response must raise ApiError with the correct status_code."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"error": "internal"}, status_code=500)

    client = _make_client(httpx.MockTransport(handler))
    with pytest.raises(ApiError) as exc_info:
        client.me()
    assert exc_info.value.status_code == 500


def test_register_verify_login_happy_path() -> None:
    """Full happy path: register → verify_email → login returns token."""
    state: dict[str, int] = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if request.url.path == "/v1/auth/register":
            return _json_response({"ok": True})
        if request.url.path == "/v1/auth/verify-email":
            return _json_response({"ok": True})
        if request.url.path == "/v1/auth/login":
            return _json_response(
                {"access_token": "tok_final", "user": {"id": "usr_2", "email": "z@z.com"}}
            )
        return _json_response({}, status_code=404)

    client = _make_client(httpx.MockTransport(handler))
    client.register(
        {
            "email": "z@z.com",
            "password": "p",
            "first_name": "Z",
            "last_name": "Z",
            "school_name": "S",
            "abn": "123",
        }
    )
    client.verify_email("verify_tok_123")
    result = client.login("z@z.com", "p", "dev-1")
    assert result["access_token"] == "tok_final"
    assert state["calls"] == 3
