"""Tests for toolkit.account — account state manager.

Uses tmp_path to redirect the LocalCache directory so no real files are touched.
Mocks httpx calls via the ApiClient override hook.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

import toolkit.account as account
import toolkit.api_client as api_client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(
    login_response: dict[str, Any] | None = None,
    register_response: dict[str, Any] | None = None,
) -> MagicMock:
    mock = MagicMock(spec=api_client.ApiClient)
    if login_response is not None:
        mock.login.return_value = login_response
    if register_response is not None:
        mock.register.return_value = register_response
    return mock


def _default_login_response(email: str = "test@school.edu.au") -> dict[str, Any]:
    return {
        "access_token": "tok_test_123",
        "user": {
            "id": "usr_abc",
            "email": email,
            "first_name": "Alice",
            "last_name": "Smith",
            "school": {"id": "sch_1", "name": "Test Secondary College", "abn": "12345678901"},
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_account_module(tmp_path: Path) -> Any:
    """Point account module at a fresh tmp_path cache and reset internal state."""
    account.set_cache_dir(tmp_path)
    account._clear_cache()  # noqa: SLF001
    # Reset the default API client so tests are isolated.
    api_client.set_default_client(None)
    yield
    account._clear_cache()  # noqa: SLF001
    account._cache_dir_override = None  # noqa: SLF001
    account._WARNED_PLAIN = False  # noqa: SLF001
    api_client.set_default_client(None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_load_state_unsigned_when_no_file(tmp_path: Path) -> None:
    """load_state() returns is_signed_in=False when account.dat is absent."""
    state = account.load_state()
    assert state.is_signed_in is False
    assert state.email is None


def test_login_writes_file(tmp_path: Path) -> None:
    """login() creates account.dat in the cache directory."""
    mock = _make_mock_client(login_response=_default_login_response())
    api_client.set_default_client(mock)

    account.login("test@school.edu.au", "password")

    assert (tmp_path / "account.dat").exists()


def test_load_state_reads_back_after_login(tmp_path: Path) -> None:
    """After login, load_state() returns the persisted account details."""
    mock = _make_mock_client(login_response=_default_login_response())
    api_client.set_default_client(mock)

    account.login("test@school.edu.au", "password")
    account._clear_cache()  # noqa: SLF001

    state = account.load_state()
    assert state.is_signed_in is True
    assert state.email == "test@school.edu.au"
    assert state.first_name == "Alice"
    assert state.last_name == "Smith"
    assert state.school_name == "Test Secondary College"
    assert state.school_abn == "12345678901"


def test_logout_deletes_file(tmp_path: Path) -> None:
    """logout() removes account.dat and clears the in-memory state."""
    mock = _make_mock_client(login_response=_default_login_response())
    api_client.set_default_client(mock)

    account.login("test@school.edu.au", "password")
    assert (tmp_path / "account.dat").exists()

    account.logout()
    assert not (tmp_path / "account.dat").exists()

    state = account.load_state()
    assert state.is_signed_in is False


def test_device_id_stable_across_logout_login(tmp_path: Path) -> None:
    """device_id.dat persists across logout/login cycles."""
    mock = _make_mock_client(login_response=_default_login_response())
    api_client.set_default_client(mock)

    account.login("test@school.edu.au", "password")
    first_did = (tmp_path / "device_id.dat").read_bytes()

    account.logout()
    account._clear_cache()  # noqa: SLF001

    mock2 = _make_mock_client(login_response=_default_login_response())
    api_client.set_default_client(mock2)
    account.login("test@school.edu.au", "password")
    second_did = (tmp_path / "device_id.dat").read_bytes()

    assert first_did == second_did, "device_id.dat should be stable across sign-out/sign-in"


def test_corrupt_account_dat_returns_unsigned(tmp_path: Path) -> None:
    """A corrupt account.dat logs a warning and returns is_signed_in=False."""
    (tmp_path / "account.dat").write_bytes(b"not valid json {{{{")

    state = account.load_state()
    assert state.is_signed_in is False


def test_register_does_not_sign_in(tmp_path: Path) -> None:
    """register() must NOT create account.dat (user must verify email first)."""
    mock = _make_mock_client(register_response={"ok": True})
    api_client.set_default_client(mock)

    account.register("new@school.edu.au", "password", "Bob", "Jones", "My School", "98765432100")

    assert not (tmp_path / "account.dat").exists()
    state = account.load_state()
    assert state.is_signed_in is False
