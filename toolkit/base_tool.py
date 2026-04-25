from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date  # noqa: F401 — re-exported for tool implementors
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
    filetypes: list[tuple[str, str]] = field(default_factory=list)  # → filedialog


@dataclass(frozen=True)
class TextInput:
    kind: Literal["text"] = "text"
    key: str = ""
    label: str = ""
    placeholder: str = ""
    max_length: int | None = None


@dataclass(frozen=True)
class NumberInput:
    kind: Literal["number"] = "number"
    key: str = ""
    label: str = ""
    min_value: float | None = None
    max_value: float | None = None
    decimals: int = 0


@dataclass(frozen=True)
class CurrencyInput:  # AUD; renders with $ prefix, 2-decimal
    kind: Literal["currency"] = "currency"
    key: str = ""
    label: str = ""


@dataclass(frozen=True)
class DateInput:
    kind: Literal["date"] = "date"
    key: str = ""
    label: str = ""
    default: Literal["today", "empty"] = "today"


@dataclass(frozen=True)
class SecretInput:  # masked; optional DPAPI-encrypted local remember
    kind: Literal["secret"] = "secret"
    key: str = ""
    label: str = ""
    pattern: str = r".+"  # e.g. r"\d{4,6}" for HYIA SIN
    remember_key: str | None = None  # when set, enables 'Remember on this device'
    # (DPAPI-encrypted at %LOCALAPPDATA%/<MSIX>/LocalCache/{remember_key}.dat)


InputSpec = FileInput | TextInput | NumberInput | CurrencyInput | DateInput | SecretInput


# ---------------------------------------------------------------------------
# Output spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutputSpec:
    key: str
    label: str
    suffix: str  # ".xlsx", ".xlsm", ".pdf" — or "" for form-only tools


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


# ---------------------------------------------------------------------------
# Progress callback type
# ---------------------------------------------------------------------------

ProgressFn = Callable[[int, str], None]  # (percent 0–100, message)


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
    pdf_body: str | None
    requires_feature: str | None  # feature id from the licence; None = free tool

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult: ...

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]: ...
