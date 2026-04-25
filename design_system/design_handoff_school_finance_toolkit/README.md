# Handoff: School Finance Toolkit

## Overview

The School Finance Toolkit is a multi-tool Windows desktop application for Victorian Government school business managers. It automates the manual Excel/CSV workflows they perform every fortnight to keep a school's finances reconciled: importing Compass exports into the Master Budget workbook, comparing Indicative vs Confirmed SRP PDFs, generating the Annual Sub-Program Report, reconciling Camps/Activities costings, and comparing period-over-period Operating Statements.

It also generates **PDF reports for School Council submission** (cover pages, variance analysis, appendices).

The starting point is an existing single-tool app (`app.py`, Tkinter + openpyxl + pywin32, shipped as an MSIX). This handoff takes it to a v2 that houses five tools under one shell, with a framework that makes adding a sixth, seventh, nth tool a ten-minute exercise.

---

## About the Design Files

The files in `ui_kits/` are **design references created in HTML** — prototypes showing intended look and behaviour, not production code to copy directly. They use inline React + Babel so every screen can be rendered and reviewed in a browser, and each artboard on the design canvas is a different state or variant.

Your task is to **recreate these HTML designs in the target environment** — Python + Tkinter for the desktop app (extending `app.py`), and a JS/React framework of your choosing for the future web toolkit. Do not ship the HTML. The HTML is a spec, not a codebase.

Typography, colour, spacing, state/colour, and PDF template rules are canonical and live in `colors_and_type.css` + `ui_kits/brand_type/`. Those values must be preserved exactly in the implementation.

---

## Fidelity

**High-fidelity.** Every screen carries final colours, typography, spacing, state rules, and copy. Account codes, dollar amounts, and error messages in the mockups are realistic but illustrative — you do not need to preserve the specific figures, only the structure, format, and style.

Low-fidelity areas (call these out if you spot them): the wordmark is built from system fonts and is deliberately not a custom lockup; iconography is minimal by design; charts are not yet included.

---

## Scope — what's in the bundle

| Folder | What | Implementation target |
|---|---|---|
| `ui_kits/brand_type/` | Type system v1.1 · 10 artboards · Aptos / Source Serif 4 / Cascadia Mono · 8-token scale · numerics contract · A4 PDF cover + body templates | Canonical — applies to both desktop and web |
| `ui_kits/desktop_app/` | Single-tool Tkinter app (the existing `app.py`, as a design reference) — 5 states: idle, running, success, warning, error | Existing codebase, already built |
| `ui_kits/desktop_multitool/` | **v2 desktop** — left-rail tool picker, 5 tools in one window, ttk.Frame per tool | **Primary implementation target** — Python + Tkinter |
| `ui_kits/web_toolkit/` | Future web shell — left rail + work area + status bar · all 5 tools as React components | Future — deferred until desktop v2 ships |
| `colors_and_type.css` | Single source of truth for design tokens | Port to Python constants for Tkinter; use as-is for web |
| `EXTENDING.md` | Framework contract — how to add a tool, how to add a PDF report | Required reading for the next developer |

---

## The five tools

Each tool is a `ttk.Frame` subclass (desktop) or a React component (web). Inputs and outputs are declared as **data** on the tool class; the shell renders the file pickers, primary button, progress bar, status line, and log viewer from that declaration.

### 1. Master Budget (existing, in `app.py`)
Import an Expense Sub-Program XLSX export into the Master Budget macro-enabled workbook. Matches account codes, writes totals into the template, preserves macro button bindings. Highlights mismatches in red (`#F4CCCC`) and source-only rows in green (`#E2F0D9`) — openpyxl fills.

**Inputs:** Expense Sub-Program file · Master Budget template
**Output:** Annotated `.xlsm` workbook
**States:** idle · running (progress bar) · success · warning (mismatches) · error

### 2. SRP Comparison (new)
Compare the Indicative SRP PDF against the Confirmed SRP PDF line by line. Output is an `.xlsx` with variance columns. Lines categorised: unchanged, increased, decreased, new in confirmed, removed.

**Inputs:** Indicative SRP (PDF) · Confirmed SRP (PDF)
**Output:** `SRP_Compare_YYYY_timestamp.xlsx`

