"""Entrypoint for the School Tool desktop application."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
import tkinter.messagebox as messagebox
import webbrowser

from app_metadata import APP_TITLE, APP_VERSION, STORE_PACKAGE_IDENTITY_NAME
from toolkit.fonts import detect_fonts
from toolkit.logging_setup import configure_logging
from toolkit.registry import all_tools
from toolkit.shell import TkShell
from toolkit.updates import UpdateInfo, check_for_store_updates

logger = logging.getLogger(__name__)


def main() -> int:
    log_path = configure_logging()

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("1440x900")
    root.minsize(960, 640)

    fonts = detect_fonts(root)

    shell = TkShell(root, fonts=fonts, tools=all_tools(), log_path=log_path)
    shell.pack(fill="both", expand=True)

    # Round 30 — check the Microsoft Store for updates on startup. The
    # check runs on a worker thread so the UI is never blocked; if an
    # update is pending the dialog is scheduled onto the Tk main loop.
    # Failure modes (offline, sideloaded install, non-Windows) all
    # return None silently — no error surfaced to the user.
    _schedule_update_check(root)

    root.mainloop()
    return 0


# ---------------------------------------------------------------------------
# Round 30 — Microsoft Store update prompt
# ---------------------------------------------------------------------------


def _schedule_update_check(root: tk.Tk) -> None:
    """Fire ``check_for_store_updates`` on a daemon thread, hand the
    result back to the Tk main loop via ``root.after``."""

    def _worker() -> None:
        try:
            info = check_for_store_updates()
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.debug("Update check raised: %s", exc)
            return
        if info is None:
            return
        # Marshal back to the Tk main thread. ``root.after(0, …)``
        # queues the callback for the next idle tick.  Guard for the
        # shutdown race — if the user closed the window during the
        # ~5 s WinRT call, root.after raises RuntimeError or
        # tk.TclError.  Swallow silently; the update prompt will
        # naturally re-appear on next launch (Round 30 design).
        try:
            root.after(0, lambda: _show_update_dialog(root, info))
        except (RuntimeError, tk.TclError) as exc:
            logger.debug("Update dialog skipped — Tk torn down: %s", exc)

    t = threading.Thread(target=_worker, daemon=True, name="update-check")
    t.start()


def _show_update_dialog(root: tk.Tk, info: UpdateInfo) -> None:
    """Modal askyesno dialog: 'Update available — open the Microsoft
    Store now?'."""
    title = "Update available"
    body_lines = [
        "A new version of School Tool is available in the Microsoft Store.",
        f"You're on v{APP_VERSION}.",
        "",
    ]
    if info.is_mandatory:
        body_lines.append("This is a required update — please install it as soon as you can.")
    else:
        body_lines.append("Updates ship bug fixes and new features — installing is recommended.")
    body_lines.append("")
    body_lines.append("Open the Microsoft Store now?")
    message = "\n".join(body_lines)

    try:
        wants_open = messagebox.askyesno(title, message, parent=root)
    except Exception as exc:  # noqa: BLE001 — Tk may be torn down on close
        logger.debug("Update dialog failed: %s", exc)
        return

    if wants_open:
        _open_store_listing()


def _open_store_listing() -> None:
    """Open the Microsoft Store page for our app.

    Uses the ``ms-windows-store://search?query=…`` URI scheme — the
    same protocol the OS itself uses to deep-link Store listings.
    Falls back to a no-op on non-Windows / when the protocol handler
    is unregistered (we don't surface an error: the user already saw
    the dialog and clicked Yes).
    """
    url = f"ms-windows-store://search/?query={STORE_PACKAGE_IDENTITY_NAME}"
    try:
        webbrowser.open(url)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.debug("Could not open Store listing: %s", exc)


if __name__ == "__main__":
    raise SystemExit(main())
