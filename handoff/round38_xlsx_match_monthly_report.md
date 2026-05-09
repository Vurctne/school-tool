# Round 38 — Sub-Program XLSX output matches Monthly Sub Program Report shape

**Date:** 2026-05-08

---

## User ask

> Sub program report change to this format. … source file is still
> GL21157_Annual Subprogram budget report. output format to match the
> xls file i sent.

The user uploaded `Monthly Sub Program Report April 2026 KMAR.xls` —
their school's own per-sub-program rollup workbook. The PDF source
parser stays the same; only the Excel export reshapes to match.

---

## What changed (output shape)

**Before** — `Annual_SubProgram_<stem>_AUTO_<ts>.xlsx` had **2 (or 3)
sheets**:

* "Revenue" — 8 columns, one row per revenue account-line
* "Expenditure" — 9 columns, one row per expenditure account-line
* (optional) "Combined" — 6 columns, one row per sub-program (Round 26)

**After** — same filename, but **one sheet** named **"Sub Program
Report"** with **12 columns, one row per sub-program**:

| # | Header | Source |
| --- | --- | --- |
| 1 | CODE | `sub_program` (numeric where possible) |
| 2 | PROGRAM NAME | `description` (first non-empty per sub-program) |
| 3 | Funds from Previous Years (Funds) | **blank** — not in PDF |
| 4 | Budget Revenue {year} | sum of `budget` for revenue lines |
| 5 | Total Budget Allocation Expenditure {year} | sum of `budget` for expenditure lines |
| 6 | Revenue YTD | sum of `ytd` for revenue lines |
| 7 | Expenditure YTD | sum of `ytd` for expenditure lines |
| 8 | Less outstanding orders | sum of `outstanding_orders` for expenditure lines |
| 9 | Available Balance YTD | `Revenue YTD − Expenditure YTD − orders` |
| 10 | Available Balance % YTD | `Available / Expenditure budget` (decimal fraction) |
| 11 | Revenue Budget % Received YTD | `Revenue YTD / Revenue budget` (decimal fraction) |
| 12 | Comments | `commentary` (first non-empty per sub-program) |

Title row 1 (merged across 12 cols): `Monthly Sub Program Report — {period}`.
Row 2: bold headers, wrap-text. Rows 3+: data. `freeze_panes = "A3"`.

### Highlight

Pink **HL_MISMATCH** fill across the whole row when **Available
Balance YTD < 0** — the canonical "this sub-program has over-drawn"
indicator. Replaces the prior `is_over` per-line pink fill (which
operated at the account-line level on the old 2-sheet shape).

### About the "Funds from Previous Years" column

The GL21157 PDF doesn't carry rolled-forward surplus/deficit data, so
the column is intentionally **left blank** rather than filled with a
guessed zero. A blank cell signals "not known"; a zero would be a
wrong number in budget review. Schools that need the column populated
can open the file and fill it in manually from their council records.

---

## Files touched

```
MOD   tools/sub_program/logic.py
       - _write_xlsx rewritten — drops the Revenue / Expenditure
         sheet split, calls the new _write_monthly_sub_program_sheet
         instead.  ``include_combined`` and ``over_budget_threshold``
         kwargs accepted for backward-compat with existing call sites
         but no-op for the new shape (the new shape IS the combined
         view).
       - new _write_monthly_sub_program_sheet — full 12-column
         implementation with pink fill on negative-balance rows,
         frozen panes at A3, accounting number format on dollar
         columns, decimal-fraction format on % columns.
       - new _to_int_or_str helper — sub-program codes render as
         integers in Excel (sortable, right-aligned) where the code
         is numeric, fall back to the original string otherwise.

MOD   tools/sub_program/frame.py
       - _export_xlsx no longer pops the Round 26 askyesnocancel
         dialog ("Include Combined sheet?").  The new shape is itself
         the combined view, so the dialog is redundant.

MOD   tools/sub_program/tests/test_logic.py
       - TestGenerateReport.test_output_has_correct_header rewritten
         for the new 12-column shape.
       - TestGenerateReport.test_output_row_count_matches_lines →
         test_output_row_count_matches_unique_subprograms (one row
         per sub-program now, not per account-line).
       - TestGenerateReport.test_pink_fill_on_over_budget_rows /
         test_over_budget_fill_all_columns — converted to one-line
         passing stubs (the new test_pink_fill_on_negative_balance_rows
         covers the new semantic; the old over-budget-per-account
         shape no longer exists).
       - TestXlsxTwoSheets class (13 tests) replaced with a single
         TestXlsxMonthlyReport class verifying the new sheet name +
         12-column header.
       - TestOverBudgetThreshold.test_xlsx_pink_fill_respects_threshold
         stubbed (the per-account threshold no longer drives row
         fills in the new shape; in-app preview still uses it).
```

