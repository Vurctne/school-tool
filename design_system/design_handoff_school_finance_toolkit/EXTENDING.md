# Extending the toolkit

The framework is built around **one registry per UI kit**. Adding a new tool is three edits: register it, write its module, and re-build. No changes to the shell, rail, or installer script.

---

## Desktop multi-tool (Option A — Python / Tkinter)

This is the path the existing `app.py` grows into. A sixth tool ships as a v2.1 update of the same MSIX.

### 1. Write the tool module

Create `tools/<id>/frame.py` exposing a single class that builds a `ttk.Frame`:

```python
# tools/fees/frame.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from toolkit.primitives import FileRow, Banner, ProgressBar, LogView, Table
from toolkit.base_tool import BaseTool, ToolResult

class FeesReconciliationTool(BaseTool):
    id      = "fees"
    group   = "Reconciliation"           # shown in the left rail
    label   = "Student Fees"
    order   = 50                          # sort order within group
    short   = "SF"                        # 2-letter mark

    # File pickers declared as data — the shell renders them.
    inputs  = [
        {"key": "fees_register", "label": "Student fees register",  "filetypes": [("Excel", "*.xlsx *.xlsm")]},
        {"key": "receipts",      "label": "Receipts export",        "filetypes": [("CSV", "*.csv"), ("Excel", "*.xlsx")]},
    ]
    output  = {"key": "output",  "label": "Output workbook",        "suffix": ".xlsx"}

    # Optional — shown as the primary button. Defaults to "Generate {label}".
    primary_button = "Generate reconciliation"

    def run(self, paths, progress) -> ToolResult:
        # Your logic here. Call progress(percent, message) as you go.
        # Return a ToolResult with summary text, log lines, and any highlighted rows.
        ...
```

### 2. Register it

Append one line to `toolkit/registry.py`:

```python
from tools.fees.frame import FeesReconciliationTool

TOOLS = [
    MasterBudgetTool,
    SrpComparisonTool,
    SubProgramReportTool,
    CampsReconciliationTool,
    OperatingStatementTool,
    FeesReconciliationTool,        # ← new
]
```

The shell:
- Adds it to the left rail under the `group` you set, sorted by `order`.
- Renders the file-picker rows from `inputs` + `output`.
- Wires the primary button to `run()`.
- Pipes `progress()` callbacks to the shared progress bar + status line.
- Renders `ToolResult.log_lines` with the existing colour tags.
- Writes a matching entry in `USER_GUIDE.txt` from the tool's docstring if present.

### 3. Package it

No changes to `build_msix_package.ps1` or the PyInstaller spec — the registry is imported at startup, so added modules are picked up automatically. Bump the version in `app_metadata.py`.

### What you can extend without touching shell code

| Extension point     | How                                          |
|---|---|
| New banner level    | Add to `toolkit.primitives.BANNER_COLORS`    |
| New log tag         | Add to `toolkit.primitives.LOG_TAGS`         |
| New highlight fill  | Add to `toolkit.highlights` (mirrors openpyxl fills) |
| Tool-specific modal | Override `BaseTool.open_dialog(name)`        |
| Extra toolbar btn   | Return additional entries from `secondary_actions()` |

### What stays locked (by design)

- Window chrome, title bar, status bar layout
- Left-rail styling and sort behaviour
- Focus ring colour, font stack, 4 px spacing grid
- Australian English copy rules (sentence-case buttons, no emoji)

Editing those lives in `toolkit/shell.py` and should be a deliberate design change, not a per-tool tweak.

---

## Web toolkit (future path)

Same registry shape, different host. `ui_kits/web_toolkit/shell.jsx` already exports a `TOOLS` array; adding a screen is:

1. Create `tool-<id>.jsx` exposing a component on `window`.
2. Append an entry to the `TOOLS` array in `shell.jsx` (same fields: `id`, `group`, `name`, `short`, `sub`, `icon`).
3. Add a `<script type="text/babel" src="tool-<id>.jsx">` to `index.html`.

The rail, top bar, status bar, and tool-switching plumbing are identical across kits — that's the contract that lets a tool ship to desktop first and web later without rewriting the screen.

---

---

## Adding a PDF report

PDFs (School Council submissions, cover pages, appendices) are first-class outputs. They live in `reports/` alongside `tools/`.

### Module layout

```
reports/
  sub_program_cover.html     ← WeasyPrint template · Source Serif 4 lead
  sub_program_body.html
  operating_statement.html
  assets/
    fonts/                    ← Source Serif 4 + Cascadia Mono (embedded in MSIX)
    logo.svg
  report.css                  ← imports colors_and_type.css; adds print rules
```

### Wiring a tool to a PDF

In the tool class:

```python
from toolkit.reports import render_pdf

class SubProgramReportTool(BaseTool):
    ...
    pdf_template = "reports/sub_program_cover.html"   # cover
    pdf_body     = "reports/sub_program_body.html"    # one or more body pages

    def secondary_actions(self):
        return [("Save as PDF…", self.save_pdf)]

    def save_pdf(self, result: ToolResult, out_path: Path):
        render_pdf(
            templates=[self.pdf_template, self.pdf_body],
            context={"result": result, "school": self.school_profile()},
            out_path=out_path,
        )
```

`render_pdf` uses **WeasyPrint** and renders the HTML templates with `report.css`. The same CSS tokens that drive the product also drive the PDF, so a colour or font change propagates to both.

### Fonts in PDFs

Source Serif 4 and Cascadia Mono are embedded once in the MSIX (`assets/fonts/`) and installed with the app. The PDF references them as **system fonts** — not embedded per-file. This keeps each PDF ~50 KB instead of ~1 MB.

Aptos / Segoe UI are already present on every DoE Windows machine.

### PDF template rules

- Every page: running header with the toolkit mark on the left, document context on the right.
- Every page: footer with generation timestamp (left) and "Page N of M" (right).
- A4 portrait by default (794 × 1123 px at 96 dpi). Landscape with `@page { size: A4 landscape; }` for wide tables.
- Margins: 80 px top, 72 px sides and bottom.
- Cover pages always have the 4 px navy top rule and document metadata block at the foot.
- Body pages always show the section number in small-caps navy above the section title.

See `ui_kits/brand_type/` artboards 06a and 06b for the canonical templates.

---

## Adding a tool — 10-minute checklist

- [ ] Pick a 2-letter `short` mark and a stable `id` (kebab-case).
- [ ] Decide its `group` — `Budget`, `Reconciliation`, or a new one.
- [ ] Declare `inputs` / `output` — the shell does the file-picker UI.
- [ ] Implement `run()` — call `progress()`, return a `ToolResult`.
- [ ] Register in `TOOLS`.
- [ ] Add a mock artboard to the matching UI kit (`tk-tools.jsx` or `tool-<id>.jsx`) so the design sits alongside the others during review.
- [ ] Update `README.md` source table if it consumes a new source file format.

No changes to shell, installer, or design tokens required.
