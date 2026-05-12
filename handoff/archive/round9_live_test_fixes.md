# Round 9 — Sub-Program live-test fixes

**Date:** 2026-04-27
**Orchestrator:** Opus 4.7
**Builder:** Sonnet 4.6 (Agent K, ~103K tokens, 195 tool uses, ~25 min)
**Quality gates:** all green (ruff format, ruff check, mypy --strict, pytest **448 passed / 41 skipped / 0 failed**)

---

## Issues addressed (from user's live test on Windows)

### Fix 1 — Clear button raised "invalid command name" Tk error

**Symptom (from screenshot):**
```
An unexpected error occurred: invalid command name
".!tkshell.!frame2.!frame3.!frame4.!canvas.!frame.!frame10.!frame.!selectablelist.!frame.!canvas.!frame.!frame"
```
The footer chip "Showing 50 of 148 — clear filter ×" stayed visible despite the error.

**Root cause:** `_clear_tool` destroyed the table frame's children **before** calling `rail.set_active(None)`. The SelectableList's inner Canvas callbacks fired against destroyed widgets.

**Fix:** Reordered `_clear_tool` steps in `toolkit/shell.py` — clear rail state (including `rail.set_active(None)`) BEFORE destroying table children. Added `winfo_exists()` guard + `try/except tk.TclError` around the rail call as defence-in-depth.

**Test:** `tests/test_shell_clear.py::test_clear_tool_after_rail_result_no_tk_error` — render rail+table → apply filter → call `_clear_tool` → assert no TclError, all state cleared. Tk-skip on Linux CI.

---

### Fix 2 — User-configurable over-budget threshold (default 101%)

**Was:** `is_over = ytd > budget` hard-coded in the parser. XLSX had no row fills.
**Now:** Threshold input on the tool, default 101.0. Rows where `used_pct > threshold` get pink row fill in the XLSX export. Data bars on % column stay (independent visualization).

**Implementation:**
- New `NumberInput(key="over_budget_threshold", label="Over-budget threshold (%)", default=101.0)` in `tools/sub_program/frame.py` inputs (third position).
- `logic.generate_report()` now takes `over_budget_threshold: float = 101.0` parameter.
- Rule changed: `is_over = used_pct > threshold` (was `ytd > budget`).
- `_OVER_FILL = PatternFill(fill_type="solid", fgColor=argb(HL_MISMATCH))` re-added to `logic.py`.
- `_write_sheet` re-applies pink fill on rows where `is_over` is True.
- Banner + log lines now surface the active threshold value (e.g. "22 lines over budget (>101%)").
- In-app `_row_style` callback decoupled from numeric threshold — now reads `_over: bool` metadata key from the row dict, set in `frame.py::_build_result` from `ln.is_over`.

**`ReportSummary.over_budget_threshold: float = 101.0`** field added so downstream consumers can see what threshold was applied.

**Tests:** `TestOverBudgetThreshold` (6 tests) in `test_logic.py`; `TestThresholdInput` (5 tests) in `test_frame.py`.

---

### Fix 3 — Window resize lag

**Symptom:** dragging window edge to resize stuttered noticeably.

**Root cause:** `SelectableList`'s inner `<Configure>` handlers (Canvas + Frame) fired synchronously on every resize event — recomputing scroll regions and laying out rows on every motion tick.

**Fix:** Replaced synchronous `<Configure>` handlers with **debounced** versions using a 50ms `after()` cancel-and-reschedule pattern. Each scheduled handler is guarded with `winfo_exists()` + `try/except tk.TclError`. New attrs `_inner_configure_after` and `_canvas_configure_after` on `SelectableList`.

**Tests:** `test_selectable_list_debounce_after_ids_initialised` and `test_selectable_list_inner_configure_fires_after_idle` in `tests/test_primitives.py` (Tk-skip on Linux CI).

---

### Fix 4 — Removed Output workbook input

**Was:** Three file pickers — Sub-Program report / Prior-period comments / Output workbook.
**Now:** Two file pickers (report + comments). Output path auto-derives from the source PDF as `Annual_SubProgram_<stem>_AUTO_<YYYYMMDD_HHMM>.xlsx` next to the source.

`output = None` on `SubProgramBudgetReportTool`. Help text updated to drop the "Output workbook" step.

**Test:** `test_output_path_auto_derived` in `test_frame.py::TestRunHappyPath`.

---

## Files changed

| File | What |
|---|---|
| `toolkit/shell.py` | `_clear_tool` step reorder + `winfo_exists()` guards |
| `toolkit/primitives.py` | `SelectableList` debounce on `<Configure>` |
| `tools/sub_program/frame.py` | `NumberInput` for threshold, `output = None`, help text update, `_row_style` reads `_over` metadata |
| `tools/sub_program/logic.py` | `_OVER_FILL` re-added, `over_budget_threshold` plumbed through `generate_report` + `_write_xlsx` + `_write_sheet`, `_recompute_is_over()` helper, `ReportSummary.over_budget_threshold` field, banner copy includes threshold |
| `tools/sub_program/tests/test_logic.py` | `TestOverBudgetThreshold` (6 tests) |
| `tools/sub_program/tests/test_frame.py` | `TestThresholdInput` (5 tests), `test_output_path_auto_derived` |
| `tests/test_shell_clear.py` | `test_clear_tool_after_rail_result_no_tk_error` |
| `tests/test_primitives.py` | 2 tests for SelectableList debounce |

---

## Final quality gates

```
ruff format --check ........ 64 files already formatted
ruff check ................. All checks passed!
mypy --strict .............. Success: no issues found in 64 source files
pytest tests/ tools/ ....... 448 passed, 41 skipped, 2 warnings
port_tokens.py --check ..... OK: tokens.py in sync with CSS
```

Baseline was 434 / 38 / 0. Round 9 added 14 passing tests and 3 Tk-gated skips → 448 / 41 / 0.

---

## What the user will see when they next run the tool

1. Restart School Tool to pick up Round 9 fixes.
2. Open Sub-Program Budget Report.
3. **Two file pickers** now (Sub-Program report + Prior-period comments). The Output workbook field is gone.
4. **A new "Over-budget threshold (%)" input field** with default value `101`. Edit if you want a different threshold (e.g. 100 to flag any line over budget; 110 to only flag serious overruns).
5. Generate report.
6. Result panel: faculty rail, table with rows above threshold highlighted in pink + danger-red text. Banner says "{N} sub-programs across {M} faculties. YTD spend {pct}% of annual. {K} lines over budget (>{threshold}%)."
7. Output XLSX writes next to the source PDF as `Annual_SubProgram_<source-stem>_AUTO_<YYYYMMDD_HHMM>.xlsx`.
8. **In the XLSX**: rows above threshold get pink row fill (back from before — but threshold-based now). Data bars on `% Budget` column stay. No fills for rows below threshold.
9. **Click a faculty in the rail** → table filters. Footer chip "Showing N of M — clear filter ×" appears.
10. **Click Clear button** → file pickers, banner, log, table, rail, filter all reset. **No more Tk error.**
11. **Drag window edge** to resize → smooth, no stuttering.

---

## Remaining items (nothing blocking)

- **Mailer FROM** — gmail.com still rejected by Resend. Manual `/verify-email` curl works as test-account unblock.
- **Argon2 in Workers** — currently degraded to PBKDF2-100k for pilot.
- **Cross-FS sync defensive script** — bash-mount truncation continues to bite every multi-file dispatch. Worth a defensive automated checker.
- **M4 (admin dashboard, invoicing, credits)** — paused since Round 6.
- **M8 — Camps Reconciliation** — blocked on sample exports.
