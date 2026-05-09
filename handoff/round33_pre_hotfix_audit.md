# Round 33 — Pre-hotfix comprehensive audit

**Date:** 2026-05-02
**Scope:** Run every check we've got — linters, type checker, full test
suite, runtime smoke harness, AST shape verification, null-byte scan,
import wiring — to surface any other regressions before shipping the
v2.2.2.0 hotfix to the Store.

**Result:** Codebase is clean. No additional regressions found beyond
the Round 32 `_render_result` fix. Safe to ship the hotfix.

---

## Checks run

### 1. Static — ruff format

```
ruff format --check .   → 79 files already formatted
```

### 2. Static — ruff lint

```
ruff check .   → All checks passed!
```

### 3. Static — mypy --strict (cleared cache)

```
rm -rf /tmp/mypy_cache
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
   → no issues found in 72 source files
```

### 4. Test suite (excluding pre-existing operating sample-PDF gap)

```
pytest --ignore=tools/operating/tests/test_logic.py
   → 550 passed, 66 skipped, 1 warning
```

The 66 skipped are Linux-environment skips (no tkinter, no pywin32).
On Windows they execute and pass.

### 5. Operating tool tests (full suite)

```
pytest tools/operating/tests/   → 9 failed, 12 errored
```

**Pre-existing issue, not a regression.** The failing tests reference
`Samples/Operating Statement/GL21150_Operating Statement Detailed.pdf`
and `... Detailed 2.pdf`. The actual files in `Samples/` are
`... Detailed Feb.pdf` and `... Detailed Mar.pdf`. CLAUDE.md
documents this as the reason `--ignore=tools/operating/tests/test_logic.py`
is the standard pytest invocation. Not in scope for the hotfix —
the Operating Statement tool is "In development" / parked anyway
(not registered in the rail).

`tools/operating/tests/test_frame.py` (the frame-side tests, which
mock the logic) all pass — 37 / 37.

### 6. Runtime smoke harness (`/tmp/smoke.py`)

Hand-built script exercising each tool's import + key code paths
without needing tkinter:

```
OK    registry.all_tools() — registers hyia, master-budget, srp, sub-program, refined-pal-search
OK    ToolResult shape (table_tabs + side_rail)
OK    Master Budget Compare end-to-end (synthetic XLSM → diff → write_compare_xlsx)
OK    MasterBudget alt_run_buttons + secondary_actions
OK    RefinedPalSearch.show_clear_button == False
OK    toolkit.updates silent-fail on non-Windows (HAVE_STORE_API == False)
OK    HYIA tool has run()
OK    Sub-Program tool methods present
SKIP  TkShell methods runtime check (tkinter absent on Linux)
OK    toolkit.tokens + fills (HL_MISMATCH → argb)
```

The skipped TkShell runtime check is replaced by AST inspection
(check 7).

### 7. TkShell method-presence audit (AST-based, no tkinter import)

37 / 37 required methods/attrs present on `TkShell`:

```
_apply_filter, _build_app_header, _build_input_widget, _build_layout,
_build_range_widget, _build_rail, _build_status_bar, _build_table_widget,
_build_tool_frame, _clear_filter, _clear_results, _clear_tool,
_collapse_inputs, _do_root_configure, _expand_inputs, _group_header_font,
_handle_tk_exception, _make_press_hold_button, _on_drag_settled,
_on_progress, _on_root_configure, _on_tool_complete, _rail_font,
_render_input_summary, _render_result, _run_tool, _set_inputs_state,
_set_status, _show_about, _show_help_window, _show_privacy_policy,
_show_user, _activate_user_tab, _small_font, _update_filter_chip,
active_tool_id, rail_item_ids
```

(Total methods/attrs in class: 44 — extras are private helpers like
`_relabel_combined_tab_if_applicable` if present, `_root_configure_after`
state vars, etc.)

### 8. Null-byte scan across the repo

```
NULL bytes detected in: 0 files
```

The cross-FS sync truncations sometimes leave `\x00` padding at EOF.
Confirmed clean — the recoveries from earlier rounds didn't leave
any bad files behind.

### 9. Suspicious-tail scan

For every `.py` file: confirm the last non-empty line doesn't end
with `(`, `,`, `=`, `\\`, or `[` (footprints of mid-statement
truncation). All clean.

### 10. Duplicate-test-name scan

