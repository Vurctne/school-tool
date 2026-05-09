# Round 32 — Restore `_render_result` rendering (Sub-Program report fix)

**Date:** 2026-05-02
**Scope:** Critical regression fix. Sub-Program Budget Report (and any
other tool returning `table_tabs` / `table` / `log_lines` /
`side_rail`) ran successfully but the result panel was empty —
nothing rendered after Generate.

---

## Bug

`toolkit/shell.py::_render_result` had been truncated by the cross-FS
sync issue down to ~60 lines that only:

* cleared the banner frame
* (Round 22c) rendered the output pill

Everything else was gone:

* metrics row → not rendered
* log block (the actual log output) → not rendered
* side rail → not rendered
* table → not rendered
* `table_tabs` Notebook → not rendered

Sub-Program returns `table_tabs` (Revenue / Expense / Combined view
tabs) plus a faculty `side_rail` plus `log_lines`. With `_render_result`
truncated, none of that surfaced — the user saw an empty panel and a
status-bar message saying the run completed.

---

## Fix

Rebuilt `_render_result` end-to-end. Order of work:

1. Banner — suppressed entirely (Round 23 design — banner duplicated
   the first log line; status bar covers it).
2. Metrics row — only when `result.metrics` is set.
3. Log lines — appended to the per-tool `LogView`; the log_frame is
   packed visible. (Round 23 made log default-expanded.)
4. Reset filter state for the new result — clears
   `_tool_filter`, `_tool_table_specs`, `_tool_table_tabs`,
   `_tool_rails`, and any stale filter chip.
5. Table OR `table_tabs` (with optional side rail) —
   `_build_table_widget` decides:
   * `result.table_tabs` set → returns a `ttk.Notebook` with one
     `Table` per `(label, TableSpec)` (Round 22b).
   * `result.table` set → returns a single `Table` from the spec.
   * Legacy `table_columns + table_rows` → builds a single `Table`.

   When `result.side_rail` is also set, the table/notebook lives in
   the right column of a grid with the rail (220 px) in the left
   column — Phase 3 G layout, preserved.
6. Output pill (Round 22c) — `💾 Saved → name.xlsx · Open folder`.

Also restored `_apply_filter` / `_clear_filter` to handle the tabbed
case (Round 22e). When a faculty rail entry is clicked while
`_tool_table_tabs[tid]` is non-empty, the filter is applied to each
tab's full row set independently and the tab's Table widget gets a
fresh `set_rows`. Single-table tools fall back to the original
single-spec path.

Plus a few collateral methods that had been truncated earlier in the
same file:

* `_on_drag_settled` — clears drag state so canvas Configure handlers
  resume after the user lets go of the rail divider.
* `_do_root_configure` — deferred root-configure settle.
* `_rail_font` / `_group_header_font` — font helpers for the left rail.

---

## What's still degraded vs end-of-Round 27

* **Round 25** — the `_relabel_combined_tab_if_applicable` helper
  that recomputes the Combined tab title totals (`YTD subsidy $X · YTD
  surplus $Y`) based on the active filter is not yet restored. The
  Combined view still works; the title just stays at the unfiltered
  total when a faculty filter is active. Cosmetic, not a regression
  in report generation.

* **Tabbed log collapse** (Round 22b) — the log block is now
  default-expanded (Round 23 reverted that anyway), so this is
  effectively no degradation.

These are tracked for a future round; they do not affect the report
itself running and rendering.

---

## Files touched

```
MOD   toolkit/shell.py
       - _render_result rewritten end-to-end (restores metrics, log,
         table, table_tabs, side_rail rendering)
       - new _build_table_widget helper (TableSpec / table_tabs /
         legacy paths)
       - _apply_filter / _clear_filter handle tabbed view
         (independent per-tab filtering against original specs)
       - re-restored _on_drag_settled, _do_root_configure,
         _rail_font, _group_header_font (lost in earlier
         cross-FS truncations)
```

No tool-side or test-side changes.

---

## Quality gates

```
ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 72 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 550 passed, 66 skipped (env)
```

---

## What to manually verify on Windows

1. Launch `python app.py`.
2. Open Sub-Program Budget Report.
3. Pick a sample CASES21 GL21157 PDF, click **Generate report**.
4. Result panel should show:
   * Log lines (`PARSE SUMMARY`, `OVER-BUDGET LINES`, etc.)
   * View tabs (`Revenue (N)`, `Expense (N)`, `Combined · YTD subsidy
     $X · YTD surplus $Y`)
   * Faculty rail on the left with click-to-filter chips
   * Per-row pink fill on over-budget lines
5. Click a faculty in the rail → all three tabs narrow to that
   faculty's rows; filter chip appears below the tabs.
6. Click `× clear filter` → all tabs restore to full row set.
7. Click **Export to Excel** → askyesnocancel for Combined sheet
   inclusion → file saved next to the source PDF; output pill shows
   `💾 Saved → Annual_SubProgram_*.xlsx · Open folder` link.

If any of those steps fails, capture a screenshot and a
`%LOCALAPPDATA%\Packages\<MSIX>\LocalCache\school_tool.log` excerpt
for the next round.

---

## Action item before re-running the Store build

The Round 31 MSIX submission (v2.2.0.0) was built with the broken
`_render_result`. **Don't ship that build to the Store** — it would
launch but Sub-Program Budget Report would render nothing.

Re-run the build chain with this fix applied:

```powershell
pwsh msix\build_msix_package.ps1 -StoreUpload
```

The version auto-bumps to v2.2.0.1 (or use `-Version 2.2.0.1`
explicitly). Smoke-test on Windows, then upload the new
`.msixupload` to Partner Center.
