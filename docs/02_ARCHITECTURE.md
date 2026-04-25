# Vic School Tool v2 — Architecture Decision Record

> Context: v2 grows the existing `Master Budget Automation Tool v1.0.2` (Tkinter + openpyxl + pywin32, shipped as MSIX) into a five-tool shell. Decisions below lock the non-negotiable contracts so that adding tools 6–N remains a 10-minute exercise.

## ADR-0001 — GUI toolkit: **Tkinter / ttk (vista theme)**

**Decision**: Keep Tkinter. No port to PySide6 / WinUI 3.

**Why**:
- Design handoff was drawn 1:1 for ttk; reusing PySide6 would force a visual redesign.
- Tkinter is stdlib — zero new PyInstaller hidden-imports, smaller MSIX, simpler build chain.
- v1 already ships on Tkinter; the refactor is structural, not a rewrite.

**Cost accepted**: No native HiDPI beyond Tk 8.6's DPI awareness, no native dark mode. Both explicitly out of scope for v2.

---

## ADR-0002 — Language & runtime: **Python 3.12**, Windows x64 only

**Decision**: Target CPython 3.12.x, x64. Frozen with PyInstaller, wrapped in MSIX. Source deliberately type-annotated and `from __future__ import annotations` in every module.

**Why**:
- v1 ships Python 3.11 via PyInstaller; 3.12 is the current Microsoft Store baseline, has first-class typing, and matches DoE SOE compatibility matrix.
- x64 only matches the DoE laptop fleet; ARM64 would double the MSIX pipeline without a user.

---

## ADR-0003 — Project layout (canonical)

```
Vic_School_Finance_Tools/
├── README.md
├── pyproject.toml                 ← PEP 621; ruff + mypy + pytest config
├── requirements.txt               ← runtime pins (openpyxl, pywin32, pdfminer.six, weasyprint, …)
├── requirements-dev.txt           ← ruff, mypy, pytest, pytest-cov, pyinstaller
├── app.py                         ← thin entrypoint: boot shell, register tools, mainloop
├── app_metadata.py                ← APP_NAME, APP_VERSION ("2.0.0"), SUPPORT_EMAIL, APP_INSTALLER_ID
├── toolkit/
│   ├── __init__.py
│   ├── base_tool.py               ← BaseTool ABC, InputSpec, OutputSpec, ToolResult dataclasses
│   ├── registry.py                ← TOOLS = [...] — single edit per new tool
│   ├── shell.py                   ← TkShell: window chrome, rail, tool swap, status bar
│   ├── primitives.py              ← FileRow, Banner, ProgressBar, LogView, Table, Metric, SectionHeader
│   ├── tokens.py                  ← colors + fonts + spacing ported from colors_and_type.css
│   ├── highlights.py              ← openpyxl fill constants (mismatch/source-only/edited)
│   ├── fonts.py                   ← startup font probe + fallback chain
│   ├── logging_setup.py           ← rotating-file handler + %LOCALAPPDATA% path resolution
│   └── reports.py                 ← render_pdf() WeasyPrint wrapper
├── tools/
│   ├── master_budget/
│   │   ├── frame.py               ← MasterBudgetTool(BaseTool) — UI-free; inputs/output/run()
│   │   ├── logic.py               ← ported from v1 budget_automation.py (pure functions)
│   │   └── tests/
│   ├── srp/{frame.py, logic.py, tests/}
│   ├── sub_program/{frame.py, logic.py, tests/}
│   ├── camps/{frame.py, logic.py, tests/}
│   └── operating/{frame.py, logic.py, tests/}
├── reports/                       ← WeasyPrint templates (v2.1 onward except Sub-Program)
│   ├── sub_program_cover.html
│   ├── sub_program_body.html
│   ├── report.css                 ← @imports ../toolkit/tokens.css style block
│   └── assets/
│       ├── fonts/source-serif-4/  ← OFL, embedded in MSIX
│       ├── fonts/cascadia-mono/   ← OFL
│       └── logo.svg
├── assets/                        ← MSIX logos (inherited from v1, re-use as-is)
│   ├── Square44x44Logo.png
│   ├── Square71x71Logo.png
│   ├── Square150x150Logo.png
│   ├── Wide310x150Logo.png
│   ├── StoreLogo.png
│   └── SplashScreen.png
├── msix/
│   ├── AppxManifest.template.xml  ← inherited from v1, updated Identity Name & capabilities if needed
│   ├── generate_msix_assets.ps1   ← inherited
│   └── build_msix_package.ps1     ← refactored from v1 build_msix_package.ps1
├── packaging/
│   └── SchoolTool.spec  ← PyInstaller onedir spec (replaces v1 .spec)
├── docs/                          ← this folder; requirements, ADR, roadmap
├── store/                         ← Partner Center submission assets (listing copy, screenshots)
├── tests/                         ← shell-level tests + e2e smoke
│   ├── test_shell_smoke.py
│   ├── test_registry.py
│   └── fixtures/                  ← sample input files (redacted)
└── .github/workflows/
    └── build.yml                  ← lint + type + test + PyInstaller build (windows-latest)
```

