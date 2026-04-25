"""Account state manager with DPAPI-encrypted token storage.

Storage layout (per §9.1):
  Windows:   %LOCALAPPDATA%\\Packages\\SchoolTool_vurctne\\LocalCache\\account.dat
             %LOCALAPPDATA%\\Packages\\SchoolTool_vurctne\\LocalCache\\device_id.dat
  Non-Windows: ~/.local/share/school-tool/cache/account.dat
               ~/.local/share/school-tool/cache/device_id.dat

Payload (JSON, encrypted at rest):
  {access_token, user_id, email, first_name, last_name,
   school: {id, name, abn}, device_id, issued_at}
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from toolkit import api_client as _api_module
from toolkit import crypto_win

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_MSIX_FAMILY_NAME = "SchoolTool_vurctne"
_WARNED_PLAIN: bool = False

# Overridable in tests via set_cache_dir().
_cache_dir_override: Path | None = None


def _cache_dir() -> Path:
    if _cache_dir_override is not None:
        return _cache_dir_override
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            base = Path(local_app_data) / "Packages" / _MSIX_FAMILY_NAME / "LocalCache"
        else:
            base = Path.home() / "AppData" / "Local" / _MSIX_FAMILY_NAME / "LocalCache"
    else:
        base = Path.home() / ".local" / "share" / "school-tool" / "cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


def set_cache_dir(path: Path) -> None:
    """Override the LocalCache directory — for tests only."""
    global _cache_dir_override  # noqa: PLW0603
    _cache_dir_override = path


# ---------------------------------------------------------------------------
# Encrypted file I/O
# ---------------------------------------------------------------------------


def _write_dat(path: Path, data: bytes) -> None:
    """Write *data* to *path*, DPAPI-encrypted on Windows; plain otherwise."""
    global _WARNED_PLAIN  # noqa: PLW0603
    path.parent.mkdir(parents=True, exist_ok=True)
    if crypto_win.available():
        crypto_win.encrypt_to_file(path, data)
    else:
        if not _WARNED_PLAIN:
            logger.warning(
                "DPAPI unavailable — writing account data as plaintext"
                " (non-Windows / missing pywin32)"
            )
            _WARNED_PLAIN = True
        path.write_bytes(data)


def _read_dat(path: Path) -> bytes:
    """Read and decrypt *path*; raises FileNotFoundError if absent."""
    if crypto_win.available():
        return crypto_win.decrypt_from_file(path)
    return path.read_bytes()


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccountState:
    is_signed_in: bool
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    school_name: str | None = None
    school_abn: str | None = None


# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------

_state_cache: AccountState | None = None
_payload_cache: dict[str, Any] | None = None


def _clear_cache() -> None:
    global _state_cache, _payload_cache  # noqa: PLW0603
    _state_cache = None
    _payload_cache = None


# ---------------------------------------------------------------------------
# Device-ID helpers
# ---------------------------------------------------------------------------


def _device_id_path() -> Path:
    return _cache_dir() / "device_id.dat"


def _account_path() -> Path:
    return _cache_dir() / "account.dat"


def _load_or_create_device_id() -> str:
    """Return the persisted device_id, creating it on first use."""
    p = _device_id_path()
    if p.exists():
        try:
            raw = _read_dat(p)
            return raw.decode().strip()
        except Exception:
            logger.warning("Could not read device_id.dat — regenerating")
    did = str(uuid.uuid4())
    _write_dat(p, did.encode())
    logger.info("Generated new device_id (saved to disk)")
    return did


# ---------------------------------------------------------------------------
# Internal payload → AccountState
# ---------------------------------------------------------------------------


def _state_from_payload(payload: dict[str, Any]) -> AccountState:
    school: dict[str, Any] = payload.get("school") or {}
    return AccountState(
        is_signed_in=True,
        email=payload.get("email"),
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
        school_name=school.get("name"),
        school_abn=school.get("abn"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_state() -> AccountState:
    """Return the cached AccountState, loading from disk if needed."""
    global _state_cache, _payload_cache  # noqa: PLW0603
    if _state_cache is not None:
        return _state_cache

    p = _account_path()
    if not p.exists():
        _state_cache = AccountState(is_signed_in=False)
        return _state_cache

    try:
        raw = _read_dat(p)
        payload: dict[str, Any] = json.loads(raw.decode())
        _payload_cache = payload
        # Restore the auth token on the shared API client.
        token = payload.get("access_token")
        if isinstance(token, str) and token:
            _api_module.default_client().set_token(token)
        _state_cache = _state_from_payload(payload)
        return _state_cache
    except FileNotFoundError:
        _state_cache = AccountState(is_signed_in=False)
        return _state_cache
    except Exception as exc:
        logger.warning("Corrupt account.dat — treating as signed out: %s", exc)
        _state_cache = AccountState(is_signed_in=False)
        return _state_cache


def register(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    school_name: str,
    abn: str,
) -> None:
    """Register a new account.  Raises ApiError on failure.

    Does NOT auto-sign-in — the user must verify their email first.
    """
    _api_module.default_client().register(
        {
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            "school_name": school_name,
            "abn": abn,
        }
    )
    logger.info("Registration submitted for %s", email)


def login(email: str, password: str) -> None:
    """Sign in, persist the access token, and update the in-memory cache."""
    global _state_cache, _payload_cache  # noqa: PLW0603

    device_id = _load_or_create_device_id()
    client = _api_module.default_client()
    response = client.login(email, password, device_id)

    token: str = response["access_token"]
    user: dict[str, Any] = response.get("user") or {}

    school: dict[str, Any] = user.get("school") or {}
    payload: dict[str, Any] = {
        "access_token": token,
        "user_id": user.get("id"),
        "email": user.get("email", email),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "school": {
            "id": school.get("id"),
            "name": school.get("name"),
            "abn": school.get("abn"),
        },
        "device_id": device_id,
        "issued_at": user.get("issued_at"),
    }

    _write_dat(_account_path(), json.dumps(payload).encode())
    logger.info("account.dat written (token NOT logged)")

    client.set_token(token)
    _payload_cache = payload
    _state_cache = _state_from_payload(payload)


def logout() -> None:
    """Delete the persisted token, clear the auth header, and wipe the cache."""
    global _state_cache, _payload_cache  # noqa: PLW0603

    p = _account_path()
    if p.exists():
        try:
            p.unlink()
        except OSError as exc:
            logger.warning("Could not delete account.dat: %s", exc)

    _api_module.default_client().set_token(None)
    _clear_cache()
    _state_cache = AccountState(is_signed_in=False)
    logger.info("Signed out — account.dat removed, token cleared")


def request_password_reset(email: str) -> None:
    """Send a password-reset email.  Silently swallows 404 (anti-enumeration)."""
    try:
        _api_module.default_client().password_reset_request(email)
        logger.info("Password reset requested for %s", email)
    except _api_module.ApiError as exc:
        if exc.status_code == 404:
            # Server contract: always 200/404 silently so as not to enumerate accounts.
            logger.info("Password reset: 404 swallowed per anti-enumeration contract")
        else:
            raise


def change_password(old: str, new: str) -> None:
    """Change the signed-in user's password.  Does not touch disk."""
    _api_module.default_client().change_password(old, new)
    logger.info("Password changed successfully")
