"""Shared widget primitives for the School Tool shell and tools.

Every class/factory accepts a parent widget and produces a fully-styled ttk
sub-widget. All colours and spacings are imported from toolkit.tokens —
nothing is hard-coded here.
"""

from __future__ import annotations

import datetime
import logging
import re
import sys
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.font as tkfont
import tkinter.ttk as ttk
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from toolkit import tokens
from toolkit.base_tool import BannerLevel, LogLine, RailItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MSIX-relative LocalCache root (for SecretField DPAPI storage)
# ---------------------------------------------------------------------------
_MSIX_FAMILY_NAME = "SchoolTool_vurctne"


def _localcache_dir() -> Path:
    import os

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            return Path(local_app_data) / "Packages" / _MSIX_FAMILY_NAME / "LocalCache"
    return Path.home() / ".local" / "share" / "school-tool" / "cache"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_font(
    family: str,
    size: int,
    weight: Literal["normal", "bold"] = "normal",
) -> tkfont.Font:
    return tkfont.Font(family=family, size=size, weight=weight)


# ---------------------------------------------------------------------------
# SectionHeader
# ---------------------------------------------------------------------------


class SectionHeader(ttk.Frame):
    """16 px bold title + optional muted 13 px subtitle."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        subtitle: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)

        title_font = _make_font("Segoe UI", tokens.FS_16, "bold")
        title_lbl = tk.Label(
            self,
            text=title,
            font=title_font,
            fg=tokens.FG_1,
            bg=tokens.BG_MUTED,
            anchor="w",
        )
        title_lbl.pack(side="top", fill="x")

        if subtitle:
            sub_font = _make_font("Segoe UI", tokens.FS_13)
            sub_lbl = tk.Label(
                self,
                text=subtitle,
                font=sub_font,
                fg=tokens.FG_MUTED,
                bg=tokens.BG_MUTED,
                anchor="w",
                wraplength=820,
                justify="left",
            )
            sub_lbl.pack(side="top", fill="x", pady=(tokens.SP_1, 0))


# ---------------------------------------------------------------------------
# FileRow
# ---------------------------------------------------------------------------


class FileRow(ttk.Frame):
    """Label-on-top file picker with fixed-width entry + Browse button.

    Round 40b — switched from inline label (26-char column, which
    truncated longer labels like "Compass Expense file (used by
    Generate budget workbook)") to stacked layout: label spans the
    full row above, entry + Browse sit on row 2 at a fixed width.

    Override ``width=`` to change the entry width (default 60 chars
    fits typical Windows paths like ``C:\\Users\\…\\Master Budget.xlsm``).
    """

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        on_pick: Callable[[Path], None],
        filetypes: list[tuple[str, str]],
        initial_path: Path | None = None,
        optional: bool = False,
        width: int = 60,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)

        self._on_pick = on_pick
        self._filetypes = filetypes
        self._var = tk.StringVar(value=str(initial_path) if initial_path else "")

        # Round 40b — full-width label on its own row.
        label_text = label if not optional else f"{label} (optional)"
        lbl = tk.Label(
            self,
            text=label_text,
            anchor="w",
            fg=tokens.FG_1,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_13),
        )
        lbl.pack(side="top", fill="x")

        # Round 40b — entry + Browse on row 2, anchored left.  No
        # fill="x"/expand=True so the entry stays at its declared
        # width regardless of panel width.
        row = tk.Frame(self, bg=tokens.BG_MUTED)
        row.pack(side="top", anchor="w")

        self._entry = tk.Entry(
            row,
            textvariable=self._var,
            width=width,
            state="readonly",
            readonlybackground=tokens.BG_READONLY,
            fg=tokens.FG_1,
            font=_make_font("Cascadia Mono", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        self._entry.pack(side="left", padx=(0, tokens.SP_3))

        self._browse_btn = ttk.Button(row, text="Browse", command=self._browse)
        self._browse_btn.pack(side="left")

    def _browse(self) -> None:
        path_str = filedialog.askopenfilename(filetypes=self._filetypes)
        if path_str:
            self._var.set(path_str)
            self._on_pick(Path(path_str))

    def get_path(self) -> Path | None:
        v = self._var.get()
        return Path(v) if v else None

    def set_path(self, path: Path) -> None:
        self._var.set(str(path))

    def set_state(self, state: str) -> None:
        """Set to 'normal' or 'disabled'."""
        self._browse_btn.configure(state=state)
        # Entry stays readonly; just toggle the button.


# ---------------------------------------------------------------------------
# TextField
# ---------------------------------------------------------------------------


class TextField(ttk.Frame):
    """Labelled text entry with optional placeholder and max_length.

    Round 40 — entry width is now fixed (default 32 chars, override
    via ``width=``). The label still spans the full parent width so
    the input row aligns left; only the Entry box is capped, which
    stops it from stretching to the whole panel on wide windows.
    """

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str = "",
        placeholder: str = "",
        max_length: int | None = None,
        width: int = 32,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)

        self._max_length = max_length
        self._placeholder = placeholder
        self._var = tk.StringVar(value=value)

        lbl = tk.Label(
            self,
            text=label,
            anchor="w",
            fg=tokens.FG_1,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_13),
        )
        lbl.pack(side="top", fill="x")

        self._entry = tk.Entry(
            self,
            textvariable=self._var,
            width=width,
            fg=tokens.FG_1,
            font=_make_font("Segoe UI", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        # Round 40 — anchor="w" instead of fill="x" so the entry stays
        # at its declared width on the left of the row.
        self._entry.pack(side="top", anchor="w")

        if max_length is not None:
            self._var.trace_add("write", self._enforce_max)

        if placeholder:
            self._show_placeholder()
            self._entry.bind("<FocusIn>", self._clear_placeholder)
            self._entry.bind("<FocusOut>", self._show_placeholder)

    def _enforce_max(self, *_: Any) -> None:
        if self._max_length and len(self._var.get()) > self._max_length:
            self._var.set(self._var.get()[: self._max_length])

    def _show_placeholder(self, *_: Any) -> None:
        if not self._var.get():
            self._entry.configure(fg=tokens.FG_3)
            self._entry.insert(0, self._placeholder)

    def _clear_placeholder(self, *_: Any) -> None:
        if self._entry.get() == self._placeholder:
            self._entry.delete(0, "end")
            self._entry.configure(fg=tokens.FG_1)

    def get(self) -> str:
        v = self._var.get()
        if v == self._placeholder:
            return ""
        return v

    def set(self, value: str) -> None:
        self._var.set(value)


# ---------------------------------------------------------------------------
# NumberField
# ---------------------------------------------------------------------------


class NumberField(ttk.Frame):
    """Numeric entry with optional min/max validation and decimal places.

    Round 40 — entry width is fixed (default 12 chars, suitable for
    "999,999.99" with breathing room). Override via ``width=``.
    """

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str = "",
        min_value: float | None = None,
        max_value: float | None = None,
        decimals: int = 0,
        width: int = 12,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)

        self._min = min_value
        self._max = max_value
        self._decimals = decimals
        self._var = tk.StringVar(value=value)

        lbl = tk.Label(
            self,
            text=label,
            anchor="w",
            fg=tokens.FG_1,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_13),
        )
        lbl.pack(side="top", fill="x")

        vcmd = (self.register(self._validate), "%P")
        self._entry = tk.Entry(
            self,
            textvariable=self._var,
            width=width,
            validate="key",
            validatecommand=vcmd,
            fg=tokens.FG_1,
            font=_make_font("Segoe UI", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        # Round 40 — anchor="w" replaces fill="x" so the box doesn't
        # stretch to fill the panel.
        self._entry.pack(side="top", anchor="w")

    def _validate(self, new_value: str) -> bool:
        if new_value == "" or new_value == "-":
            return True
        try:
            float(new_value)
        except ValueError:
            return False
        # Check decimal places
        if "." in new_value and self._decimals == 0:
            return False
        if "." in new_value:
            parts = new_value.split(".")
            if len(parts[1]) > self._decimals:
                return False
        return True

    def get(self) -> str:
        return self._var.get()

    def get_value(self) -> float | None:
        try:
            v = float(self._var.get())
            if self._min is not None and v < self._min:
                return None
            if self._max is not None and v > self._max:
                return None
            return v
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# CurrencyField
# ---------------------------------------------------------------------------


class CurrencyField(ttk.Frame):
    """AUD currency entry: $ prefix + 2-decimal numeric. Exposes .get_cents()."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str = "",
        width: int = 14,
        **kwargs: Any,
    ) -> None:
        # Round 40 — entry width fixed (default 14 chars: fits
        # "9,999,999.99" with breathing room). Override via ``width=``.
        super().__init__(parent, **kwargs)

        self._var = tk.StringVar(value=value)

        lbl = tk.Label(
            self,
            text=label,
            anchor="w",
            fg=tokens.FG_1,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_13),
        )
        lbl.pack(side="top", fill="x")

        row = tk.Frame(self, bg=tokens.BG_MUTED)
        row.pack(side="top", anchor="w")

        prefix = tk.Label(
            row,
            text="$",
            fg=tokens.FG_1,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_13),
        )
        prefix.pack(side="left")

        vcmd = (self.register(self._validate), "%P")
        self._entry = tk.Entry(
            row,
            textvariable=self._var,
            width=width,
            validate="key",
            validatecommand=vcmd,
            fg=tokens.FG_1,
            font=_make_font("Segoe UI", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        # Round 40 — no fill="x"/expand=True so the entry stays at
        # the declared width regardless of panel width.
        self._entry.pack(side="left")

    def _validate(self, new_value: str) -> bool:
        if new_value == "":
            return True
        try:
            float(new_value)
        except ValueError:
            return False
        if "." in new_value:
            parts = new_value.split(".")
            if len(parts[1]) > 2:
                return False
        return True

    def get(self) -> str:
        return self._var.get()

    def get_cents(self) -> int:
        """Return value as integer cents (e.g. 20000.00 → 2000000)."""
        raw = self._var.get().strip()
        if not raw:
            return 0
        try:
            from decimal import Decimal

            return int(Decimal(raw) * 100)
        except Exception:
            return 0


# ---------------------------------------------------------------------------
# DateField
# ---------------------------------------------------------------------------


class DateField(ttk.Frame):
    """Date picker (tkcalendar if available, else plain DD/MM/YYYY entry)."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        default: str = "today",
        width: int = 12,
        **kwargs: Any,
    ) -> None:
        # Round 40 — entry width fixed (default 12 chars: DD/MM/YYYY = 10
        # chars + dropdown affordance). Override via ``width=``.
        super().__init__(parent, **kwargs)

        today = datetime.date.today()
        init_date = today if default == "today" else None

        lbl = tk.Label(
            self,
            text=label,
            anchor="w",
            fg=tokens.FG_1,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_13),
        )
        lbl.pack(side="top", fill="x")

        self._calendar_widget: Any = None

        try:
            from tkcalendar import (  # type: ignore[import-not-found]
                DateEntry,
            )

            kw: dict[str, Any] = dict(
                date_pattern="dd/mm/yyyy",
                font=_make_font("Segoe UI", tokens.FS_13),
                width=width,
            )
            if init_date:
                kw["year"] = init_date.year
                kw["month"] = init_date.month
                kw["day"] = init_date.day
            self._calendar_widget = DateEntry(self, **kw)
            self._calendar_widget.pack(side="top", anchor="w")
            self._mode = "calendar"
        except ImportError:
            # Fallback: plain entry with DD/MM/YYYY validation
            init_val = today.strftime("%d/%m/%Y") if init_date else ""
            self._var = tk.StringVar(value=init_val)
            self._entry = tk.Entry(
                self,
                textvariable=self._var,
                width=width,
                fg=tokens.FG_1,
                font=_make_font("Segoe UI", tokens.FS_13),
                relief="sunken",
                bd=1,
            )
            self._entry.pack(side="top", anchor="w")
            self._mode = "entry"

    def get_date(self) -> datetime.date | None:
        """Return the selected date, or None if invalid."""
        if self._mode == "calendar" and self._calendar_widget is not None:
            try:
                return self._calendar_widget.get_date()  # type: ignore[no-any-return]
            except Exception:
                return None
        else:
            raw = self._var.get().strip()
            try:
                return datetime.datetime.strptime(raw, "%d/%m/%Y").date()
            except ValueError:
                return None

    def get(self) -> str:
        d = self.get_date()
        return d.strftime("%d/%m/%Y") if d else ""


# ---------------------------------------------------------------------------
# SecretField
# ---------------------------------------------------------------------------


class SecretField(ttk.Frame):
    """Masked entry with eye-toggle + optional 'Remember on this device' checkbox."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        pattern: str = r".+",
        remember_key: str | None = None,
        width: int = 20,
        **kwargs: Any,
    ) -> None:
        # Round 40 — entry width fixed (default 20 chars; HYIA SIN is
        # 4-6 digits but secrets in general can be longer).
        super().__init__(parent, **kwargs)

        self._pattern = re.compile(pattern)
        self._remember_key = remember_key
        self._var = tk.StringVar()
        self._show_var = tk.BooleanVar(value=False)
        self._remember_var = tk.BooleanVar(value=False)

        lbl = tk.Label(
            self,
            text=label,
            anchor="w",
            fg=tokens.FG_1,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_13),
        )
        lbl.pack(side="top", fill="x")

        row = tk.Frame(self, bg=tokens.BG_MUTED)
        row.pack(side="top", anchor="w")

        self._entry = tk.Entry(
            row,
            textvariable=self._var,
            width=width,
            show="●",
            fg=tokens.FG_1,
            font=_make_font("Segoe UI", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        # Round 40 — drop fill="x"/expand=True so the entry stays at
        # its declared width (the eye-toggle button is right next to it).
        self._entry.pack(side="left", padx=(0, tokens.SP_2))
        self._entry.bind("<FocusOut>", self._on_blur)

        self._eye_btn = ttk.Button(row, text="Show", width=6, command=self._toggle_show)
        self._eye_btn.pack(side="left")

        if remember_key:
            cb = ttk.Checkbutton(
                self,
                text="Remember on this device",
                variable=self._remember_var,
                command=self._on_remember_toggled,
            )
            cb.pack(side="top", anchor="w", pady=(tokens.SP_1, 0))
            # Attempt to pre-fill from stored value
            self._try_load_stored()

    def _toggle_show(self) -> None:
        if self._show_var.get():
            self._show_var.set(False)
            self._entry.configure(show="●")
            self._eye_btn.configure(text="Show")
        else:
            self._show_var.set(True)
            self._entry.configure(show="")
            self._eye_btn.configure(text="Hide")

    def _on_blur(self, _event: Any = None) -> None:
        if self._remember_key and self._remember_var.get():
            self._persist()

    def _on_remember_toggled(self) -> None:
        if self._remember_key and self._remember_var.get():
            self._persist()

    def _persist(self) -> None:
        if not self._remember_key:
            return
        value = self._var.get()
        if not value:
            return
        try:
            from toolkit.crypto_win import encrypt_to_file

            cache_dir = _localcache_dir()
            cache_dir.mkdir(parents=True, exist_ok=True)
            dat_path = cache_dir / f"{self._remember_key}.dat"
            encrypt_to_file(dat_path, value.encode())
        except Exception as exc:
            logger.warning("SecretField: could not persist %r: %s", self._remember_key, exc)

    def _try_load_stored(self) -> None:
        if not self._remember_key:
            return
        try:
            from toolkit.crypto_win import decrypt_from_file

            dat_path = _localcache_dir() / f"{self._remember_key}.dat"
            if dat_path.exists():
                plaintext = decrypt_from_file(dat_path)
                self._var.set(plaintext.decode())
                self._remember_var.set(True)
        except Exception as exc:
            logger.debug("SecretField: no stored value for %r: %s", self._remember_key, exc)

    def get(self) -> str:
        return self._var.get()

    def is_valid(self) -> bool:
        return bool(self._pattern.fullmatch(self._var.get()))


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

_BANNER_STYLES: dict[str, dict[str, str]] = {
    "neutral": {"bg": tokens.BG_MUTED, "fg": tokens.FG_1},
    "ok": {"bg": tokens.OK_BG, "fg": tokens.OK_FG},
    "warning": {"bg": tokens.WARN_BG, "fg": tokens.WARN_FG},
    "danger": {"bg": tokens.DANGER_BG, "fg": tokens.DANGER_FG},
    "info": {"bg": tokens.INFO_BG, "fg": tokens.INFO_FG},
}


class Banner(tk.Frame):
    """Status/result banner: 5 levels with token-sourced colours."""

    def __init__(
        self,
        parent: tk.Widget,
        level: BannerLevel,
        text: str,
        **kwargs: Any,
    ) -> None:
        style = _BANNER_STYLES.get(level, _BANNER_STYLES["neutral"])
        super().__init__(parent, bg=style["bg"], **kwargs)

        self._label = tk.Label(
            self,
            text=text,
            fg=style["fg"],
            bg=style["bg"],
            font=_make_font("Segoe UI", tokens.FS_13),
            anchor="w",
            justify="left",
            wraplength=900,
            padx=tokens.SP_3,
            pady=tokens.SP_2,
        )
        self._label.pack(fill="both", expand=True)

    def update_text(self, text: str, level: BannerLevel | None = None) -> None:
        style = _BANNER_STYLES.get(level or "neutral", _BANNER_STYLES["neutral"])
        self._label.configure(text=text, fg=style["fg"], bg=style["bg"])
        self.configure(bg=style["bg"])


# ---------------------------------------------------------------------------
# ProgressBar
# ---------------------------------------------------------------------------


class ProgressBar(ttk.Frame):
    """16 px tall progress bar with status text. Uses ttk.Progressbar (vista style)."""

    def __init__(self, parent: tk.Widget, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)

        self._msg_var = tk.StringVar(value="Ready")
        self._pct_var = tk.IntVar(value=0)

        self._msg_lbl = tk.Label(
            self,
            textvariable=self._msg_var,
            fg=tokens.FG_2,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_13),
            anchor="w",
        )
        self._msg_lbl.pack(side="top", fill="x")

        self._bar = ttk.Progressbar(
            self,
            variable=self._pct_var,
            maximum=100,
            mode="determinate",
            style="TProgressbar",
        )
        self._bar.configure(length=400)
        self._bar.pack(side="top", fill="x", pady=(tokens.SP_1, 0))
        # Fixed height of 16 px via pack configure
        self._bar.configure(length=16)

    def set(self, percent: int, message: str) -> None:
        self._pct_var.set(max(0, min(100, percent)))
        self._msg_var.set(message)


# ---------------------------------------------------------------------------
# LogView
# ---------------------------------------------------------------------------

_LOG_TAG_COLOURS: dict[str, str] = {
    "heading": tokens.FG_1,
    "ok": tokens.OK_FG,
    "warning": tokens.WARN_FG,
    "danger": tokens.DANGER_FG,
    "extra": tokens.LOG_EXTRA_FG,
    "muted": tokens.FG_MUTED,
}


class LogView(tk.Frame):
    """Monospace log viewer with per-tag colour styling."""

    def __init__(self, parent: tk.Widget, min_height: int = 160, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)

        self._text = tk.Text(
            self,
            font=_make_font("Cascadia Mono", tokens.FS_12),
            bg=tokens.BG_PANEL,
            fg=tokens.FG_1,
            relief="sunken",
            bd=1,
            wrap="none",
            state="disabled",
            height=max(6, min_height // 18),
        )
        self._text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._text.yview)
        scrollbar.pack(side="right", fill="y")
        self._text.configure(yscrollcommand=scrollbar.set)

        # Configure all log tags
        for tag, colour in _LOG_TAG_COLOURS.items():
            self._text.tag_configure(
                tag,
                foreground=colour,
                font=_make_font(
                    "Cascadia Mono",
                    tokens.FS_12,
                    "bold" if tag == "heading" else "normal",
                ),
            )

    def append(self, line: LogLine) -> None:
        self._text.configure(state="normal")
        tag = line.tag or ""
        content = (line.text or "\u00a0") + "\n"
        if tag and tag in _LOG_TAG_COLOURS:
            self._text.insert("end", content, tag)
        else:
            self._text.insert("end", content)
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class Table(ttk.Frame):
    """ttk.Treeview with vista theme; numeric cols right-aligned + Cascadia Mono.

    columns: list of dicts with keys: key, label, width (optional), align (optional),
             mono (optional bool for numeric columns).

    Optional kwargs (phase-3 additions):
        row_style:    Callable[[dict], dict[str, str]] — per-row Tkinter option dict.
                      Takes precedence over legacy ``_bg``/``_fg`` row keys when present.
        on_row_click: Callable[[dict], None] — invoked with the full row dict on selection.
    """

    def __init__(
        self,
        parent: tk.Widget,
        columns: list[dict[str, Any]],
        min_height: int = 200,
        row_style: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        on_row_click: Callable[[dict[str, Any]], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)

        col_ids = [str(c["key"]) for c in columns]
        self._columns = columns
        self._row_style = row_style
        self._on_row_click = on_row_click
        self._rows: list[dict[str, Any]] = []  # live snapshot for click lookup

        self._tree = ttk.Treeview(
            self,
            columns=col_ids,
            show="headings",
            height=max(5, min_height // 22),
        )

        # Configure columns and headings.
        # stretch=True on all columns causes Tk to recompute column widths on
        # every pixel of a resize drag (O(n_cols) per tick).  Only the LAST
        # column stretches to fill remaining space; all others use fixed widths.
        # This reduces layout work dramatically for tables with many columns
        # (e.g. Sub-Program has 7 columns).  (Fix 2 — Round 13)
        mono_font = _make_font("Cascadia Mono", tokens.FS_12)
        last_col_idx = len(columns) - 1
        for i, col in enumerate(columns):
            cid = str(col["key"])
            width = int(col.get("width", 120))
            is_right = col.get("align") == "right" or col.get("mono")
            col_anchor: Literal["e", "w"] = "e" if is_right else "w"
            # Only the last column stretches; others keep their declared widths.
            col_stretch = i == last_col_idx
            self._tree.heading(cid, text=str(col["label"]))
            self._tree.column(cid, width=width, anchor=col_anchor, stretch=col_stretch)

        # Scrollbars
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Alternating row tags
        self._tree.tag_configure("alt", background=tokens.BG_ROW_ALT)

        # Mono font tag for numeric cells (applied per column via tags on rows)
        self._mono_font = mono_font

        # Row-click binding (set once; remains valid across set_rows calls)
        if on_row_click is not None:
            self._tree.bind("<<TreeviewSelect>>", self._on_select)

    def _on_select(self, _event: Any = None) -> None:
        """Internal handler: reconstruct row dict and invoke on_row_click."""
        if self._on_row_click is None:
            return
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        # iid was stored as the row index during insert
        try:
            idx = int(self._tree.item(iid, "text"))
        except (ValueError, tk.TclError):
            return
        if 0 <= idx < len(self._rows):
            self._on_row_click(self._rows[idx])

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        # Save live snapshot for click reconstruction
        self._rows = list(rows)

        # Clear existing
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        for i, row in enumerate(rows):
            values = [str(row.get(str(c["key"]), "")) for c in self._columns]
            tags: list[str] = []

            # Phase-3: row_style takes precedence over legacy _bg/_fg keys
            style_opts: dict[str, str] = {}
            if self._row_style is not None:
                style_opts = self._row_style(row)

            if style_opts:
                tag_name = f"style_{i}"
                # Round 22 — accept an optional ``font`` key so callers can
                # render italic / muted "comment sub-rows" inline beneath
                # their parent data row.  Falls through to no-font when the
                # caller doesn't supply one (default Tk Treeview font).
                tag_kwargs: dict[str, Any] = {
                    "background": style_opts.get("background", ""),
                    "foreground": style_opts.get("foreground", ""),
                }
                if "font" in style_opts:
                    tag_kwargs["font"] = style_opts["font"]
                self._tree.tag_configure(tag_name, **tag_kwargs)
                tags.append(tag_name)
            else:
                bg = row.get("_bg")
                fg = row.get("_fg")

                if bg or fg:
                    tag_name = f"custom_{i}"
                    self._tree.tag_configure(
                        tag_name,
                        background=str(bg) if bg else "",
                        foreground=str(fg) if fg else "",
                    )
                    tags.append(tag_name)
                elif i % 2:
                    tags.append("alt")

            # Store row index as the item's "text" field for click reconstruction
            self._tree.insert("", "end", text=str(i), values=values, tags=tags)


# ---------------------------------------------------------------------------
# SelectableList
# ---------------------------------------------------------------------------


class SelectableList(tk.Frame):
    """Scrollable vertical list of label+value rows with click-to-select.

    Used as the in-tool side rail (Sub-Program faculty filter) and inside
    CommentaryDialog (sub-program picker).

    Parameters
    ----------
    parent:
        Parent widget.
    items:
        Initial list of RailItem entries to render.
    on_select:
        Callback invoked with ``item.filter_key`` when the user clicks a row
        or navigates with Up/Down arrow keys.
    focus_on_mount:
        When True the inner canvas receives focus immediately after mount.
        Pass True from CommentaryDialog; leave False for the in-tool rail.
    width:
        Fixed width in pixels.  Default 220 matches the locked shell rail width.
    """

    def __init__(
        self,
        parent: tk.Widget,
        items: list[RailItem],
        on_select: Callable[[str], None],
        *,
        focus_on_mount: bool = False,
        width: int = 220,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)

        self._on_select = on_select
        self._active_key: str | None = None
        self._item_list: list[RailItem] = []
        self._row_frames: dict[str, tk.Frame] = {}
        self._row_labels: dict[str, tk.Label] = {}
        self._row_badges: dict[str, tk.Label] = {}
        self._focus_on_mount = focus_on_mount
        self._width = width
        # Debounce after() ids for resize handlers — cancel-and-reschedule so
        # layout math runs only once per ~100 ms idle (raised from 50 ms in
        # Round 14), not on every pixel drag.  This reduces flicker frequency
        # during window-drag while keeping settle latency acceptably low.
        self._inner_configure_after: str | None = None
        self._canvas_configure_after: str | None = None

        # Outer border frame
        border = tk.Frame(self, bg=tokens.BORDER_SUBTLE, bd=0)
        border.pack(fill="both", expand=True)

        # Canvas + scrollbar
        self._canvas = tk.Canvas(
            border,
            bg=tokens.BG_INSET,
            highlightthickness=0,
            bd=0,
        )
        scrollbar = ttk.Scrollbar(border, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        # Inner frame (holds the row widgets)
        self._inner = tk.Frame(self._canvas, bg=tokens.BG_INSET)
        self._window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Keyboard navigation
        self._canvas.configure(takefocus=True)
        self._canvas.bind("<Up>", lambda e: self._nav(-1))
        self._canvas.bind("<Down>", lambda e: self._nav(1))
        self._canvas.bind("<Button-1>", lambda e: self._canvas.focus_set())
        self._inner.bind("<Up>", lambda e: self._nav(-1))
        self._inner.bind("<Down>", lambda e: self._nav(1))

        # Populate initial items
        self.set_items(items)

        if focus_on_mount:
            self._canvas.after_idle(self._canvas.focus_set)

    # ------------------------------------------------------------------
    # Private layout callbacks
    # ------------------------------------------------------------------

    def _on_inner_configure(self, _event: Any) -> None:
        # Debounce: cancel any pending call and reschedule 100 ms out.
        # This fires on every pixel of an inner-frame size change — batching
        # via after() prevents layout thrash during rapid window resizes.
        if self._inner_configure_after is not None:
            try:
                self._canvas.after_cancel(self._inner_configure_after)
            except tk.TclError:
                pass
        self._inner_configure_after = self._canvas.after(100, self._do_inner_configure)

    def _do_inner_configure(self) -> None:
        """Deferred scroll-region update — runs once per 100 ms idle window."""
        self._inner_configure_after = None
        try:
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        except tk.TclError:
            pass  # widget may have been destroyed between schedule and fire

    def _on_canvas_configure(self, event: Any) -> None:
        # Debounce: same approach — fire the itemconfig once per idle window.
        w = event.width
        if self._canvas_configure_after is not None:
            try:
                self._canvas.after_cancel(self._canvas_configure_after)
            except tk.TclError:
                pass
        self._canvas_configure_after = self._canvas.after(100, lambda: self._do_canvas_configure(w))

    def _do_canvas_configure(self, width: int) -> None:
        """Deferred canvas-window width update — runs once per 100 ms idle window."""
        self._canvas_configure_after = None
        try:
            self._canvas.itemconfig(self._window, width=width)
        except tk.TclError:
            pass  # widget may have been destroyed between schedule and fire

    # ------------------------------------------------------------------
    # Row building
    # ------------------------------------------------------------------

    def _build_rows(self) -> None:
        """Destroy all existing row widgets and rebuild from self._item_list."""
        for widget in self._inner.winfo_children():
            widget.destroy()
        self._row_frames.clear()
        self._row_labels.clear()
        self._row_badges.clear()

        label_font = _make_font(tokens.FONT_SANS_FALLBACK, tokens.FS_13)
        badge_font = _make_font(tokens.FONT_MONO_PRIMARY, tokens.FS_12)

        for idx, item in enumerate(self._item_list):
            # Determine base background (alternating or highlight)
            if item.highlight:
                base_bg = tokens.RAIL_HL_BG
            elif idx % 2 == 0:
                base_bg = tokens.BG_INSET
            else:
                base_bg = tokens.BG_ROW_ALT

            row_frame = tk.Frame(
                self._inner,
                bg=base_bg,
                cursor="hand2",
            )
            row_frame.pack(fill="x")

            # Round 22d — pack the optional data-bar FIRST so it claims
            # the bottom 3px of the row.  Subsequent label/badge widgets
            # then fill the remaining height.  Pack ordering matters: a
            # widget packed later with side=bottom only gets the
            # leftover bottom area, so the bar must come before the
            # label/badge to be visible.  Backwards-compatible: when
            # value_pct is None no bar is packed and the row looks
            # identical to the pre-22d rail.
            if item.value_pct is not None:
                pct_clamped = max(0.0, min(100.0, item.value_pct))
                if item.value_pct > 110:
                    bar_color = tokens.DANGER_FG
                elif item.value_pct > 100:
                    bar_color = tokens.WARN_FG
                else:
                    bar_color = tokens.OK_FG
                bar_track = tk.Frame(
                    row_frame,
                    bg=tokens.BORDER_SUBTLE,
                    height=3,
                )
                bar_track.pack(side="bottom", fill="x")
                bar_track.pack_propagate(False)
                bar_fill = tk.Frame(bar_track, bg=bar_color)
                bar_fill.place(x=0, y=0, relwidth=pct_clamped / 100.0, relheight=1.0)

            lbl = tk.Label(
                row_frame,
                text=item.label,
                font=label_font,
                fg=tokens.FG_1,
                bg=base_bg,
                anchor="w",
                padx=tokens.SP_2,
                pady=tokens.SP_1,
            )
            lbl.pack(side="left", fill="x", expand=True)

            badge = tk.Label(
                row_frame,
                text=item.value,
                font=badge_font,
                fg=tokens.FG_2,
                bg=base_bg,
                anchor="e",
                padx=tokens.SP_2,
                pady=tokens.SP_1,
            )
            badge.pack(side="right")

            self._row_frames[item.filter_key] = row_frame
            self._row_labels[item.filter_key] = lbl
            self._row_badges[item.filter_key] = badge

            # Bind click on every sub-widget
            def _make_click(key: str) -> Callable[..., None]:
                def _click(*_: Any) -> None:
                    self.set_active(key)
                    self._on_select(key)

                return _click

            click_cb = _make_click(item.filter_key)
            row_frame.bind("<Button-1>", click_cb)
            lbl.bind("<Button-1>", click_cb)
            badge.bind("<Button-1>", click_cb)

        # Restore active highlight if still present
        if self._active_key in self._row_frames:
            self._apply_active(self._active_key)

    def _row_base_bg(self, filter_key: str) -> str:
        """Return the default (non-selected) background for the given row."""
        for idx, item in enumerate(self._item_list):
            if item.filter_key == filter_key:
                if item.highlight:
                    return tokens.RAIL_HL_BG
                return tokens.BG_INSET if idx % 2 == 0 else tokens.BG_ROW_ALT
        return tokens.BG_INSET

    def _apply_active(self, key: str | None) -> None:
        """Paint the active row blue; restore all others to their base colour."""
        for fk, frame in self._row_frames.items():
            lbl = self._row_labels.get(fk)
            badge = self._row_badges.get(fk)
            if fk == key:
                bg = tokens.RAIL_SELECTED
                fg = tokens.FG_INVERSE
            else:
                bg = self._row_base_bg(fk)
                fg = tokens.FG_1
            frame.configure(bg=bg)
            if lbl:
                lbl.configure(bg=bg, fg=fg)
            if badge:
                badge.configure(bg=bg, fg=fg)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _nav(self, direction: int) -> str:
        keys = [item.filter_key for item in self._item_list]
        if not keys:
            return "break"
        if self._active_key not in keys:
            new_key = keys[0]
        else:
            cur_idx = keys.index(self._active_key)
            new_idx = max(0, min(len(keys) - 1, cur_idx + direction))
            new_key = keys[new_idx]
        self.set_active(new_key)
        self._on_select(new_key)
        return "break"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_active(self, filter_key: str | None) -> None:
        """Highlight the row whose filter_key matches; pass None to clear."""
        self._active_key = filter_key
        self._apply_active(filter_key)

    def set_items(self, items: list[RailItem]) -> None:
        """Replace the rendered items, preserving active selection if still present."""
        prev_key = self._active_key
        self._item_list = list(items)
        self._build_rows()
        # Re-apply active if the key survived the refresh
        new_keys = {item.filter_key for item in self._item_list}
        if prev_key in new_keys:
            self._active_key = prev_key
            self._apply_active(prev_key)
        else:
            self._active_key = None

    def get_label_widget(self, filter_key: str) -> tk.Label | None:
        """Return the label widget for a row, or None if not found.

        Intended for CommentaryDialog to update per-row font weight when
        commentary text is added or removed.  Do not mutate bg/fg via this
        handle — use set_active / set_items instead.
        """
        return self._row_labels.get(filter_key)

    @property
    def canvas(self) -> tk.Canvas:
        """Expose the inner canvas for focus management by CommentaryDialog."""
        return self._canvas


# ---------------------------------------------------------------------------
# Metric
# ---------------------------------------------------------------------------

_METRIC_TONE_COLOURS: dict[str, str] = {
    "ok": tokens.OK_FG,
    "warn": tokens.WARN_FG,
    "danger": tokens.DANGER_FG,
    "neutral": tokens.FG_1,
}


class Metric(ttk.Frame):
    """Uppercase label + big monospace value. tone: ok/warn/danger/neutral."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str,
        tone: str = "neutral",
        large: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)

        fg = _METRIC_TONE_COLOURS.get(tone, tokens.FG_1)
        font_size = tokens.FS_32 if large else tokens.FS_20

        lbl = tk.Label(
            self,
            text=label.upper(),
            fg=tokens.FG_3,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_12),
            anchor="center",
        )
        lbl.pack(side="top", fill="x")

        val_lbl = tk.Label(
            self,
            text=value,
            fg=fg,
            bg=tokens.BG_MUTED,
            font=_make_font("Cascadia Mono", font_size, "bold"),
            anchor="center",
        )
        val_lbl.pack(side="top", fill="x")


# ------------------------
# ---------------------------------------------------------------------------
# CommentaryDialog
# ---------------------------------------------------------------------------


def CommentaryDialog(  # noqa: N802
    parent: tk.Widget,
    sub_programs: list[str],
    initial: dict[str, str],
) -> dict[str, str] | None:
    """Modal dialog for editing per-sub-program commentary.

    Opens a modal ``tk.Toplevel`` centred on the parent root.

    Parameters
    ----------
    parent:
        Any Tk widget in the target root window.
    sub_programs:
        Ordered list of sub-program IDs to display in the left-hand list.
    initial:
        Mapping of sub-program id -> existing commentary text (may be empty).

    Returns
    -------
    dict[str, str] | None
        The final ``{sub_program_id: commentary_text}`` mapping on Save,
        or ``None`` when the user cancels or closes the window.
    """
    # --- in-memory store (copy so we don't mutate caller's dict) -----------
    comments: dict[str, str] = dict(initial)

    result: dict[str, str] | None = None

    # -----------------------------------------------------------------------
    # Build the Toplevel
    # -----------------------------------------------------------------------
    top = tk.Toplevel(parent)
    top.title("Edit commentary")
    top.minsize(560, 360)

    # Centre on the root window
    root = parent.winfo_toplevel()
    root.update_idletasks()
    rw, rh = root.winfo_width(), root.winfo_height()
    rx, ry = root.winfo_rootx(), root.winfo_rooty()
    w, h = 760, 560
    cx = rx + (rw - w) // 2
    cy = ry + (rh - h) // 2
    top.geometry(f"{w}x{h}+{cx}+{cy}")

    top.grab_set()  # modal

    # -----------------------------------------------------------------------
    # Header strip
    # -----------------------------------------------------------------------
    header = tk.Frame(top, bg=tokens.BRAND_NAVY, height=tokens.SP_12)
    header.pack(side="top", fill="x")
    header.pack_propagate(False)

    header_font = _make_font("Segoe UI", tokens.FS_16, "bold")
    tk.Label(
        header,
        text="Edit commentary",
        bg=tokens.BRAND_NAVY,
        fg=tokens.FG_INVERSE,
        font=header_font,
        anchor="w",
        padx=tokens.SP_4,
    ).pack(side="left", fill="y")

    # -----------------------------------------------------------------------
    # Main body -- left list + right editor
    # -----------------------------------------------------------------------
    body = tk.Frame(top, bg=tokens.BG_PANEL)
    body.pack(side="top", fill="both", expand=True)

    # --- Left pane: SelectableList (210 px wide) ----------------------------
    left_frame = tk.Frame(body, bg=tokens.BG_PANEL, width=210)
    left_frame.pack(side="left", fill="y")
    left_frame.pack_propagate(False)

    # Build initial RailItem list -- value="" because CommentaryDialog does
    # not show a numeric badge; highlight=False because over-budget semantics
    # don't apply in this context.
    def _make_rail_items() -> list[RailItem]:
        return [RailItem(label=sp, value="", filter_key=sp) for sp in sub_programs]

    _sp_list = list(sub_programs)
    _selected: list[str] = []  # mutable single-element container

    # Fonts used for bold-if-has-text feedback on the left list
    normal_font = _make_font("Segoe UI", tokens.FS_13)
    bold_font = _make_font("Segoe UI", tokens.FS_13, "bold")

    def _on_sp_select(sp_id: str) -> None:
        _load_sp(sp_id)

    list_widget = SelectableList(
        left_frame,
        items=_make_rail_items(),
        on_select=_on_sp_select,
        focus_on_mount=True,
        width=210,
    )
    list_widget.pack(
        fill="both",
        expand=True,
        padx=(tokens.SP_3, 0),
        pady=tokens.SP_3,
    )

    # Apply initial bold-font for items that already have commentary
    for sp_id in sub_programs:
        if bool(initial.get(sp_id, "").strip()):
            lbl = list_widget.get_label_widget(sp_id)
            if lbl is not None:
                lbl.configure(font=bold_font)

    # Divider between left and right
    tk.Frame(body, bg=tokens.BORDER_SUBTLE, width=1).pack(side="left", fill="y")

    # --- Right pane ---------------------------------------------------------
    right_frame = tk.Frame(body, bg=tokens.BG_PANEL)
    right_frame.pack(side="left", fill="both", expand=True)

    # Muted label: "Commentary for sub-program: <id>"
    label_font = _make_font("Segoe UI", tokens.FS_13)
    context_var = tk.StringVar(value="Commentary for sub-program: —")
    context_lbl = tk.Label(
        right_frame,
        textvariable=context_var,
        fg=tokens.FG_MUTED,
        bg=tokens.BG_PANEL,
        font=label_font,
        anchor="w",
    )
    context_lbl.pack(side="top", fill="x", padx=tokens.SP_4, pady=(tokens.SP_3, tokens.SP_1))

    # Text editor
    editor_frame = tk.Frame(right_frame, bg=tokens.BG_PANEL)
    editor_frame.pack(side="top", fill="both", expand=True, padx=tokens.SP_4)

    text_font = _make_font("Segoe UI", tokens.FS_13)
    editor = tk.Text(
        editor_frame,
        font=text_font,
        fg=tokens.FG_1,
        bg=tokens.BG_PANEL,
        wrap="word",
        relief="sunken",
        bd=1,
        padx=tokens.SP_2,
        pady=tokens.SP_2,
        undo=True,
    )
    editor_vsb = ttk.Scrollbar(editor_frame, orient="vertical", command=editor.yview)
    editor.configure(yscrollcommand=editor_vsb.set)
    editor_vsb.pack(side="right", fill="y")
    editor.pack(side="left", fill="both", expand=True)

    # Bottom button row
    btn_row = tk.Frame(right_frame, bg=tokens.BG_PANEL)
    btn_row.pack(side="bottom", fill="x", padx=tokens.SP_4, pady=tokens.SP_3)

    # -----------------------------------------------------------------------
    # State helpers
    # -----------------------------------------------------------------------

    def _update_row_font(sp_id: str) -> None:
        lbl_widget = list_widget.get_label_widget(sp_id)
        if lbl_widget is None:
            return
        has_text = bool(comments.get(sp_id, "").strip())
        lbl_widget.configure(font=bold_font if has_text else normal_font)

    def _save_current_text() -> None:
        """Flush the editor content into comments for the currently selected sp."""
        if not _selected:
            return
        text = editor.get("1.0", "end-1c")
        comments[_selected[0]] = text
        _update_row_font(_selected[0])

    def _load_sp(sp_id: str) -> None:
        """Switch the editor to show commentary for sp_id."""
        _save_current_text()
        _selected.clear()
        _selected.append(sp_id)

        # Delegate row highlight to SelectableList
        list_widget.set_active(sp_id)

        context_var.set(f"Commentary for sub-program: {sp_id}")
        editor.delete("1.0", "end")
        editor.insert("1.0", comments.get(sp_id, ""))
        editor.focus_set()

    # -----------------------------------------------------------------------
    # Auto-save on text change
    # -----------------------------------------------------------------------
    def _on_text_modified(event: Any = None) -> None:
        if not _selected:
            return
        # Reset modified flag immediately to allow future events
        editor.edit_modified(False)
        text = editor.get("1.0", "end-1c")
        comments[_selected[0]] = text
        _update_row_font(_selected[0])

    editor.bind("<<Modified>>", _on_text_modified)

    # -----------------------------------------------------------------------
    # Save / Clear all / OK / Cancel actions
    # -----------------------------------------------------------------------

    # Status label — shows "Saved" briefly after the Save button is pressed.
    _save_status_var = tk.StringVar(value="")
    _save_status_lbl = tk.Label(
        btn_row,
        textvariable=_save_status_var,
        fg=tokens.OK_FG,
        bg=tokens.BG_PANEL,
        font=_make_font("Segoe UI", tokens.FS_12),
        anchor="w",
    )
    _save_status_lbl.pack(side="left")

    _save_status_after: list[str | None] = [None]

    def _show_saved_feedback() -> None:
        """Briefly display 'Saved' next to the button row, then clear."""
        _save_status_var.set("Saved")
        if _save_status_after[0] is not None:
            try:
                top.after_cancel(_save_status_after[0])
            except Exception:
                pass
        _save_status_after[0] = top.after(1800, lambda: _save_status_var.set(""))

    def _do_save_inplace(*_: Any) -> None:
        """Flush current edits into the in-memory dict WITHOUT closing the dialog."""
        _save_current_text()
        _show_saved_feedback()

    def _do_clear_all(*_: Any) -> None:
        """Clear ALL commentary across ALL sub-programs after user confirmation."""
        import tkinter.messagebox as _mb

        confirmed = _mb.askyesno(
            "Clear all commentary?",
            "This will remove every saved commentary. Continue?",
            parent=top,
        )
        if not confirmed:
            return
        comments.clear()
        # Refresh the editor if a sub-program is currently selected.
        if _selected:
            editor.delete("1.0", "end")
        # Update bold/normal font for every row in the list.
        for sp_id in sub_programs:
            _update_row_font(sp_id)

    def _do_ok(*_: Any) -> None:
        """Commit all edits and close the dialog (OK)."""
        nonlocal result
        result = dict(comments)
        top.destroy()

    def _do_cancel(*_: Any) -> None:
        nonlocal result
        result = None
        top.destroy()

    # Buttons — right side: OK (primary accent), Cancel; left: Save, Clear all
    btn_font = _make_font("Segoe UI", tokens.FS_13)

    # Save (persist without closing — accent style, primary save action)
    save_btn = ttk.Button(
        btn_row,
        text="Save",
        style="Accent.TButton",
        command=_do_save_inplace,
    )
    save_btn.pack(side="left", padx=(tokens.SP_2, tokens.SP_1))

    # Clear all (less prominent — plain ttk.Button)
    clear_all_btn = ttk.Button(
        btn_row,
        text="Clear all",
        command=_do_clear_all,
    )
    clear_all_btn.pack(side="left", padx=(0, tokens.SP_2))

    # OK / Cancel on the right
    ok_btn = tk.Button(
        btn_row,
        text="OK",
        font=btn_font,
        fg=tokens.FG_INVERSE,
        bg=tokens.BRAND_ACCENT,
        activebackground=tokens.BRAND_NAVY,
        activeforeground=tokens.FG_INVERSE,
        relief="flat",
        padx=tokens.SP_4,
        pady=tokens.SP_2,
        command=_do_ok,
        cursor="hand2",
    )
    ok_btn.pack(side="right", padx=(tokens.SP_2, 0))

    cancel_btn = tk.Button(
        btn_row,
        text="Cancel",
        font=btn_font,
        fg=tokens.FG_1,
        bg=tokens.BG_MUTED,
        activebackground=tokens.BORDER_SUBTLE,
        activeforeground=tokens.FG_1,
        relief="flat",
        padx=tokens.SP_4,
        pady=tokens.SP_2,
        command=_do_cancel,
        cursor="hand2",
    )
    cancel_btn.pack(side="right")

    # Keyboard shortcuts
    top.bind("<Escape>", _do_cancel)
    top.bind("<Control-s>", _do_save_inplace)

    # Tab order: list canvas -> editor -> save -> clear all -> ok -> cancel
    list_widget.canvas.configure(takefocus=True)
    editor.configure(takefocus=True)
    save_btn.configure(takefocus=True)
    clear_all_btn.configure(takefocus=True)
    ok_btn.configure(takefocus=True)
    cancel_btn.configure(takefocus=True)

    # Select first item if available
    if _sp_list:
        _load_sp(_sp_list[0])

    # Window-close protocol -> cancel
    top.protocol("WM_DELETE_WINDOW", _do_cancel)

    # Wait for the dialog to close
    top.wait_window()

    return result