**Rule**: a tool module may import from `toolkit.*`; `toolkit` must never import from `tools.*`. The registry is the one-way gate.

---

## ADR-0004 — Framework contract (`BaseTool`) — **frozen surface**

Revised to support form-field inputs (needed by HYIA Transfer Code Generator — no file I/O, just form fields). `InputSpec` is now a discriminated union.

```python
# toolkit/base_tool.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Literal, Protocol, Union

Status = Literal["idle", "running", "success", "warning", "error"]
LogTag = Literal["heading", "ok", "warning", "danger", "extra", "muted"]

# --- Input kinds (discriminated union) -----------------------------------

@dataclass(frozen=True)
class FileInput:
    kind:      Literal["file"] = "file"
    key:       str = ""
    label:     str = ""
    filetypes: list[tuple[str, str]] = field(default_factory=list)   # → filedialog

@dataclass(frozen=True)
class TextInput:
    kind:        Literal["text"] = "text"
    key:         str = ""
    label:       str = ""
    placeholder: str = ""
    max_length:  int | None = None

@dataclass(frozen=True)
class NumberInput:
    kind:      Literal["number"] = "number"
    key:       str = ""
    label:     str = ""
    min_value: float | None = None
    max_value: float | None = None
    decimals:  int = 0

@dataclass(frozen=True)
class CurrencyInput:     # AUD; renders with $ prefix, 2-decimal
    kind:  Literal["currency"] = "currency"
    key:   str = ""
    label: str = ""

@dataclass(frozen=True)
class DateInput:
    kind:    Literal["date"] = "date"
    key:     str = ""
    label:   str = ""
    default: Literal["today", "empty"] = "today"

@dataclass(frozen=True)
class SecretInput:       # masked; optional DPAPI-encrypted local remember
    kind:         Literal["secret"] = "secret"
    key:          str = ""
    label:        str = ""
    pattern:      str = r".+"               # e.g. r"\d{4,6}" for HYIA SIN
    remember_key: str | None = None         # when set, enables 'Remember on this device'
                                            # (DPAPI-encrypted at %LOCALAPPDATA%/<MSIX>/LocalCache/{remember_key}.dat)

InputSpec = Union[FileInput, TextInput, NumberInput, CurrencyInput, DateInput, SecretInput]

@dataclass(frozen=True)
class OutputSpec:
    key:   str
    label: str
    suffix: str                        # ".xlsx", ".xlsm", ".pdf" — or None for form-only tools

@dataclass
class LogLine:
    text: str
    tag: LogTag | None = None

@dataclass
class ToolResult:
    status: Status
    banner_level: Literal["neutral", "ok", "warning", "danger", "info"]
    banner_text: str
    log_lines: list[LogLine] = field(default_factory=list)
    metrics: list[tuple[str, str, str | None]] = field(default_factory=list)  # (label, value, tone)
    table_columns: list[dict] | None = None
    table_rows: list[dict] | None = None
    output_path: Path | None = None

ProgressFn = Callable[[int, str], None]     # (percent 0–100, message)

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

    def run(self, paths: dict[str, Path], progress: ProgressFn) -> ToolResult: ...
    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]: ...
```

**Non-negotiable**: `run()` is pure (takes a `dict[str, Any]` of resolved input values, returns a `ToolResult`). It **must not** touch Tk, the shell, or the registry. The shell is the only thing that renders `ToolResult`. Violation = PR blocker.

The shell resolves each `InputSpec` to a concrete value before calling `run()`:
- `FileInput` → `Path` (from the picker)
- `TextInput` / `SecretInput` → `str`
- `NumberInput` / `CurrencyInput` → `Decimal` (never float for currency)
- `DateInput` → `datetime.date`

Tools with no file outputs (HYIA) leave `output = None` and rely on `ToolResult.banner_text` + metrics to render their answer.

---

## ADR-0005 — Threading model

- UI thread owns the Tk main loop. All widget mutations on the UI thread.
- Clicking the primary button:
  1. Disables inputs, switches status to `running`, shows the progress bar at 0 %.
  2. Spawns one `concurrent.futures.ThreadPoolExecutor(max_workers=1)` task per tool instance.
  3. Worker calls `tool.run(paths, progress)`; `progress(pct, msg)` is wrapped to marshal into the UI thread via `root.after(0, …)`.
  4. On completion or exception the wrapped future posts a single `on_complete(ToolResult | Exception)` back to the UI thread.