### 3. Annual Sub-Program Report (new)
Reformat the raw Annual Sub-Program Budget Report export, merge in prior-period commentary, flag over-budget lines, produce a Council-ready workbook. Left rail groups sub-programs by faculty.

**Inputs:** Sub-Program report (XLSX) · Prior-period comments (XLSX)
**Output:** `Annual_SubProgram_<period>_AUTO_<timestamp>.xlsx`

### 4. Camps / Activities Reconciliation (new)
Three-way reconciliation: Camps Register × Supplier Invoices × Sub-Program Ledger. Outputs per-activity variance rows with Match / Minor / Open status.

**Inputs:** Camps register · Supplier invoices · Sub-Program ledger
**Output:** `Camps_Reconciliation_AUTO_<timestamp>.xlsx`

### 5. Operating Statement (new)
Compare the current-period GL Operating Statement against a prior period. User-configurable variance threshold (dollars or percent). Output is a variance-filtered `.xlsx`.

**Inputs:** Current period (XLS) · Prior period (XLS)
**Threshold controls:** dollar value · percentage
**Output:** `OpStat_Compare_<timestamp>.xlsx`

---

## Shell anatomy (desktop v2)

```
┌─ Window title bar (Windows 11 chrome) ────────────────────────┐
│ [SF] School Finance Toolkit v2.0.0 — <Active Tool Name>       │
├──────────┬────────────────────────────────────────────────────┤
│ Budget   │  Tool content area (ttk.Frame per tool)            │
│  ▸ MB    │  ┌────────────────────────────────────────────┐    │
│  ▸ SRP   │  │ Section header + subtitle                  │    │
│  ▸ SP    │  ├────────────────────────────────────────────┤    │
│ Recon    │  │ File pickers (declared as data)            │    │
│  ▸ Camps │  ├────────────────────────────────────────────┤    │
│  ▸ OpSt  │  │ Action buttons (primary + secondary)       │    │
│ ────     │  ├────────────────────────────────────────────┤    │
│ Instr.   │  │ Status banner (neutral/ok/warn/danger)     │    │
│ About    │  │ Progress bar                               │    │
│          │  │ Metric cards (optional)                    │    │
│          │  │ Log viewer / result table                  │    │
│          │  └────────────────────────────────────────────┘    │
├──────────┴────────────────────────────────────────────────────┤
│ Ready                            v2.0.0 · ivan.wang@…         │
└───────────────────────────────────────────────────────────────┘
```

Rail width: **220 px**. Status bar height: **22 px**. Left padding inside tool frames: **16 px**. Everything else follows the 4 px grid in `colors_and_type.css` (`--sp-1` … `--sp-16`).

See `ui_kits/desktop_multitool/tk-shell.jsx` for the visual reference and `ui_kits/desktop_multitool/tk-tools.jsx` for the five tool frames.

---

## Framework contract — non-negotiable

Implementing these as five hand-rolled screens will fail the moment a sixth tool is requested. Implement the framework described in `EXTENDING.md` first, then build each tool against it.

```python
# toolkit/base_tool.py
class BaseTool:
    id:      str                 # kebab-case unique id
    group:   str                 # "Budget" | "Reconciliation" | new group
    label:   str                 # display name in rail
    order:   int = 100           # sort order inside group
    short:   str                 # 2-letter mark (e.g. "MB", "SR")

    inputs:  list[InputSpec] = []   # file pickers rendered by shell
    output:  OutputSpec | None = None
    primary_button: str = "Generate"

    pdf_template: str | None = None      # optional WeasyPrint cover
    pdf_body:     str | None = None      # optional WeasyPrint body

    def run(self, paths: dict, progress: Callable[[int, str], None]) -> ToolResult: ...
    def secondary_actions(self) -> list[tuple[str, Callable]]: return []
```

The shell:
- Adds the tool to the left rail under its `group`, sorted by `order`.
- Renders file-picker rows from `inputs` + `output`.
- Wires the primary button to `run()` on a worker thread; posts `progress()` callbacks to the status bar and progress widget.
- Renders `ToolResult.log_lines` with colour tags from `colors_and_type.css`.
- Surfaces `secondary_actions()` as additional buttons.