For every `tests/test_*.py`: confirm no two `test_*` functions in
the same file share a name (which would silently mask the second).
All clean.

### 11. Tool entry-point structural audit

Each registered tool's frame.py:

```
OK   tools/hyia/frame.py: HyiaTool has run() + primary_button
OK   tools/master_budget/frame.py: MasterBudgetTool has run() + primary_button
OK   tools/sub_program/frame.py: SubProgramBudgetReportTool has run() + primary_button
OK   tools/srp/frame.py: SrpComparisonTool has run() + primary_button
OK   tools/operating/frame.py: OperatingStatementTool has run() + primary_button
OK   tools/refined_pal_search/frame.py: RefinedPalSearchTool has run() + primary_button
```

### 12. ReportSummary / SubProgramLine shape

Sub-Program's data dataclasses (consumed by `_build_result` and the
shell) are intact:

```
SubProgramLine fields (13): sub_program, account, description, budget,
    ytd, remaining, used_pct, faculty, is_over, commentary,
    last_year_actual, last_year_budget, outstanding_orders
ReportSummary fields (13): lines, faculty_counts, over_budget_lines,
    total_budget, total_ytd, output_path, faculty_budget, faculty_ytd,
    faculty_used_pct, period_label, over_budget_threshold,
    revenue_threshold, expense_threshold
```

### 13. Primitives module exports

All 13 widget classes the shell imports from `toolkit.primitives` are
exported: `Banner, Metric, Table, LogView, ProgressBar, FileRow,
TextField, NumberField, CurrencyField, DateField, SecretField,
SectionHeader, SelectableList`.

### 14. ToolResult discriminated-union annotation

```
ToolResult.table       : TableSpec | None
ToolResult.table_tabs  : list[tuple[str, TableSpec]] | None
ToolResult.side_rail   : list[RailItem] | None
TableSpec fields       : columns, rows, row_style, on_row_click
```

All as expected — Round 22b's `table_tabs` field is correctly typed,
which is the path Sub-Program uses.

---

## Findings

**No additional regressions found.** The Sub-Program "not generating
reports" bug fixed in Round 32 was the only real issue. The codebase
is in a shippable state.

### Known not-in-scope items

These are pre-existing or acknowledged-degraded; none block the
hotfix:

* `tools/operating/tests/test_logic.py` — sample-PDF naming gap
  (CLAUDE.md documented; tool is parked).
* Round 25's `_relabel_combined_tab_if_applicable` — Combined tab
  title doesn't recompute totals on filter change. Cosmetic only;
  Round 32 handoff noted.
* `winrt-Windows.*` deps in `pyproject.toml` — Windows-only,
  `pip install -e .` resolves them on Windows. Verified
  `toolkit.updates.HAVE_STORE_API` correctly returns False on
  Linux (silent fail path is exercised by the smoke harness).

---

## Hotfix path forward

```powershell
# On the Windows machine, in repo root
cd D:\Software\Productivity\Vic_School_Finance_Tools
pip install -e .                          # ensures winrt deps if added since last run
pwsh msix\build_msix_package.ps1 -StoreUpload
```

The build auto-bumps APP_VERSION's BUILD digit (currently 2.2.1.0,
which is what's published). Next build → 2.2.2.0 — the hotfix.

After the build:

1. Sideload `msix/output/School_Tool_2.2.2.0_x64.msix` via
   `Add-AppxPackage`.
2. Smoke test specifically: open Sub-Program Budget Report, generate
   a report from a sample PDF, confirm the result panel shows the
   log + the three view tabs + the faculty rail. (This is exactly
   what was broken in v2.2.1.0.)
3. Also re-test Master Budget Compare and the existing HYIA flow
   to confirm nothing else broke.
4. If all good: upload `msix/output/School_Tool_2.2.2.0_x64.msixupload`
   to Partner Center as a new submission of School Tool.
5. Release notes: paste the line below.

### Suggested release notes for the hotfix submission

```
v2.2.2.0 — hotfix

* Sub-Program Budget Report: fixed a regression where the report ran
  but the results panel stayed empty.
* No other functional changes.
```

The Round 30 update check we shipped means every existing v2.2.1.0
user gets prompted to install v2.2.2.0 on next launch — they don't
have to find it manually in the Store.

---

## Round 33 files touched

```
ADD   handoff/round33_pre_hotfix_audit.md
```

No code changes — Round 33 is a verification-only round.
