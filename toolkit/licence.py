"""Signed licence token verifier and renewal prompt scheduler.

Ed25519 public key is embedded at build time by replacing the placeholder
constant ``PUBLIC_KEY_BASE64``.  Ivan swaps this per release using the value
produced by the backend's ``wrangler secret get`` derivative.

For M2 (development milestone) the placeholder is left as-is; signature
verification will fail gracefully (``"expired"`` / ``"none"`` states) until
real keys are embedded.

Licence file location (§3.1 / ADR-0011):
  Windows:    %LOCALAPPDATA%\\Packages\\SchoolTool_vurctne\\LocalCache\\licence.json
  Non-Windows: ~/.local/share/school-tool/cache/licence.json
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import app_metadata
from toolkit import account as _account_module
from toolkit import api_client as _api_module

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedded public key — SWAP THIS PER RELEASE
# ---------------------------------------------------------------------------

# Placeholder: base64-encoded Ed25519 public key (32 raw bytes).
# Set to a real value by the release pipeline.  An empty / invalid string means
# all licence signatures will fail verification and the tool will report "expired"
# until the key is populated.
PUBLIC_KEY_BASE64: str = "__EMBEDDED_AT_BUILD_TIME__"

# ---------------------------------------------------------------------------
# Path helpers (mirrors account.py's cache dir)
# ---------------------------------------------------------------------------

_MSIX_FAMILY_NAME = "SchoolTool_vurctne"
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


def _licence_path() -> Path:
    return _cache_dir() / "licence.json"


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

LicenceState = Literal[
    "none", "invoice_issued", "po_uploaded", "under_review", "active", "grace", "expired"
]


@dataclass(frozen=True)
class LicenceStatus:
    state: LicenceState
    expires_at: datetime | None = None
    devices: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RenewalPrompt:
    title: str
    message: str


# ---------------------------------------------------------------------------
# Ed25519 signature verification
# ---------------------------------------------------------------------------


def _canonical_json(payload: dict[str, Any]) -> bytes:
    """Return canonical UTF-8 JSON with sorted keys and compact separators."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _verify_signature(doc: dict[str, Any]) -> bool:
    """Return True if the Ed25519 signature in *doc* is valid over all other fields."""
    raw_sig_field: Any = doc.get("signature", "")
    if not isinstance(raw_sig_field, str):
        return False
    sig_str: str = raw_sig_field

    # Strip the "ed25519:" prefix if present.
    if sig_str.startswith("ed25519:"):
        sig_str = sig_str[len("ed25519:") :]

    try:
        sig_bytes = base64.b64decode(sig_str)
    except Exception:
        logger.debug("Licence signature is not valid base64")
        return False

    # Build the signed payload (every field except "signature" and "prompts").
    payload = {k: v for k, v in doc.items() if k not in ("signature", "prompts")}

    try:
        raw_key = base64.b64decode(PUBLIC_KEY_BASE64)
        pub_key = Ed25519PublicKey.from_public_bytes(raw_key)
        pub_key.verify(sig_bytes, _canonical_json(payload))
        return True
    except (InvalidSignature, Exception) as exc:
        logger.debug("Licence signature verification failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _load_raw() -> dict[str, Any] | None:
    """Read licence.json from disk, returning the parsed dict or None."""
    p = _licence_path()
    if not p.exists():
        return None
    try:
        return dict(json.loads(p.read_text(encoding="utf-8")))
    except Exception as exc:
        logger.warning("Could not parse licence.json: %s", exc)
        return None


def _save_raw(doc: dict[str, Any]) -> None:
    """Atomically write *doc* to licence.json via temp-file + rename."""
    p = _licence_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path_str = tempfile.mkstemp(dir=p.parent, prefix=".licence_tmp_")
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        tmp_path.replace(p)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_status(now: datetime | None = None) -> LicenceStatus:
    """Read and verify the cached licence.json, returning a LicenceStatus.

    Mapping:
    - Missing file                       → "none"
    - Invalid signature OR expired > 14d → "expired"
    - Expired 0–14 days                  → "grace"
    - Valid + expires_at > now           → "active"
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)

    doc = _load_raw()
    if doc is None:
        return LicenceStatus(state="none")

    if not _verify_signature(doc):
        logger.warning("Licence signature invalid — treating as expired")
        return LicenceStatus(state="expired")

    expires_at = _parse_datetime(doc.get("expires_at"))
    if expires_at is None:
        logger.warning("Licence has no expires_at — treating as expired")
        return LicenceStatus(state="expired")

    delta = expires_at - now
    days_left = delta.total_seconds() / 86400

    devices: list[str] = []
    raw_devices: Any = doc.get("devices")
    if isinstance(raw_devices, list):
        devices = [str(d) for d in raw_devices]

    if days_left > 0:
        return LicenceStatus(state="active", expires_at=expires_at, devices=devices)
    elif days_left >= -14:
        return LicenceStatus(state="grace", expires_at=expires_at, devices=devices)
    else:
        return LicenceStatus(state="expired", expires_at=expires_at, devices=devices)


def refresh() -> LicenceStatus:
    """Call the server to refresh the licence token, write it to disk, and return status."""
    _account_module.load_state()
    raw = _load_raw() or {}

    device_id: str = raw.get("device_id", "")
    if not device_id:
        # Fall back to the device_id stored in account.dat via account module internals.
        import toolkit.account as _acct  # noqa: PLC0415

        acct_payload: dict[str, Any] = dict(_acct._payload_cache or {})
        device_id = str(acct_payload.get("device_id", ""))

    os_info = f"{sys.platform} {sys.version}"
    app_version = app_metadata.APP_VERSION

    logger.info("Refreshing licence from server (device_id present=%s)", bool(device_id))
    response = _api_module.default_client().refresh_licence(device_id, os_info, app_version)

    # Server returns the full signed licence JSON; write it verbatim.
    if not isinstance(response, dict):
        logger.warning("refresh_licence returned unexpected type — skipping write")
    else:
        _save_raw(response)
        logger.info("licence.json updated from server")

    return read_status()


def maybe_prompt(now: datetime | None = None) -> RenewalPrompt | None:
    """Return a RenewalPrompt if one should be shown per §3.3, else None.

    Prompt schedule:
      days_left == 60 → modal once (flagged prompts.d60)
      days_left == 30 → modal once (flagged prompts.d30)
      1 ≤ days_left ≤ 7 → modal once per calendar day (keyed prompts.last_prompted_on)
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)

    doc = _load_raw()
    if doc is None:
        return None

    expires_at = _parse_datetime(doc.get("expires_at"))
    if expires_at is None:
        return None

    delta = expires_at - now
    # Round to nearest integer day so that a licence created as
    # "exactly N days from now" is reliably treated as N days left.
    days_left = round(delta.total_seconds() / 86400)

    prompts: dict[str, Any] = {}
    raw_prompts: Any = doc.get("prompts")
    if isinstance(raw_prompts, dict):
        prompts = dict(raw_prompts)

    def _save_prompts(p: dict[str, Any]) -> None:
        doc["prompts"] = p
        _save_raw(doc)

    if days_left == 60 and not prompts.get("d60"):
        prompts["d60"] = True
        _save_prompts(prompts)
        return RenewalPrompt(
            title="60 days",
            message="Your licence expires in 60 days. Renew now?",
        )

    if days_left == 30 and not prompts.get("d30"):
        prompts["d30"] = True
        _save_prompts(prompts)
        return RenewalPrompt(
            title="30 days",
            message="Your licence expires in 30 days. Renew now?",
        )

    if 1 <= days_left <= 7:
        today = now.date().isoformat()
        if prompts.get("last_prompted_on") != today:
            prompts["last_prompted_on"] = today
            _save_prompts(prompts)
            return RenewalPrompt(
                title=f"{days_left} days left",
                message=f"Your licence expires in {days_left} day(s). Renew now?",
            )

    return None