**Do not** add shell-aware code inside a tool. If a tool needs shell behaviour the shell doesn't provide, extend `BaseTool` / the shell, not the tool.

### Registration

`toolkit/registry.py`:

```python
TOOLS = [
    MasterBudgetTool,
    SrpComparisonTool,
    SubProgramReportTool,
    CampsReconciliationTool,
    OperatingStatementTool,
    # Append new tools here. No shell or installer changes.
]
```

---

## Design tokens

All tokens live in `colors_and_type.css`. Port them to a Python module (`toolkit/tokens.py`) for Tkinter; use the CSS directly on the web.

### Brand colours
| Token | Value | Usage |
|---|---|---|
| `--brand-navy` | `#185787` | SF monogram, focus accents, section rules |
| `--brand-navy-700` | `#124466` | Info banner text |
| `--brand-navy-tint` | `#E6EEF5` | Info banner fill |
| `--brand-accent` | `#2B7CB8` | Hover / focus |

### Semantic state (direct lift from `app.py`)
| State | Fg | Bg |
|---|---|---|
| ok | `#0B6E0B` | `#E8F5E9` |
| warning | `#9A6700` | `#FFF7E6` |
| danger | `#B00020` | `#FDECEA` |
| info | `#124466` | `#E6EEF5` |

### Data highlights (openpyxl fills)
| Fill | Hex | Meaning |
|---|---|---|
| Mismatch | `#F4CCCC` | Account code missing from source |
| Source-only | `#E2F0D9` | New line inserted from source |
| Edited | `#FFF2CC` | User override convention |

### Type — 8-token scale
| Token | Size | Weight | Family | Usage |
|---|---|---|---|---|
| `display / 32` | 32 | 700 | Source Serif 4 | Hero metric · PDF cover subtitle |
| `h1 / 24` | 24 | 600 | Source Serif 4 | PDF chapter title · app section header |
| `h2 / 20` | 20 | 600 | Aptos / Segoe UI | Tool screen title |
| `h3 / 16` | 16 | 600 | Aptos / Segoe UI | Card title · form group heading |
| `body / 14` | 14 | 400 | Aptos / Segoe UI | Default body |
| `caption / 12` | 12 | 400 | Aptos / Segoe UI | Captions · file paths |
| `num / 24` | 24 | 600 | Cascadia Mono | Metric card values · totals |
| `num-sm / 13` | 13 | 500 | Cascadia Mono | Table cells · log lines |

### Spacing (4 px grid)
`--sp-1` = 4 px … `--sp-16` = 64 px. Section gaps: `--sp-4`. Tool frame padding: `--sp-4`. Rail item padding: `4px 12px 4px 30px`.

### Fonts — Tkinter mapping
| Surface | Tkinter font spec |
|---|---|
| Window title, menus, labels | `("Aptos", 9)` → fallback `("Segoe UI", 9)` |
| Tool title | `("Aptos", 12, "bold")` |
| Metric number | `("Cascadia Mono", 14, "bold")` |
| Log viewer, file paths | `("Cascadia Mono", 10)` → fallback Consolas |
| Treeview rows | `("Aptos", 9)` / `("Cascadia Mono", 9)` for `$` columns, `anchor='e'` |

Detect Aptos at startup with `tkinter.font.families()`; if absent, fall back to Segoe UI.

---

## Numerics contract (canonical)

See `ui_kits/brand_type/` artboard 04. Summary:

1. **Tabular figures always.** `font-variant-numeric: tabular-nums` on web; Cascadia Mono is tabular by default; `anchor='e'` on Treeview numeric columns.
2. **Thousands separators:** comma (`1,482,310.00`). Never full stop, never spaces.
3. **Negatives:** Unicode minus U+2212 (`−`), not hyphen. Parentheses acceptable in accountancy sections of PDFs — pick one per report.
4. **Colour is never the only signal.** Negative is red *and* has a minus. Positive is green *and* has a plus.
5. **Currency:** `$` prefix, no space (`$1,482,310`). Omit symbol in `$` columns. Never "AUD".
6. **Decimals:** two places in reconciliation views; whole dollars in Council summaries and metric cards. Banker's rounding.

