# Round 22b — View tabs + log collapse + Combined subsidy viz

**Date:** 2026-05-01
**Scope:** Three highest-impact items from the Round 22 backlog after
22a shipped inline commentary.  Round 22c will pick up the remaining
polish items (output pill, sliders side-by-side, auto-collapse inputs,
faculty rail data-bars).

---

## Before / after

**Before (Round 22a):** dashboard real estate dominated by a redundant
log block; a single Treeview showing all rows mixed (Revenue + Expense)
without a fast way to compare; no view of school-subsidised
sub-programs.

**After (Round 22b):**
- Result area is now a `ttk.Notebook` with three tabs:
  `Revenue (n)` · `Expense (n)` · `Combined · school subsidy $X`.
- Log block hidden by default behind a `Show log ▾` toggle button.
- Combined tab shows per-sub-program aggregates with a unicode-bar
  Budget shape column; rows where Expense > Revenue (school is
  propping up the gap) sort to the top and render with the pink
  HL_MISMATCH fill.

---

## What changed

### 1. View tabs (Revenue / Expense / Combined)

**`toolkit/base_tool.ToolResult`** gained an optional
`table_tabs: list[tuple[str, TableSpec]] | None` field.  When set,
the shell's `_build_table_widget` returns a `ttk.Notebook` with one
Table per entry instead of the single-Table render.  `result.table`
is kept non-None as a fallback for any path that hasn't learned about
tabs (e.g. legacy `preview_update` callers).

**`toolkit/shell.py::_build_table_widget`** rewritten to take three
priority paths:
1. `result.table_tabs` → ttk.Notebook with one Table per tab.
2. `result.table` → single Table (current path).
3. Legacy `result.table_columns` + `result.table_rows`.

**`_tool_tables`** type widened from `dict[str, Table | None]` to
`dict[str, tk.Widget | None]` so it can carry a Notebook.  The
faculty rail click-to-filter (`_apply_filter` / `_clear_filter`) now
guards `set_rows` calls behind `isinstance(..., Table)` so the
Notebook variant doesn't crash; tab-aware filtering can be added in
a follow-up if users ask for it.

**`tools/sub_program/frame.py::_build_result`** emits three tabs:
- **Revenue (n)** — filtered slice of `table_rows` where
  `account == "Revenue"` (carrying over comment sub-rows).
- **Expense (n)** — filtered slice of `table_rows` where
  `account == "Expenditure"` (with comment sub-rows).
- **Combined · school subsidy $X** — synthetic per-sub-program
  aggregation (see §3 below).  When total subsidy is zero, the
  label drops the `· school subsidy $X` suffix.

Tab labels carry the row count (Revenue/Expense) or subsidy total
(Combined) so the user gets a one-glance summary without switching
tabs.

### 2. Log block collapsed by default

The log block used to dominate the result area with content largely
duplicated in the banner.  Round 22b wraps it in a collapsible:

- A small `Show log ▾` button is packed in the log frame.
- The actual `LogView` lives in a child Frame that starts unpacked.
- Clicking the button toggles a `tk.BooleanVar` and flips the child
  Frame's pack state + the button label (`Show log ▾` ↔ `Hide log ▴`).
- On every fresh result render, the toggle resets to collapsed so the
  log doesn't bleed across runs.

The shell stores the toggle state per-tool in `widget_map` keyed
`__log_toggle_btn__` / `__log_toggle_var__` / `__log_body__`.

### 3. Combined subsidy viz

**`tools/sub_program/frame.py::_build_combined_rows`** builds a
synthetic row list:

- Aggregates Revenue and Expenditure per sub-program code.
- `subsidy = max(0, expense - revenue)` — the school-funded gap.
- `subsidy_pct = subsidy / expense × 100` for sub-programs with
  expense > 0; otherwise `—`.
- Sorts by subsidy descending, then by sub-program code, so the
  biggest gaps appear first.
- Each row carries a 20-character unicode bar in the
  `Budget shape` column: `█` blocks for the Revenue portion and
  `▓` blocks for the subsidy portion, proportional within-row.

