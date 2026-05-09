from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date  # noqa: F401 -- re-exported for tool implementors
from pathlib import Path
from typing import Any, Literal, Protocol

Status = Literal["idle", "running", "success", "warning", "error"]
LogTag = Literal["heading", "ok", "warning", "danger", "extra", "muted"]
BannerLevel = Literal["neutral", "ok", "warning", "danger", "info"]

# ---------------------------------------------------------------------------
# Input kinds (discriminated union)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileInput:
    kind: Literal["file"] = "file"
    key: str = ""
    label: str = ""
    filetypes: list[tuple[str, str]] = field(default_factory=list)  # -> filedialog
    # Round 40b — entry width in characters.  Default 60 fits typical
    # Windows paths.  Tools that always pick from a fixed-format
    # source (e.g. the same school's CASES21 export) can shrink this.
    width: int = 60


@dataclass(frozen=True)
class TextInput:
    kind: Literal["text"] = "text"
    key: str = ""
    label: str = ""
    placeholder: str = ""
    max_length: int | None = None
    # Round 40 — entry width in characters.  Default 32 fits most labels;
    # tools with shorter content (e.g. school code) can override.
    width: int = 32


@dataclass(frozen=True)
class NumberInput:
    kind: Literal["number"] = "number"
    key: str = ""
    label: str = ""
    min_value: float | None = None
    max_value: float | None = None
    decimals: int = 0
    # Round 40 — entry width.  Default 12 fits "999,999.99".
    width: int = 12
    # Round 45 Phase A — pre-fill value when the input cache is empty
    # (i.e. first render).  Mirrors RangeInput.default so tools can
    # ship a sensible starting value without relying on the user typing
    # one.  None = no pre-fill.
    default: float | None = None


@dataclass(frozen=True)
class CurrencyInput:  # AUD; renders with $ prefix, 2-decimal
    kind: Literal["currency"] = "currency"
    key: str = ""
    label: str = ""
    # Round 40 — entry width.  Default 14 fits "9,999,999.99".
    width: int = 14


@dataclass(frozen=True)
class DateInput:
    kind: Literal["date"] = "date"
    key: str = ""
    label: str = ""
    default: Literal["today", "empty"] = "today"
    # Round 40 — entry width.  Default 12 fits DD/MM/YYYY plus chevron.
    width: int = 12


@dataclass(frozen=True)
class SecretInput:  # masked; optional DPAPI-encrypted local remember
    kind: Literal["secret"] = "secret"
    key: str = ""
    label: str = ""
    pattern: str = r".+"  # e.g. r"\d{4,6}" for HYIA SIN
    remember_key: str | None = None  # when set, enables 'Remember on this device'
    # (DPAPI-encrypted at %LOCALAPPDATA%/<MSIX>/LocalCache/{remember_key}.dat)
    # Round 40 — entry width.  Default 20 covers common secret lengths;
    # narrow inputs like a 4-6 digit SIN can override to 8 or so.
    width: int = 20


@dataclass(frozen=True)
class RangeInput:
    """A draggable slider input. Rendered as ttk.Scale with a numeric value label.

    The shell calls ``tool.preview_update(key, value)`` (debounced ~100 ms) every
    time the user drags the slider. Tools that don't override preview_update get
    no live preview; the slider's value is still passed to ``run()`` via paths.

    When ``numeric_box`` is True the shell renders:
    * Range labels (``min_value%`` / ``max_value%``) flanking the slider.
    * A paired ``ttk.Entry`` (width ~6 chars) followed by a ``%`` suffix label.
    * A muted italic hint "Type any value > 0 — drag limited to min–max%".

    Two separate ``tk.DoubleVar`` instances are used:
    * ``actual_var`` — the user-facing value; accepts **any value > 0** (no upper
      cap).  This is what ``_input_cache`` stores and ``run()`` receives.
    * ``slider_var`` (internal) — drives the Scale knob, always clamped to
      ``[min_value, max_value]``.  Typing a value outside the slider range moves
      the knob to the nearest endpoint without capping the typed value.

    Entry validation on focus-out / Return:
    * Non-numeric → reverts to the last committed actual value.
    * Value ≤ 0 → reverts to the last committed actual value.
    * Value > 0 → accepted; ``actual_var`` updated; slider knob clamped.

    ``preview_update(key, value)`` is called with the **actual** (unclamped) value.

    Default ``numeric_box=False`` so existing call sites are unaffected.
    """

    kind: Literal["range"] = "range"
    key: str = ""
    label: str = ""
    min_value: float = 0.0
    max_value: float = 100.0
    default: float = 50.0
    step: float = 1.0
    live: bool = True  # if False, slider value only read by run(), no preview_update
    numeric_box: bool = False  # if True, render a paired number entry next to the slider
    # Round 22e — when True, this RangeInput packs into the same row as the
    # previous input, side-by-side, instead of breaking onto its own row.
    # Used for the Sub-Program Revenue / Expense threshold pair so they
    # share a horizontal band.  Default False preserves the existing
    # "one input per row" layout for every other tool.
    inline_with_previous: bool = False