- Exceptions inside `run()` are caught at the boundary → rendered as a `ToolResult(status="error", banner_level="danger", ...)`. They do not propagate to Tk.

Cancellation: **not supported in v2.0.0**. The worker is allowed to run to completion. Secondary action *Clear* is disabled while running.

---

## ADR-0006 — PDF pipeline: **WeasyPrint**

**Decision**: Ship WeasyPrint inside the MSIX. GTK runtime (Pango/Cairo/Fontconfig) bundled by PyInstaller hooks.

**Why over ReportLab**: the same CSS tokens already drive the product; re-use is worth the +~35 MB install cost. Template changes propagate to product and PDF together.

**Cost accepted**: MSIX grows to ~85 MB. PyInstaller needs `--collect-submodules weasyprint --collect-data weasyprint --collect-binaries weasyprint` and the MSIX staging step has to copy the GTK DLLs next to the frozen exe.

**Fallback plan**: if GTK bundling turns into a fight we cannot win before M5, the Sub-Program PDF falls back to `xhtml2pdf` for v2.0.0 and WeasyPrint lands in v2.1. This is a documented fallback, not a default.

---

## ADR-0007 — Input parsers

Per tool, all parsing is isolated in `tools/<tool>/logic.py` so it can be unit-tested without Tk.

| Tool | Input format | Library |
|---|---|---|
| HYIA Transfer Code | form fields only (no file I/O) | stdlib — pure arithmetic + `win32crypt` for optional SIN storage |
| Master Budget | `.xlsx` / `.xlsm` | `openpyxl` (existing v1) + `pywin32` only for macro-preserving write |
| SRP Comparison | `.pdf` | `pdfplumber` (tables) + `pdfminer.six` (text); custom line-schema detector per SRP template |
| Sub-Program Report | `.pdf` (CASES21 GL21157) — *XLSX also accepted if CASES21 lets user export that way* | `pdfplumber` primary; `openpyxl` fallback when XLSX supplied |
| Camps Reconciliation | `.xlsx` | `openpyxl` |
| Operating Statement | `.pdf` (CASES21 GL21150) — *sample is PDF; earlier assumption was `.xls`, corrected* | `pdfplumber` |

**Correction note** — samples confirmed 2026-04-23: CASES21 exports GL21157 (Annual Sub-Program Budget Report) and GL21150 (Operating Statement Detailed) as **PDFs**, not XLSX/XLS as the design handoff implied. Parser stack updated. Still resilient: if a user supplies XLSX, we fall through to `openpyxl`; if XLS, to `xlrd==1.2.0`. File-type dispatched on extension + magic-bytes sniff.

**Risk — Camps sample files not yet provided.** `tools/camps/logic.py` is scaffolded against a provisional schema (see §3.4 of requirements) and shipped as *experimental* until real exports land. Wiring the rail + UI does not block on this; only the parser does.

---

## ADR-0008 — State management

**Per tool instance (lives on the `BaseTool` subclass)**:
```python
inputs:       dict[str, Path]      # current file-picker values
output:       Path | None
status:       Status
progress:     int                  # 0..100
progress_msg: str
result:       ToolResult | None
```

**Shell-level**:
```python
active_tool_id: str
tools:          dict[str, BaseTool]     # id → instance, built once at startup
```

No disk persistence in v2.0.0. When/if session.json arrives in v2.1, it stores `last_active_tool_id` and each tool's `last_inputs` (paths only — never file contents).

---

## ADR-0009 — Design tokens port

`colors_and_type.css` is the canonical source. Port lives in `toolkit/tokens.py`:

```python
# auto-generated by scripts/port_tokens.py — do not edit by hand
BRAND_NAVY        = "#185787"
BRAND_NAVY_700    = "#124466"
BRAND_NAVY_TINT   = "#E6EEF5"
# …
OK_FG, OK_BG             = "#0B6E0B", "#E8F5E9"
WARN_FG, WARN_BG         = "#9A6700", "#FFF7E6"
DANGER_FG, DANGER_BG     = "#B00020", "#FDECEA"
INFO_FG, INFO_BG         = "#124466", "#E6EEF5"
HL_MISMATCH              = "F4CCCC"   # openpyxl fill (no leading #)
HL_SOURCE_ONLY           = "E2F0D9"
HL_EDITED                = "FFF2CC"
SP_1 = 4;  SP_2 = 8;  SP_3 = 12;  SP_4 = 16;  SP_5 = 20;  SP_6 = 24
SP_8 = 32; SP_10 = 40; SP_12 = 48; SP_16 = 64
FONT_SANS_PRIMARY   = "Aptos";   FONT_SANS_FALLBACK   = "Segoe UI"
FONT_MONO_PRIMARY   = "Cascadia Mono";  FONT_MONO_FALLBACK  = "Consolas"
FONT_SERIF_PRIMARY  = "Source Serif 4"
```

