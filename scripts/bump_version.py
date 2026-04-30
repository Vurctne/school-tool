"""Auto-increment APP_VERSION's BUILD (3rd segment) in app_metadata.py.

Reads the current ``APP_VERSION`` value from ``app_metadata.py``, parses it as
a 4-segment dotted version ``MAJOR.MINOR.BUILD.REVISION``, increments BUILD
by 1, resets REVISION to 0, and writes it back.

Why bump BUILD and not REVISION:
    Microsoft Store rejects MSIX submissions where the REVISION (4th segment)
    is non-zero — the manifest must end in `.0`. So every Store-bound build
    bumps BUILD instead, leaving REVISION pinned at 0.

Run:
    python scripts/bump_version.py

Output:
    Prints the new version string to stdout (so the build script can capture it).

Examples:
    "2.1.0.0"  ->  "2.1.1.0"
    "2.1.5.0"  ->  "2.1.6.0"
    "2.5.0.0"  ->  "2.5.1.0"

Manual MAJOR/MINOR changes:
    Edit ``app_metadata.py`` directly and reset BUILD + REVISION to 0 in the
    same edit so the next auto-bump produces the expected ``M.N.1.0``.

REVISION is reserved for hotfixes within the same BUILD (rare); bumping it
manually requires editing app_metadata.py by hand.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_METADATA = _REPO_ROOT / "app_metadata.py"

# Captures the 4 numeric segments. Stored on a single line:
#     APP_VERSION = "2.1.0.0"
_VERSION_LINE_RE = re.compile(
    r'^(APP_VERSION\s*=\s*")(\d+)\.(\d+)\.(\d+)\.(\d+)("\s*)$', re.MULTILINE
)


def main() -> int:
    if not _APP_METADATA.exists():
        print(f"ERROR: {_APP_METADATA} not found", file=sys.stderr)
        return 1

    text = _APP_METADATA.read_text(encoding="utf-8")
    match = _VERSION_LINE_RE.search(text)
    if match is None:
        print(
            f"ERROR: APP_VERSION not found in 4-part format in {_APP_METADATA}.\n"
            f'Expected: APP_VERSION = "MAJOR.MINOR.BUILD.REVISION"',
            file=sys.stderr,
        )
        return 2

    prefix, major, minor, build, _revision, suffix = match.groups()
    new_build = int(build) + 1
    new_version = f"{major}.{minor}.{new_build}.0"  # REVISION reset to 0

    new_text = text.replace(
        f"{prefix}{major}.{minor}.{build}.{_revision}{suffix}",
        f"{prefix}{new_version}{suffix}",
        1,
    )
    _APP_METADATA.write_text(new_text, encoding="utf-8")

    # Print only the version (no extra text) so the build script can capture
    # this directly via subprocess output.
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
