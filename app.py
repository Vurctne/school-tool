"""Entrypoint for the School Tool desktop application."""

from __future__ import annotations

import tkinter as tk

from app_metadata import APP_TITLE
from toolkit.fonts import detect_fonts
from toolkit.logging_setup import configure_logging
from toolkit.registry import all_tools
from toolkit.shell import TkShell


def main() -> int:
    log_path = configure_logging()

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("1200x820")
    root.minsize(960, 640)

    fonts = detect_fonts(root)

    shell = TkShell(root, fonts=fonts, tools=all_tools(), log_path=log_path)
    shell.pack(fill="both", expand=True)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