A script (`scripts/port_tokens.py`) regenerates this from the CSS at build time, so a token change is a one-line diff that propagates to both surfaces. CI fails if `tokens.py` drifts from the CSS.

---

## ADR-0010 — MSIX packaging & signing

- Build chain (inherited, extended): `PyInstaller onedir → copy → msix/build_msix_package.ps1 → signtool`.
- `AppxManifest.template.xml` receives new `Identity Name` (`AustralianDepartmentOfEducation.SchoolTool` or DoE's actual Partner Center identity), `Version 2.0.0.0`, `PublisherDisplayName`, updated `DisplayName` and `Description`. Capabilities stay `runFullTrust`.
- Signing: DoE-owned Microsoft Partner Center publisher identity. First store-ready MSIX at the end of M1 (feature-complete identity, even if empty app), so that submission + cert pipeline is validated early.
- Vendored SDK: re-use `.tools/msixsdk/` from v1 (makeappx, makepri, signtool).
- Install size budget: 90 MB.

---

## ADR-0011 — Logging & crash reporting

- Rotating-file logger → `%LOCALAPPDATA%\Packages\<MSIX-family-name>\LocalCache\logs\sftk.log`.
- Max 5 files × 1 MB.
- Default level `INFO`; `DEBUG` when `SFTK_DEBUG=1` env var set.
- `sys.excepthook` and `Tk.report_callback_exception` both route to a dedicated `toolkit.errors.handle_unhandled(exc)` that logs the traceback and shows a top-level danger banner with the message + "See log at: <path>" copy. App keeps running.
- **No network-based crash reporting.** DoE privacy bar.

---

## ADR-0012 — Testing strategy

Three tiers:

1. **Unit tests** — per `tools/*/logic.py`. Pure functions over fixture inputs; `pytest`; coverage ≥ 80 % on logic modules. Zero Tk imports.
2. **Shell tests** — `toolkit/shell.py`, registry wiring, primitives. Render headless with `pyvirtualdisplay` on CI; assert widget tree, token application, tool-switching. Smoke-level only.
3. **End-to-end smoke** — launch the packaged MSIX on a Windows runner, click through each tool with a recorded fixture set, assert output file exists and non-empty. Runs nightly.

CI (`.github/workflows/build.yml`): `ruff` → `mypy --strict` → `pytest` → PyInstaller onedir build → MSIX packaging step (PR builds don't sign; only tags build a signed artifact).

Independent verification: after each milestone, a Sonnet *code-review* agent and a *test* agent run in parallel with **no shared context** to catch confirmation bias.

---

## ADR-0013 — Versioning & release

- SemVer: `MAJOR.MINOR.PATCH`. v2.0.0 = the five-tool shell. v2.1.0 = PDFs for remaining tools. v2.0.x = bugfixes.
- `app_metadata.APP_VERSION` is the single source; `AppxManifest.xml` version derived from it at build.
- Git tags: `v2.0.0` etc. Partner Center submission per tag.

---

## ADR-0014 — What stays locked by design

Touching these requires a deliberate design-review cycle, not a per-tool tweak:

- Window chrome, status-bar layout, rail width (220 px), rail styling, selection colour (`#3399FF`), focus ring (`rgba(43,124,184,.35)`).
- 4 px spacing grid, 8-token type scale, colour tokens in `colors_and_type.css`.
- Australian English copy rules, sentence-case buttons, `−` for negatives, no emoji.
- The `BaseTool` contract (ADR-0004).

---

## Open risks & mitigations

| Risk | Mitigation |
|---|---|
| Camps sample data missing | Build UI + framework; parser lands when exports arrive. Don't block M1–M3. |
| WeasyPrint GTK bundling in MSIX | Fall back to `xhtml2pdf` for v2.0.0 if blocked; WeasyPrint in v2.1. |
| Partner Center identity string | Confirmed: DoE account available; Ivan owns the identity + cert. |
| `.xls` legacy format in OpStat | `xlrd==1.2.0` pinned; tested against a real sample on M4. |
| Fonts (Aptos) absent on older DoE images | Runtime probe + fall back to Segoe UI; visual change is tolerable. |
| MSIX install size > 90 MB | PyInstaller `--exclude-module` audit in M5; drop unused scipy/numpy subpackages that weasyprint pulls. |