**Combined-view columns** (`_COMBINED_COLUMNS`):
`Sub-program · Description · Revenue · Expense · Subsidy · Subsidy % · Budget shape`.

**Row styling:** subsidised rows (`_subsidised=True`) get the same
HL_MISMATCH pink background + danger foreground used for
over-budget rows in the main views.  Non-subsidised rows render
plain.

The Combined tab does NOT wire `on_row_click` — comment editing is
scoped to per-line dashboard rows in Revenue/Expense tabs, not the
sub-program-level aggregate.

---

## Files touched

```
MOD   toolkit/base_tool.py
       - ToolResult.table_tabs added (optional list of (label, TableSpec))

MOD   toolkit/shell.py
       - _build_table_widget: 3-priority render (tabs → table → legacy)
       - _tool_tables type widened to tk.Widget | None
       - rail filter guarded by isinstance(..., Table)
       - log frame wrapped in Show/Hide log toggle
       - log toggle resets to collapsed on each fresh result render

MOD   tools/sub_program/frame.py
       - _COMBINED_COLUMNS schema (7 cols incl. Budget shape)
       - _build_combined_rows aggregates per-sub-program subsidy +
         renders unicode bar
       - _build_result emits table_tabs[Revenue, Expense, Combined]
       - _combined_row_style paints subsidised rows pink

MOD   tools/sub_program/tests/test_frame.py
       - new TestRound22bViewTabs class (6 tests)
```

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict toolkit/ tools/ tests/  → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 467 passed (including the cross-tool tests)
pytest tools/sub_program/tests/test_frame.py
                         → 67 passed (6 new Round 22b tests)
```

Pre-existing test pollution in
`tools/sub_program/tests/test_frame.py` (when run in the same pytest
process as `test_shell_smoke.py`) and the unrelated
`tools/operating/tests/test_logic.py` sample-PDF naming drift are
both unchanged.

---

## What remains (Round 22c)

1. **Output pill** — promote the durable "Output: D:\…" log line to
   a clickable chip near the Open output folder button.
2. **Sliders side-by-side** — Revenue + Expense thresholds in one row
   sharing a hint line.
3. **Auto-collapse inputs** after first run into a summary chip.
4. **Faculty rail data-bars** behind each rail row scaled to usage %.
5. **Tab-aware faculty filter** — currently disabled when tabs are
   present (rail click is silently a no-op for tabs).  Re-enable by
   filtering the active tab's rows.

---

## Cross-FS sync gotcha hits this round

Five truncations on `tools/sub_program/frame.py` (the file grew the
most) plus one on `toolkit/base_tool.py` and one on `toolkit/shell.py`.
All recovered via the standard `head -n N file > /tmp/head ; cat
/tmp/head /tmp/tail > /tmp/full ; cp /tmp/full file ; touch file`
pattern.  CLAUDE.md already documents the pattern.

---

## What to manually verify on Windows

The Tk smoke tests skip on Linux CI so the user should sanity-check:

1. **Three tabs appear** above the data area: `Revenue (n)`,
   `Expense (n)`, `Combined · school subsidy $X` (or just
   "Combined" if no subsidy).  Click each and verify rows update.

2. **Log collapsed by default** — the log block should show only a
   `Show log ▾` button under the action row.  Click it; the log body
   appears and the button becomes `Hide log ▴`.  Run again; log
   collapses.

3. **Combined tab visual** — pink rows at the top show
   sub-programs the school is subsidising; the `Budget shape` column
   shows a `████▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓` style bar where `█` is Revenue
   and `▓` is the subsidised portion.

4. **Row click in Revenue/Expense tab** still opens the inline
   comment editor from Round 22a.  Comments should also flow through
   to the matching tab's rows (only the parent line's tab; the
   Combined tab doesn't show comments, by design).

5. **Faculty rail click** behaves predictably — currently a no-op
   when tabs are used (Round 22c will re-add tab-aware filtering).
