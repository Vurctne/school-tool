"""Generate an Ed25519 keypair for School Tool licence signing.

Usage
-----
  python scripts/generate_licence_keypair.py
  python scripts/generate_licence_keypair.py --write-app-metadata
  python scripts/generate_licence_keypair.py --write-app-metadata --app-metadata-path PATH

The script prints both keys to stdout in a copy-friendly format and,
when --write-app-metadata is given, patches LICENCE_PUBLIC_KEY in
app_metadata.py (backing up the original first).

This is a one-shot operator tool.  Do NOT run it in CI or in automated
tests — import the module-level functions and call them directly instead.
"""

from __future__ import annotations

import argparse
import base64
import re
import shutil
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# ---------------------------------------------------------------------------
# Repo-root resolution (for the default --app-metadata-path)
# ---------------------------------------------------------------------------

_REPO = Path(__file__).parent.parent
_DEFAULT_APP_METADATA = _REPO / "app_metadata.py"

# Matches the LICENCE_PUBLIC_KEY assignment with any bytes literal value,
# optionally followed by a comment.  Group 1 = everything up to and including
# the closing quote; group 2 = the optional trailing comment (including any
# whitespace before it).
_KEY_RE = re.compile(
    r'^(LICENCE_PUBLIC_KEY\s*=\s*b"[^"]*")([ \t]*(?:#[^\n]*)?)',
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Core library functions (importable from tests without invoking the CLI)
# ---------------------------------------------------------------------------


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate a fresh Ed25519 keypair and return (priv_raw, pub_raw).

    Both byte strings are 32 bytes (the raw key material, not PEM/DER).
    """
    priv = Ed25519PrivateKey.generate()
    priv_raw: bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_raw: bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv_raw, pub_raw


def encode_key(raw: bytes) -> str:
    """Base64-encode *raw* key bytes and return an ASCII string (with padding)."""
    return base64.b64encode(raw).decode("ascii")


def write_public_key_to_app_metadata(pub_b64: str, path: Path) -> None:
    """Replace the LICENCE_PUBLIC_KEY assignment in *path* with *pub_b64*.

    Backs up the original to ``<path>.bak`` before writing.  Exits with
    code 2 if the pattern is not found so the caller can detect the error.

    Raises:
        SystemExit(2): when LICENCE_PUBLIC_KEY is not found in *path*.
    """
    original = path.read_text(encoding="utf-8")

    if not _KEY_RE.search(original):
        print(
            f"Error: could not find LICENCE_PUBLIC_KEY assignment in {path}; refusing to write.",
            file=sys.stderr,
        )
        sys.exit(2)

    replacement = rf'LICENCE_PUBLIC_KEY = b"{pub_b64}"\2'
    updated = _KEY_RE.sub(replacement, original)

    # Back up first, then overwrite.
    bak_path = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak_path)
    path.write_text(updated, encoding="utf-8")
    print(f"Backed up original to: {bak_path}")
    print(f"Updated: {path}")


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _print_output(pub_b64: str, priv_b64: str) -> None:
    """Print the keypair and next-steps instructions to stdout."""
    print("Generated Ed25519 keypair for School Tool licence signing.")
    print()
    print(f"PUB_BASE64={pub_b64}")
    print(f"PRIV_BASE64={priv_b64}")
    print()
    print("Next steps for the project owner:")
    print()
    print("  1. Set the private key as a Cloudflare Workers secret on the backend:")
    print("       wrangler secret put LICENCE_SIGNING_PRIVATE_KEY_ED25519")
    print("     Paste:")
    print(f"       {priv_b64}")
    print()
    print("  2. Embed the public key in the desktop binary by either:")
    print("       (a) Re-running this script with --write-app-metadata, OR")
    print("       (b) Manually editing app_metadata.py:")
    print(f'             LICENCE_PUBLIC_KEY = b"{pub_b64}"')
    print()
    print("  3. Rebuild the MSIX so the new public key ships with the desktop app:")
    print("       Build MSIX.bat")
    print()
    print("The private key MUST stay secret. Do not commit it to git, paste it")
    print("in chat, or share it. Cloudflare Workers secrets are encrypted at rest")
    print("and never echoed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an Ed25519 keypair for School Tool licence signing. "
            "Prints both keys to stdout. "
            "Optionally patches LICENCE_PUBLIC_KEY in app_metadata.py."
        ),
    )
    parser.add_argument(
        "--write-app-metadata",
        action="store_true",
        default=False,
        help=(
            "Write the public key into app_metadata.py's LICENCE_PUBLIC_KEY field. "
            "The original file is backed up to app_metadata.py.bak first."
        ),
    )
    parser.add_argument(
        "--app-metadata-path",
        type=Path,
        default=_DEFAULT_APP_METADATA,
        metavar="PATH",
        help="Path to app_metadata.py (default: %(default)s).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    priv_raw, pub_raw = generate_keypair()
    pub_b64 = encode_key(pub_raw)
    priv_b64 = encode_key(priv_raw)

    _print_output(pub_b64, priv_b64)

    if args.write_app_metadata:
        write_public_key_to_app_metadata(pub_b64, args.app_metadata_path)


if __name__ == "__main__":
    main()