---

## PDF reports (School Council submissions)

PDFs are first-class outputs. Implementation uses **WeasyPrint** — HTML + CSS rendered to vector PDF. The same CSS tokens drive both the product and the PDFs.

Template rules (see `ui_kits/brand_type/` artboards 06a and 06b):

- **A4 portrait** (794 × 1123 px at 96 dpi). Landscape for wide tables via `@page { size: A4 landscape; }`.
- **Margins:** 80 px top, 72 px sides and bottom.
- **Running header** (every page): toolkit mark left, document context right.
- **Running footer** (every page): generation timestamp left, `Page N of M` right.
- **Cover page:** 4 px navy top rule, title block with section label in small-caps navy, display title in Source Serif 4, italic subtitle, metadata block at foot (Prepared by / Reviewed by / Document id).
- **Body page:** section number in small-caps navy, section title in Source Serif 4, running prose in Source Serif 4, data table with Cascadia Mono numerals, tabular figures, tight row padding.

Fonts are **embedded once in the MSIX**, not per-PDF — keeps each export ~50 KB instead of ~1 MB.

---

## Interactions & behaviour

### Tool switching
Click a left-rail item → the shell swaps the tool frame in the work area. Previously-entered file paths persist in-memory for the session (do not lose work on accidental tool switch). Selected tool is underlined with Windows blue (`#3399FF`) row highlight.

### File pickers
Triggered by the `Browse` button; `filedialog.askopenfilename` with the `filetypes` list from the tool's `inputs` spec. Selected path is displayed as read-only text (truncated with ellipsis if overflowing) in Cascadia Mono.

### Primary action
On click: disable all inputs, show the progress bar, switch to "Running" state. Run the tool's `run()` on a worker thread. On completion: re-enable inputs, show result banner (colour from `ok` / `warn` / `danger`), fill metric cards, populate log viewer.

### Progress
`run()` receives a `progress(percent: int, message: str)` callback. Shell updates the progress bar (0–100) and the status bar message. Progress bar style: Windows vista `progressbar.Horizontal.TProgressbar`, gradient green.

### Log viewer
Monospace text widget. Lines are tagged with one of: `heading` (bold), `ok` (green), `warning` (amber), `danger` (red), `extra` (light green for source-only rows), `muted` (grey). Colours from `colors_and_type.css`.

### Result tables
`ttk.Treeview` with vista theme. Numeric columns: `anchor='e'`, Cascadia Mono font, tabular figures. Row highlight colours follow data-highlight tokens (mismatch red, source-only green, edited yellow) via `tree.tag_configure(...)`.

### Tool buttons
Sentence case (`Generate budget workbook`, not `Generate Budget Workbook`). Focused primary button gets a 2 px accent blue ring. Disabled buttons use `#F5F5F5` fill and `#A0A0A0` text.

---

## State management

Per tool (lives on the tool instance):
```python
inputs:       dict[str, Path]      # current file-picker values
output:       Path | None
status:       "idle" | "running" | "success" | "warning" | "error"
progress:     int                  # 0..100
progress_msg: str
result:       ToolResult | None    # set by run() on completion
```

Shell-level:
```python
active_tool_id: str
tools:          dict[str, BaseTool]    # id → instance
```

No persistence required for v2 — every session starts fresh. If you add it later, persist `last_active_tool_id` and per-tool `last_inputs` to `%APPDATA%/SchoolFinanceToolkit/session.json`. Do not persist file contents.

---

## Screens — detailed layout

See the artboards in `ui_kits/desktop_multitool/index.html` for the canonical rendering of all five screens. Each shows:

- Exact field order and labels
- Button order and labels (primary first, Browse aligned to inputs, secondary row with Clear at the end)
- Banner copy for success / warning / error states
- Metric card layout (4 columns, equal width, ~90 px tall)
- Log viewer / result table dimensions and content

Use these as pixel-accurate references for layout. Match spacing, alignment, and colour exactly. The copy in the mockups is production-quality — you can ship it as-is.

---

