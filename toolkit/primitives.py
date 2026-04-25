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
from toolkit.base_tool import BannerLevel, LogLine

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
    """190 px label column + read-only entry (mono) + Browse button."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        on_pick: Callable[[Path], None],
        filetypes: list[tuple[str, str]],
        initial_path: Path | None = None,
        optional: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)

        self._on_pick = on_pick
        self._filetypes = filetypes
        self._var = tk.StringVar(value=str(initial_path) if initial_path else "")

        # Label column — fixed 190 px
        label_text = label if not optional else f"{label} (optional)"
        lbl = tk.Label(
            self,
            text=label_text,
            width=26,  # ~190 px at 13 px font
            anchor="w",
            fg=tokens.FG_1,
            bg=tokens.BG_MUTED,
            font=_make_font("Segoe UI", tokens.FS_13),
        )
        lbl.pack(side="left", padx=(0, tokens.SP_3))

        # Read-only entry (Cascadia Mono / Consolas)
        entry_frame = tk.Frame(self, bg=tokens.BG_MUTED)
        entry_frame.pack(side="left", fill="x", expand=True, padx=(0, tokens.SP_3))

        self._entry = tk.Entry(
            entry_frame,
            textvariable=self._var,
            state="readonly",
            readonlybackground=tokens.BG_READONLY,
            fg=tokens.FG_1,
            font=_make_font("Cascadia Mono", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        self._entry.pack(fill="x")

        # Browse button
        self._browse_btn = ttk.Button(self, text="Browse", command=self._browse)
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
    """Labelled text entry with optional placeholder and max_length."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str = "",
        placeholder: str = "",
        max_length: int | None = None,
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
            fg=tokens.FG_1,
            font=_make_font("Segoe UI", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        self._entry.pack(side="top", fill="x")

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
    """Numeric entry with optional min/max validation and decimal places."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str = "",
        min_value: float | None = None,
        max_value: float | None = None,
        decimals: int = 0,
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
            validate="key",
            validatecommand=vcmd,
            fg=tokens.FG_1,
            font=_make_font("Segoe UI", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        self._entry.pack(side="top", fill="x")

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
        **kwargs: Any,
    ) -> None:
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
        row.pack(side="top", fill="x")

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
            validate="key",
            validatecommand=vcmd,
            fg=tokens.FG_1,
            font=_make_font("Segoe UI", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        self._entry.pack(side="left", fill="x", expand=True)

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
        **kwargs: Any,
    ) -> None:
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
            )
            if init_date:
                kw["year"] = init_date.year
                kw["month"] = init_date.month
                kw["day"] = init_date.day
            self._calendar_widget = DateEntry(self, **kw)
            self._calendar_widget.pack(side="top", fill="x")
            self._mode = "calendar"
        except ImportError:
            # Fallback: plain entry with DD/MM/YYYY validation
            init_val = today.strftime("%d/%m/%Y") if init_date else ""
            self._var = tk.StringVar(value=init_val)
            self._entry = tk.Entry(
                self,
                textvariable=self._var,
                fg=tokens.FG_1,
                font=_make_font("Segoe UI", tokens.FS_13),
                relief="sunken",
                bd=1,
            )
            self._entry.pack(side="top", fill="x")
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
        **kwargs: Any,
    ) -> None:
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
        row.pack(side="top", fill="x")

        self._entry = tk.Entry(
            row,
            textvariable=self._var,
            show="●",
            fg=tokens.FG_1,
            font=_make_font("Segoe UI", tokens.FS_13),
            relief="sunken",
            bd=1,
        )
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, tokens.SP_2))
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
    """

    def __init__(
        self,
        parent: tk.Widget,
        columns: list[dict[str, Any]],
        min_height: int = 200,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)

        col_ids = [str(c["key"]) for c in columns]
        self._columns = columns

        self._tree = ttk.Treeview(
            self,
            columns=col_ids,
            show="headings",
            height=max(5, min_height // 22),
        )

        # Configure columns and headings
        mono_font = _make_font("Cascadia Mono", tokens.FS_12)
        for col in columns:
            cid = str(col["key"])
            width = int(col.get("width", 120))
            is_right = col.get("align") == "right" or col.get("mono")
            col_anchor: Literal["e", "w"] = "e" if is_right else "w"
            self._tree.heading(cid, text=str(col["label"]))
            self._tree.column(cid, width=width, anchor=col_anchor, stretch=True)

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

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        # Clear existing
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        for i, row in enumerate(rows):
            values = [str(row.get(str(c["key"]), "")) for c in self._columns]
            tags: list[str] = []

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

            self._tree.insert("", "end", values=values, tags=tags)


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
        Mapping of sub-program id → existing commentary text (may be empty).

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
    # Main body — left list + right editor
    # -----------------------------------------------------------------------
    body = tk.Frame(top, bg=tokens.BG_PANEL)
    body.pack(side="top", fill="both", expand=True)

    # --- Left pane: scrollable list (210 px wide) ---------------------------
    left_frame = tk.Frame(body, bg=tokens.BG_PANEL, width=210)
    left_frame.pack(side="left", fill="y")
    left_frame.pack_propagate(False)

    list_border = tk.Frame(left_frame, bg=tokens.BORDER_SUBTLE, bd=0)
    list_border.pack(fill="both", expand=True, padx=(tokens.SP_3, 0), pady=tokens.SP_3)

    list_canvas = tk.Canvas(
        list_border,
        bg=tokens.BG_PANEL,
        highlightthickness=0,
        bd=0,
    )
    list_scrollbar = ttk.Scrollbar(list_border, orient="vertical", command=list_canvas.yview)
    list_canvas.configure(yscrollcommand=list_scrollbar.set)

    list_scrollbar.pack(side="right", fill="y")
    list_canvas.pack(side="left", fill="both", expand=True)

    list_inner = tk.Frame(list_canvas, bg=tokens.BG_PANEL)
    list_window = list_canvas.create_window((0, 0), window=list_inner, anchor="nw")

    def _on_list_inner_configure(event: Any) -> None:
        list_canvas.configure(scrollregion=list_canvas.bbox("all"))

    def _on_list_canvas_configure(event: Any) -> None:
        list_canvas.itemconfig(list_window, width=event.width)

    list_inner.bind("<Configure>", _on_list_inner_configure)
    list_canvas.bind("<Configure>", _on_list_canvas_configure)

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
    # State: currently selected sub-program id
    # -----------------------------------------------------------------------
    _selected: list[str] = []  # mutable single-element container
    _row_labels: dict[str, tk.Label] = {}

    normal_font = _make_font("Segoe UI", tokens.FS_13)
    bold_font = _make_font("Segoe UI", tokens.FS_13, "bold")

    def _update_row_font(sp_id: str) -> None:
        lbl = _row_labels.get(sp_id)
        if lbl is None:
            return
        has_text = bool(comments.get(sp_id, "").strip())
        lbl.configure(font=bold_font if has_text else normal_font)

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

        # Highlight selected row; clear others
        for sid, lbl in _row_labels.items():
            lbl.configure(
                bg=tokens.RAIL_SELECTED if sid == sp_id else tokens.BG_PANEL,
                fg=tokens.FG_INVERSE if sid == sp_id else tokens.FG_1,
            )

        context_var.set(f"Commentary for sub-program: {sp_id}")
        editor.delete("1.0", "end")
        editor.insert("1.0", comments.get(sp_id, ""))
        editor.focus_set()

    # Build list rows
    for sp_id in sub_programs:
        has_text = bool(initial.get(sp_id, "").strip())
        row_lbl = tk.Label(
            list_inner,
            text=sp_id,
            font=bold_font if has_text else normal_font,
            fg=tokens.FG_1,
            bg=tokens.BG_PANEL,
            anchor="w",
            padx=tokens.SP_3,
            pady=tokens.SP_2,
            cursor="hand2",
        )
        row_lbl.pack(fill="x")
        _row_labels[sp_id] = row_lbl

        # Bind click
        def _make_click(sid: str) -> Callable[..., None]:
            def _click(*_: Any) -> None:
                _load_sp(sid)

            return _click

        row_lbl.bind("<Button-1>", _make_click(sp_id))

    # Keyboard navigation — Up/Down on list canvas
    _sp_list = list(sub_programs)

    def _nav_list(direction: int, event: Any = None) -> str:
        if not _selected or not _sp_list:
            if _sp_list:
                _load_sp(_sp_list[0])
            return "break"
        cur_idx = _sp_list.index(_selected[0])
        new_idx = max(0, min(len(_sp_list) - 1, cur_idx + direction))
        _load_sp(_sp_list[new_idx])
        return "break"

    list_canvas.bind("<Up>", lambda e: _nav_list(-1, e))
    list_canvas.bind("<Down>", lambda e: _nav_list(1, e))
    list_canvas.bind("<Button-1>", lambda e: list_canvas.focus_set())
    list_inner.bind("<Up>", lambda e: _nav_list(-1, e))
    list_inner.bind("<Down>", lambda e: _nav_list(1, e))

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
    # Save / Cancel actions
    # -----------------------------------------------------------------------
    def _do_save(*_: Any) -> None:
        nonlocal result
        _save_current_text()
        result = dict(comments)
        top.destroy()

    def _do_cancel(*_: Any) -> None:
        nonlocal result
        result = None
        top.destroy()

    # Buttons
    btn_font = _make_font("Segoe UI", tokens.FS_13)
    save_btn = tk.Button(
        btn_row,
        text="Save",
        font=btn_font,
        fg=tokens.FG_INVERSE,
        bg=tokens.BRAND_ACCENT,
        activebackground=tokens.BRAND_NAVY,
        activeforeground=tokens.FG_INVERSE,
        relief="flat",
        padx=tokens.SP_4,
        pady=tokens.SP_2,
        command=_do_save,
        cursor="hand2",
    )
    save_btn.pack(side="right", padx=(tokens.SP_2, 0))

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

    # -----------------------------------------------------------------------
    # Keyboard shortcuts
    # -----------------------------------------------------------------------
    top.bind("<Escape>", _do_cancel)
    top.bind("<Control-s>", _do_save)

    # Tab order: list canvas → editor → save → cancel
    list_canvas.configure(takefocus=True)
    editor.configure(takefocus=True)
    save_btn.configure(takefocus=True)
    cancel_btn.configure(takefocus=True)

    # Select first item if available
    if _sp_list:
        _load_sp(_sp_list[0])

    # Window-close protocol → cancel
    top.protocol("WM_DELETE_WINDOW", _do_cancel)

    # Wait for the dialog to close
    top.wait_window()

    return result
