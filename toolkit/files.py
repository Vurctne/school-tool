"""Shared filesystem helpers for tools."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def open_output_folder(path: Path) -> None:
    """Open the OS file explorer at *path*'s parent directory, with *path* selected.

    Windows: uses ``explorer /select,"<path>"`` as a single shell command string —
        the list-form (``["explorer", "/select,", str(path)]``) breaks on paths
        with spaces (notably OneDrive paths under
        ``C:\\Users\\<name>\\OneDrive - ...``).
        See CLAUDE.md gotcha "OneDrive Open output folder" for context.
    macOS:   uses ``open -R <path>``.
    Linux:   uses ``xdg-open <parent>`` (no native "select" verb; opens the
        parent dir).

    Errors are logged at WARNING and swallowed — opening a folder is best-effort.
    """
    if not path.exists():
        logger.warning("open_output_folder: path does not exist: %s", path)
        return

    try:
        if sys.platform == "win32":
            # CRITICAL: single string, NOT a list — see CLAUDE.md OneDrive gotcha.
            # shell=False is intentional: we want Windows CreateProcess to receive
            # the string directly so explorer.exe's own parser handles the
            # /select,"<path>" form correctly for paths containing spaces.
            subprocess.Popen(f'explorer /select,"{path}"', shell=False)  # noqa: S603
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])  # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])  # noqa: S603,S607
    except OSError as exc:
        logger.warning("open_output_folder failed for %s: %s", path, exc)
