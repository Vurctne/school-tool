"""Tests for scripts/generate_licence_keypair.py.

Calls the module's library functions directly — no subprocess.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from scripts.generate_licence_keypair import (
    encode_key,
    generate_keypair,
    write_public_key_to_app_metadata,
)

# ---------------------------------------------------------------------------
# Test 1 — keypair produces 32-byte keys and public key is correctly derived
# ---------------------------------------------------------------------------


def test_generate_pair_produces_32_byte_keys() -> None:
    """generate_keypair() returns (priv_raw, pub_raw) each exactly 32 bytes,
    and pub_raw is correctly derived from priv_raw."""
    priv_raw, pub_raw = generate_keypair()

    assert len(priv_raw) == 32, f"private key should be 32 bytes, got {len(priv_raw)}"
    assert len(pub_raw) == 32, f"public key should be 32 bytes, got {len(pub_raw)}"

    # Re-derive the public key from the private key and compare.
    from cryptography.hazmat.primitives import serialization

    priv_obj = Ed25519PrivateKey.from_private_bytes(priv_raw)
    rederived_pub: bytes = priv_obj.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    assert rederived_pub == pub_raw, "public key does not match re-derived public key"


# ---------------------------------------------------------------------------
# Test 2 — base64 encode/decode round-trip; 44-char output with padding
# ---------------------------------------------------------------------------


def test_keys_base64_encode_decodes_round_trip() -> None:
    """encode_key() produces a 44-character base64 string that decodes back to
    the original 32 bytes and includes '=' padding."""
    priv_raw, pub_raw = generate_keypair()

    for raw in (priv_raw, pub_raw):
        encoded = encode_key(raw)
        assert len(encoded) == 44, (
            f"base64 of 32 bytes should be 44 chars, got {len(encoded)}: {encoded!r}"
        )
        assert encoded.endswith("="), f"32-byte base64 must have '=' padding, got: {encoded!r}"
        decoded = base64.b64decode(encoded)
        assert decoded == raw, "decoded base64 does not match original raw bytes"


# ---------------------------------------------------------------------------
# Test 3 — write_public_key_to_app_metadata replaces the placeholder
# ---------------------------------------------------------------------------


def test_write_app_metadata_replaces_placeholder(tmp_path: Path) -> None:
    """Writer replaces LICENCE_PUBLIC_KEY = b"" with the new value,
    leaves other lines unchanged, and creates a .bak file."""
    metadata = tmp_path / "app_metadata.py"
    metadata.write_text(
        "from __future__ import annotations\n\n"
        'APP_NAME = "School Tool"\n'
        'LICENCE_PUBLIC_KEY = b""\n'
        'SUPPORT_EMAIL = "x@example.com"\n',
        encoding="utf-8",
    )

    pub_b64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    write_public_key_to_app_metadata(pub_b64, metadata)

    updated = metadata.read_text(encoding="utf-8")
    assert f'LICENCE_PUBLIC_KEY = b"{pub_b64}"' in updated
    assert 'APP_NAME = "School Tool"' in updated
    assert 'SUPPORT_EMAIL = "x@example.com"' in updated

    bak_path = tmp_path / "app_metadata.py.bak"
    assert bak_path.exists(), ".bak file was not created"
    assert 'LICENCE_PUBLIC_KEY = b""' in bak_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 4 — write_public_key_to_app_metadata replaces an existing key
# ---------------------------------------------------------------------------


def test_write_app_metadata_replaces_existing_key(tmp_path: Path) -> None:
    """Writer replaces an existing non-empty LICENCE_PUBLIC_KEY value."""
    old_key = "OldOldOldOldOldOldOldOldOldOldOldOldOldOldX="
    metadata = tmp_path / "app_metadata.py"
    metadata.write_text(
        f'LICENCE_PUBLIC_KEY = b"{old_key}"\n',
        encoding="utf-8",
    )

    new_key = "NewNewNewNewNewNewNewNewNewNewNewNewNewNewNew="
    write_public_key_to_app_metadata(new_key, metadata)

    updated = metadata.read_text(encoding="utf-8")
    assert f'LICENCE_PUBLIC_KEY = b"{new_key}"' in updated
    assert old_key not in updated


# ---------------------------------------------------------------------------
# Test 5 — trailing comment is preserved after the assignment
# ---------------------------------------------------------------------------


def test_write_app_metadata_preserves_trailing_comment(tmp_path: Path) -> None:
    """Trailing comment on the LICENCE_PUBLIC_KEY line is preserved exactly."""
    metadata = tmp_path / "app_metadata.py"
    metadata.write_text(
        'LICENCE_PUBLIC_KEY = b""  # some comment\n',
        encoding="utf-8",
    )

    pub_b64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    write_public_key_to_app_metadata(pub_b64, metadata)

    updated = metadata.read_text(encoding="utf-8")
    assert f'LICENCE_PUBLIC_KEY = b"{pub_b64}"  # some comment' in updated


# ---------------------------------------------------------------------------
# Test 6 — missing LICENCE_PUBLIC_KEY pattern exits with code 2
# ---------------------------------------------------------------------------


def test_write_app_metadata_missing_pattern_errors(tmp_path: Path) -> None:
    """Writer raises SystemExit(2) when LICENCE_PUBLIC_KEY is absent."""
    metadata = tmp_path / "app_metadata.py"
    metadata.write_text(
        'APP_NAME = "School Tool"\nAPP_VERSION = "2.0.0"\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        write_public_key_to_app_metadata("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", metadata)

    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Test 7 — signature round-trip: sign with private, verify with public
# ---------------------------------------------------------------------------


def test_signature_roundtrip() -> None:
    """A keypair produced by generate_keypair() is valid for Ed25519 signing.

    Signs a known message with the private key and verifies with the public key.
    cryptography raises InvalidSignature if verification fails.
    """
    priv_raw, pub_raw = generate_keypair()

    priv_obj = Ed25519PrivateKey.from_private_bytes(priv_raw)
    pub_obj: Ed25519PublicKey = Ed25519PrivateKey.from_private_bytes(priv_raw).public_key()

    message = b"school-tool licence test payload"
    signature = priv_obj.sign(message)

    # verify() raises InvalidSignature on failure — no assertion needed beyond
    # confirming it does NOT raise.
    try:
        pub_obj.verify(signature, message)
    except InvalidSignature:
        pytest.fail("Ed25519 signature verification failed — keypair is invalid.")

    # Also confirm that verifying via the public key derived from pub_raw agrees.
    pub_from_raw: Ed25519PublicKey = Ed25519PublicKey.from_public_bytes(pub_raw)
    try:
        pub_from_raw.verify(signature, message)
    except InvalidSignature:
        pytest.fail(
            "Ed25519 signature verification failed via pub_raw — "
            "public key derivation is inconsistent."
        )