---

## What stayed the same

* The **PDF source parser** — identical behavior. GL21157 PDFs parse
  the same way they always have.
* `SubProgramLine` dataclass — same 13 fields.
* The in-app **Combined view tab** (Round 24) — same per-sub-program
  YTD comparison the user already sees.
* The **revenue / expense thresholds** sliders — still drive
  `is_over` flags on the in-app per-account table, just no longer
  drive the XLSX row fills.
* The **per-account log lines** showing OVER-BUDGET LINES (these
  remain useful for the user reviewing on-screen).
* Excel **accounting number format** on dollar columns,
  **decimal fraction** format on percentage columns (matches the
  source workbook's convention — e.g. 0.398 in the Available Balance
  % column, not 39.8%).

---

## Quality gates

```
ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 72 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 541 passed, 66 skipped (env)
                           (was 550 — −9 net from removing 13
                            obsolete TestXlsxTwoSheets tests + 1
                            TestOverBudgetThreshold and adding
                            5 new ones)
```

---

## Variance-analysis lens — why this shape is a better deliverable

The new export is the same shape the school's own finance officer
reads at month-end: every sub-program on one row, with the four
columns that drive their conversation:

* **Available Balance YTD** — "where am I right now?" (the headline)
* **Available Balance % YTD** — "how much runway do I have left?"
* **Revenue Budget % Received YTD** — "are we collecting fees on time?"
* **Less outstanding orders** — "what's already committed?"

Materiality threshold for review (per the variance-analysis skill):

| Comparison | Default trigger |
| --- | --- |
| Available Balance YTD < 0 | Hard flag — pink fill across the row |
| Revenue Budget % Received < 50% mid-year | Visible (column 11) — investigate at user's discretion |
| Outstanding orders > Available Balance | Visible — investigate manually |

Future round could add conditional formatting for the % columns
(green/amber/red) — out of scope for this round.

---

## What to manually verify on Windows

1. Run Sub-Program Budget Report against a CASES21 GL21157 PDF.
2. Click **Export to Excel**. No more "Include Combined sheet?"
   dialog — file saves immediately.
3. Open the saved XLSX. **Single sheet**, name "Sub Program Report".
4. Title row (row 1): `Monthly Sub Program Report — {period}`.
5. Header row (row 2): 12 bold columns starting `CODE | PROGRAM NAME
   | Funds from Previous Years | Budget Revenue {year} | …`.
6. Data rows: one per sub-program. Pink rows = Available Balance
   YTD < 0.
7. `freeze_panes` works — header stays visible while scrolling.
8. Numeric cells format as `$N,NNN`; % columns format as `0.65`
   (decimal fraction, matching the source workbook's convention).

---

## Roll into v2.2.2.0 hotfix or hold for v2.2.3.0?

This is a non-trivial output-shape change. Two options:

**A) Bundle into v2.2.2.0 hotfix (already in flight)** — same Store
review cycle as the Sub-Program rendering fix + email + privacy
trim. Single submission to Partner Center.

**B) Hold for v2.2.3.0** — ship the v2.2.2.0 hotfix first (gets
Sub-Program rendering working for all current users), then ship
v2.2.3.0 with the new output shape after a few days of feedback.

**Recommendation: option A** — the new shape is more useful than the
old one, and existing users haven't seen any of v2.2.1.0's
Sub-Program output anyway (it didn't render). Shipping the new
shape directly avoids a "downgrade then upgrade" UX.

Patch-notes line for v2.2.2.0:

> • **Excel export reshaped** to match Victorian schools' Monthly
>   Sub Program Report workbook — one row per sub-program, 12
>   columns covering revenue, expenditure, outstanding orders,
>   available balance, and the two key ratios.

---

## Files committed-side

```
MOD   tools/sub_program/logic.py
MOD   tools/sub_program/frame.py
MOD   tools/sub_program/tests/test_logic.py
ADD   handoff/round38_xlsx_match_monthly_report.md
```
