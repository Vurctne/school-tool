"""Tests for toolkit.licence — Ed25519 verification and renewal prompt schedule.

Generates a throwaway Ed25519 keypair per test session so no real keys are needed.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import toolkit.licence as lic

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_keypair() -> tuple[Ed25519PrivateKey, str]:
    """Return (private_key, public_key_base64)."""
    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes_raw()
    return priv, base64.b64encode(pub_bytes).decode()


def _sign_licence(priv: Ed25519PrivateKey, doc: dict[str, Any]) -> dict[str, Any]:
    """Return *doc* with a valid 'signature' field added."""
    payload = {k: v for k, v in doc.items() if k not in ("signature", "prompts")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig_bytes = priv.sign(canonical)
    signed = dict(doc)
    signed["signature"] = "ed25519:" + base64.b64encode(sig_bytes).decode()
    return signed


def _future(days: int = 365) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).isoformat()


def _past(days: int = 1) -> str:
    return (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()


def _write_licence(tmp_path: Path, doc: dict[str, Any]) -> None:
    (tmp_path / "licence.json").write_text(json.dumps(doc), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def keypair() -> tuple[Ed25519PrivateKey, str]:
    return _generate_keypair()


@pytest.fixture(autouse=True)
def reset_licence_module(tmp_path: Path) -> Any:
    lic.set_cache_dir(tmp_path)
    lic._cache_dir_override = tmp_path  # noqa: SLF001
    yield
    lic._cache_dir_override = None  # noqa: SLF001


# ---------------------------------------------------------------------------
# Tests: read_status()
# ---------------------------------------------------------------------------


def test_read_status_none_when_no_file() -> None:
    """read_status() returns 'none' when licence.json is absent."""
    status = lic.read_status()
    assert status.state == "none"


def test_read_status_active_with_valid_signature(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """read_status() returns 'active' when signature is valid and expires_at is future."""
    priv, pub_b64 = keypair
    doc = _sign_licence(
        priv,
        {
            "licence_id": "lic_1",
            "school_id": "sch_1",
            "email": "user@school.edu.au",
            "device_id": "dev-1",
            "issued_at": _past(1),
            "expires_at": _future(365),
            "features": ["sub_program"],
        },
    )
    _write_licence(tmp_path, doc)

    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        status = lic.read_status()

    assert status.state == "active"
    assert status.expires_at is not None


def test_tampered_payload_returns_expired(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """Tampering with any field after signing must yield 'expired'."""
    priv, pub_b64 = keypair
    doc = _sign_licence(
        priv,
        {
            "licence_id": "lic_1",
            "school_id": "sch_1",
            "email": "user@school.edu.au",
            "device_id": "dev-1",
            "issued_at": _past(1),
            "expires_at": _future(365),
            "features": ["sub_program"],
        },
    )
    # Tamper: extend the expiry after signing.
    doc["expires_at"] = _future(999)
    _write_licence(tmp_path, doc)

    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        status = lic.read_status()

    assert status.state == "expired"


def test_expired_10_days_ago_returns_grace(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """Licence expired 10 days ago is within grace period → 'grace'."""
    priv, pub_b64 = keypair
    doc = _sign_licence(
        priv,
        {
            "licence_id": "lic_2",
            "school_id": "sch_1",
            "email": "user@school.edu.au",
            "device_id": "dev-1",
            "issued_at": _past(375),
            "expires_at": _past(10),
            "features": ["sub_program"],
        },
    )
    _write_licence(tmp_path, doc)

    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        status = lic.read_status()

    assert status.state == "grace"


def test_expired_30_days_ago_returns_expired(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """Licence expired 30 days ago is beyond grace → 'expired'."""
    priv, pub_b64 = keypair
    doc = _sign_licence(
        priv,
        {
            "licence_id": "lic_3",
            "school_id": "sch_1",
            "email": "user@school.edu.au",
            "device_id": "dev-1",
            "issued_at": _past(400),
            "expires_at": _past(30),
            "features": ["sub_program"],
        },
    )
    _write_licence(tmp_path, doc)

    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        status = lic.read_status()

    assert status.state == "expired"


def test_invalid_public_key_returns_expired(tmp_path: Path) -> None:
    """An unrecognised public key placeholder causes verification to fail → 'expired'."""
    priv, _pub = _generate_keypair()
    doc = _sign_licence(
        priv,
        {
            "licence_id": "lic_bad",
            "email": "x@x.com",
            "expires_at": _future(365),
        },
    )
    _write_licence(tmp_path, doc)

    with patch.object(lic, "PUBLIC_KEY_BASE64", "__EMBEDDED_AT_BUILD_TIME__"):
        status = lic.read_status()

    assert status.state == "expired"


# ---------------------------------------------------------------------------
# Tests: maybe_prompt()
# ---------------------------------------------------------------------------


def _write_signed_licence(
    tmp_path: Path,
    priv: Ed25519PrivateKey,
    days_left: int,
    prompts: dict[str, Any] | None = None,
) -> None:
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=days_left)
    base: dict[str, Any] = {
        "licence_id": "lic_prompt",
        "email": "user@school.edu.au",
        "expires_at": expires_at.isoformat(),
    }
    doc = _sign_licence(priv, base)
    if prompts:
        doc["prompts"] = prompts
    _write_licence(tmp_path, doc)


def test_maybe_prompt_day_60(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """maybe_prompt() returns the 60-day modal on the first call at day 60."""
    priv, pub_b64 = keypair
    _write_signed_licence(tmp_path, priv, days_left=60)

    now = datetime.now(tz=timezone.utc)
    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        result = lic.maybe_prompt(now)

    assert result is not None
    assert "60" in result.title


def test_maybe_prompt_day_60_only_once(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """maybe_prompt() does NOT fire again for day-60 after the flag is set."""
    priv, pub_b64 = keypair
    _write_signed_licence(tmp_path, priv, days_left=60, prompts={"d60": True})

    now = datetime.now(tz=timezone.utc)
    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        result = lic.maybe_prompt(now)

    assert result is None


def test_maybe_prompt_day_30(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """maybe_prompt() returns the 30-day modal on the first call at day 30."""
    priv, pub_b64 = keypair
    _write_signed_licence(tmp_path, priv, days_left=30)

    now = datetime.now(tz=timezone.utc)
    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        result = lic.maybe_prompt(now)

    assert result is not None
    assert "30" in result.title


def test_maybe_prompt_day_5_daily(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """maybe_prompt() fires the daily modal when days_left is in 1–7 range."""
    priv, pub_b64 = keypair
    _write_signed_licence(tmp_path, priv, days_left=5)

    now = datetime.now(tz=timezone.utc)
    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        result = lic.maybe_prompt(now)

    assert result is not None
    assert "days left" in result.title


def test_maybe_prompt_day_5_not_repeated_same_day(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """maybe_prompt() does NOT fire twice on the same calendar day."""
    priv, pub_b64 = keypair
    now = datetime.now(tz=timezone.utc)
    today = now.date().isoformat()
    _write_signed_licence(tmp_path, priv, days_left=5, prompts={"last_prompted_on": today})

    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        result = lic.maybe_prompt(now)

    assert result is None


def test_maybe_prompt_day_100_returns_none(
    tmp_path: Path,
    keypair: tuple[Ed25519PrivateKey, str],
) -> None:
    """maybe_prompt() returns None when days_left > 60."""
    priv, pub_b64 = keypair
    _write_signed_licence(tmp_path, priv, days_left=100)

    now = datetime.now(tz=timezone.utc)
    with patch.object(lic, "PUBLIC_KEY_BASE64", pub_b64):
        result = lic.maybe_prompt(now)

    assert result is None


def test_maybe_prompt_no_licence_returns_none() -> None:
    """maybe_prompt() returns None when no licence.json exists."""
    result = lic.maybe_prompt()
    assert result is None