## Assets

- `ui_kits/../../assets/SplashScreen.png`, `Square150x150Logo.png`, `Square44x44Logo.png`, `StoreLogo.png`, `Wide310x150Logo.png` — existing MSIX logos, reuse as-is.
- No custom iconography beyond these logos. The rail uses small carets (▾) drawn inline; status icons are handled by banner fill colour, not glyphs.
- Fonts:
  - **Aptos** — system on Win11 22H2+, detect at startup
  - **Segoe UI** — fallback, ships with Windows
  - **Source Serif 4** — embed in MSIX (`assets/fonts/source-serif-4/`), OFL licence
  - **Cascadia Mono** — ships on Win10 21H1+ and Win11; fall back to Consolas

---

## Files in this bundle

```
design_handoff_school_finance_toolkit/
├── README.md                            ← you are here
├── EXTENDING.md                         ← framework contract — READ THIS
├── colors_and_type.css                  ← design tokens — canonical source
└── ui_kits/
    ├── brand_type/index.html            ← type system v1.1 (10 artboards)
    ├── desktop_app/
    │   ├── index.html                   ← existing Tkinter app states
    │   ├── mb-app.jsx                   ← Master Budget screen
    │   ├── windows-chrome.jsx
    │   └── design-canvas.jsx
    ├── desktop_multitool/
    │   ├── index.html                   ← PRIMARY target — v2 multi-tool
    │   ├── tk-shell.jsx                 ← window chrome + left rail
    │   ├── tk-primitives.jsx            ← TkButton, TkEntry, TkLog, TkTable, …
    │   └── tk-tools.jsx                 ← all 5 tool frames
    └── web_toolkit/
        ├── index.html                   ← future web shell
        ├── shell.jsx
        └── tool-*.jsx                   ← 5 tool components
```

Open each `index.html` in a browser to review. All use React + Babel via unpkg, no build step needed.

---

## Suggested implementation order

1. **Read `EXTENDING.md`.** The framework contract is the non-negotiable part; everything else is applying it.
2. **Refactor the existing `app.py`** into `toolkit/shell.py` + `toolkit/base_tool.py` + `tools/master_budget/frame.py`. Confirm it still builds the MSIX and runs identically. No new tools yet.
3. **Add the left rail** and tool-switching. Still only Master Budget registered.
4. **Port `colors_and_type.css` tokens** to `toolkit/tokens.py` and wire into `ttk.Style()` at startup.
5. **Add tools 2–5** one at a time, in the order: SRP Comparison → Operating Statement → Sub-Program Report → Camps Reconciliation. (SRP and OpStat are the simplest; the report and reconciliation tools need more data plumbing.)
6. **Add PDF report generation** via WeasyPrint for Sub-Program Report first (the tool with the clearest Council-facing output). Follow the A4 templates in `ui_kits/brand_type/` 06a and 06b exactly.
7. **Bump version to 2.0.0** and rebuild the MSIX via the existing `build_msix_package.ps1`.

The web toolkit in `ui_kits/web_toolkit/` is **deferred** — do not build it now. It exists in the handoff so that when the web port is scoped in 12–18 months, the design work is already done and the `TOOLS` registry pattern ports 1:1.

---

## Questions to raise with the team before you start

- **Tkinter vs Qt for v2?** The mockups are Tkinter-native. If the team has capacity for PySide6 it would give a nicer shell, but it doubles the rebuild effort. Default answer: stay on Tkinter.
- **Is WeasyPrint acceptable in the MSIX?** It pulls in Pango/Cairo via GTK. ReportLab is a smaller but less CSS-faithful alternative. Default: WeasyPrint — the CSS reuse is worth the installer size.
- **Do School Councils see drafts or only finals?** Affects whether "Draft" watermarking is needed on PDF covers.
- **Where do CASES21 exports come from in the Camps reconciliation flow?** The mockup assumes a Sub-Program ledger export; confirm the exact export format.

---

_Prepared by the design conversation for the Victorian School Finance Toolkit v2. Everything in `ui_kits/brand_type/` is the canonical design authority; everything in the other `ui_kits/` folders is a rendering of those tokens applied to a surface._