InputSpec = (
    FileInput | TextInput | NumberInput | CurrencyInput | DateInput | SecretInput | RangeInput
)


# ---------------------------------------------------------------------------
# Output spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutputSpec:
    key: str
    label: str
    suffix: str  # ".xlsx", ".xlsm", ".pdf" -- or "" for form-only tools


# ---------------------------------------------------------------------------
# Log line
# ---------------------------------------------------------------------------


@dataclass
class LogLine:
    text: str
    tag: LogTag | None = None


# ---------------------------------------------------------------------------
# Tool result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RailItem:
    """A single row in the in-tool side rail (e.g. a faculty / sub-program entry).

    label      -- display name shown on the left of the row.
    value      -- pre-formatted summary badge shown on the right (e.g. "72 %").
    filter_key -- opaque token the tool frame uses to filter table rows.
    highlight  -- True renders a pink/over-budget tint on the rail row.
    value_pct  -- Round 22d — optional 0-100+ percentage that drives a thin
                  data-bar at the bottom of the row.  Bar colour:
                  green ≤100%, amber 100-110%, red >110%.  None = no bar
                  (preserves the existing rail look for tools that don't
                  use this field).
    """

    label: str
    value: str
    filter_key: str
    highlight: bool = False
    value_pct: float | None = None


@dataclass(frozen=True)
class TableSpec:
    """A self-contained table descriptor for use in ToolResult.table.

    Replaces the legacy table_columns / table_rows pair and adds optional
    per-row styling and row-click callbacks.

    columns      -- same shape as today's table_columns.
    rows         -- same shape as today's table_rows.
    row_style    -- called per row; returns a Tkinter option dict
                    (e.g. {"background": "#F4CCCC"}). Empty dict = no override.
    on_row_click -- called with the full row dict when the user clicks a row.
    """

    columns: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    # Round 22a — value type widened to Any so callers can supply ``font``
    # as a Tk font-spec tuple (family, size, "italic") in addition to the
    # original background/foreground hex strings.
    row_style: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    on_row_click: Callable[[dict[str, Any]], None] | None = None


@dataclass
class ToolResult:
    status: Status
    banner_level: BannerLevel
    banner_text: str
    log_lines: list[LogLine] = field(default_factory=list)
    metrics: list[tuple[str, str, str | None]] = field(default_factory=list)  # (label, value, tone)
    table_columns: list[dict[str, Any]] | None = None
    table_rows: list[dict[str, Any]] | None = None
    output_path: Path | None = None
    # --- new fields (v2.0 phase 3 additions) ---
    side_rail: list[RailItem] | None = None
    table: TableSpec | None = None
    # --- Round 22b — multi-tab data view -----------------------------------
    # When set, the shell renders a ``ttk.Notebook`` with one tab per entry
    # rather than the single ``table`` above.  Each entry is
    # ``(tab_label, TableSpec)``.  The first tab is the default selection.
    # ``table`` is left non-None as a fallback for any code path that hasn't
    # learned about tabs yet (e.g. legacy ``preview_update`` returns).
    table_tabs: list[tuple[str, TableSpec]] | None = None


# ---------------------------------------------------------------------------
# Progress callback type
# ---------------------------------------------------------------------------

ProgressFn = Callable[[int, str], None]  # (percent 0-100, message)


# ---------------------------------------------------------------------------
# BaseTool protocol
# ---------------------------------------------------------------------------


class BaseTool(Protocol):
    id: str
    group: str
    label: str
    short: str
    order: int
    inputs: list[InputSpec]
    output: OutputSpec | None
    primary_button: str
    pdf_template: str | None
    pdf_body: str | None  # feature id from the licence; None = free tool

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult: ...

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]: ...

    def clear(self) -> None:
        """Reset any tool-specific in-memory state.

        Called by the shell when the user clicks the Clear button. The shell
        handles UI-level resets (file picker fields, banner, log, table,
        side rail). Override this method if your tool has additional per-tool
        state to clear (e.g. cached commentary, last output path).
        """
        return None

    def preview_update(self, key: str, value: float | str) -> ToolResult | None:
        """Re-emit the result panel without re-running parse/compute.

        Called by the shell when a ``live=True`` RangeInput changes (debounced
        ~100 ms). Default returns None (no live preview). Tools that cache
        state in ``run()`` can override this to return a fresh ToolResult
        reflecting the new input value without repeating expensive I/O.

        Parameters
        ----------
        key:
            The ``RangeInput.key`` that changed.
        value:
            Current slider value as a float (or string if the shell's cache
            was set from a text source).

        Returns
        -------
        ToolResult | None
            A fresh result to replace the current panel, or None to leave
            the panel unchanged.
        """
        return None
