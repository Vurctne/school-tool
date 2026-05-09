# Rounds 25 + 26 — Combined tab filter totals + Excel Combined sheet

**Date:** 2026-05-01
**Scope:** Two related Combined-view follow-ups bundled into one
handoff because they shipped together.

---

## Round 25 — Combined tab totals react to faculty filter

### Problem

Pre-25, the Combined tab title showed totals computed at build time —
e.g. `Combined · YTD subsidy $80,000 · YTD surplus $40,000`.  When the
user clicked a faculty in the side rail, the **rows** narrowed
correctly (Round 23 fix) but the **tab title** stayed at the unfiltered
totals, so it looked like the totals were lying.

### Fix

Each Combined row now carries `_net_ytd_raw` (raw signed `Decimal`).
The shell's filter handler (`_apply_filter` / `_clear_filter`)
recomputes per-tab totals from the filtered rows and updates the tab
title via `notebook.tab(idx, text=...)`:

- Rows where `_net_ytd_raw < 0` contribute to filtered subsidy total.
- Rows where `_net_ytd_raw > 0` contribute to filtered surplus total.

Implementation lives in `toolkit/shell.py::_relabel_combined_tab_if_applicable`
and is generic — it triggers on any tab whose rows carry the
`_net_ytd_raw` marker, so future tools that emit similar combined rows
get the same behaviour for free.

### Files touched

```
MOD   tools/sub_program/frame.py
       - _build_combined_rows: each row gains _net_ytd_raw + _net_budget_raw
         Decimal fields

MOD   toolkit/shell.py
       - _relabel_combined_tab_if_applicable helper (new)
       - _apply_filter / _clear_filter call it after each tab's set_rows
       - import Any, cast from typing
```

---

## Round 26 — Excel export: include Combined sheet toggle

### Problem

The Excel export wrote Revenue + Expenditure sheets but no Combined
sheet — the YTD subsidy/surplus picture lived only in the in-app
Combined tab.  User asked for the option to include it in the export.

### Solution

`Export to Excel` now pops a yes / no / cancel dialog:

> **Include the Combined sheet?**
>
> Yes — write Revenue, Expense, and Combined sheets (Combined shows
>   per-sub-program Net YTD).
> No  — write Revenue and Expense sheets only.
> Cancel — don't export.

The Combined sheet, when included, has:

- Title row (merged): `Annual Sub-Program Budget Report — Combined — {period}`
- Header row: `Sub-program · Description · Revenue YTD · Expense YTD · Net YTD · Annual budget net`
- One row per sub-program, sorted by Net YTD ascending (biggest deficit
  first).
- Subsidised rows (Net YTD < 0) get the canonical pink HL_MISMATCH
  fill so users can scan for school-funded gaps.
- Numeric cells use the `_ACCOUNTING_FMT` standard from the existing
  Revenue / Expenditure sheets.
- Frozen panes at A3 (header row stays visible while scrolling).

### Files touched

```
MOD   tools/sub_program/logic.py
       - _write_xlsx gained ``include_combined: bool = False`` keyword arg
       - new _write_combined_sheet helper aggregates Rev/Exp YTD per
         sub-program and writes the Combined sheet

MOD   tools/sub_program/frame.py
       - _export_xlsx pops askyesnocancel dialog and forwards the choice
         to logic._write_xlsx
```

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict toolkit/ tools/ tests/  → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 534 passed, no regressions
```

The token drift guard stays happy — no new hex literals; the Combined
sheet's pink fill reuses `_OVER_FILL` (HL_MISMATCH).

---

## What to manually verify on Windows

### Round 25

1. Generate a Sub-Program report, switch to the Combined tab.  Note the
   tab title totals: `Combined · YTD subsidy $X · YTD surplus $Y`.
2. Click a faculty in the rail.  The Combined tab title should
   narrow to that faculty's totals (e.g. only the Curriculum
   sub-programs' subsidy / surplus).
3. Click another faculty.  Title updates again.
4. Click the chip's `× clear filter`.  Title returns to the all-rows
   totals.

### Round 26

1. Run Generate report, then click Export to Excel.
2. The dialog should ask whether to include Combined sheet.
3. **Yes** — open the saved XLSX; should have Revenue, Expense, AND
   Combined tabs.  Combined tab shows per-sub-program YTD with pink
   fill on subsidised rows.
4. **No** — saved XLSX has only Revenue and Expense.
5. **Cancel** — no file written; no error message.

---

## Cross-FS sync gotcha hits this round

Heavy this round.  `toolkit/shell.py`, `tools/sub_program/frame.py`,
and `tools/sub_program/logic.py` all truncated mid-edit on the bash
mount, sometimes more than once each.  The bash filesystem also left
trailing null-byte padding (`\x00`) at end-of-file twice — `head -n N
file > /tmp/clean ; cp /tmp/clean file` is the right recovery.

CLAUDE.md already documents the pattern.  Worth flagging that on this
session the truncation happened on every third or fourth Edit; if the
sandbox stays this flaky, batching multiple edits via /tmp file
replacement (rather than incremental Edit calls) would save tokens.
