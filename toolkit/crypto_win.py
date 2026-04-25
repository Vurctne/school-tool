from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Guard: only attempt pywin32 import on Windows where it may be present.
_DPAPI_AVAILABLE: bool = False
_win32crypt: Any = None

if sys.platform == "win32":
    try:
        import win32crypt as _win32crypt  # type: ignore[import-untyped]

        _DPAPI_AVAILABLE = True
    except ImportError:
        pass


def available() -> bool:
    """Return True only on Windows with pywin32 installed."""
    return _DPAPI_AVAILABLE


def encrypt_to_file(path: Path, plaintext: bytes) -> None:
    """Encrypt *plaintext* with DPAPI and write the ciphertext to *path*.

    Raises RuntimeError on non-Windows or when pywin32 is absent.
    """
    if not _DPAPI_AVAILABLE or _win32crypt is None:
        raise RuntimeError("DPAPI not available on this platform")

    ciphertext: bytes = _win32crypt.CryptProtectData(
        plaintext,
        None,  # description
        None,  # optional entropy
        None,  # reserved
        None,  # prompt struct
        0,  # flags
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ciphertext)


def decrypt_from_file(path: Path) -> bytes:
    """Read ciphertext from *path* and decrypt it with DPAPI.

    Raises RuntimeError on non-Windows or when pywin32 is absent.
    Raises FileNotFoundError if *path* does not exist (propagated naturally).
    """
    if not _DPAPI_AVAILABLE or _win32crypt is None:
        raise RuntimeError("DPAPI not available on this platform")

    ciphertext = path.read_bytes()
    _description, plaintext = _win32crypt.CryptUnprotectData(
        ciphertext,
        None,  # optional entropy
        None,  # reserved
        None,  # prompt struct
        0,  # flags
    )
    result: bytes = plaintext
    return result
