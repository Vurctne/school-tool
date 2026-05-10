# Round 56 — Pacing logic removed; Watchlist narrowed to over-budget

**Date:** 2026-05-10
**Trigger:** User directive (Chinese):

> 1. 移除 watchlist (metric card)
> 2. 移除所有 pacing 计算
> 3. Watchlist 只显示 overbudget
> 4. 图1 (sub-programs card) 不显示 fac

After follow-up `AskUserQuestion` for the Expenditure-only judgement
basis, the user picked option 1: `exp_ytd > expense_threshold% ×
annual_exp_budget`. Spent-without-budget rows still go on Watchlist.

---

## What changed

### Logic (`tools/sub_program/logic.py`)

- **`SubProgramLine.pacing`** field removed. The dataclass no longer
  carries the period-over-calendar ratio.
- **`ReportSummary.calendar_pct`** field removed. The summary no longer
  carries the parsed-from-period-label calendar fraction.
- **`calendar_pct_from_period_label()`** + the `_MONTH_TO_PCT` table
  deleted entirely.
- **`compute_status_pill()`** redesigned. New keyword-only signature:

  ```python
  def compute_status_pill(
      *,
      annual_exp_budget: Decimal,
      exp_ytd: Decimal,
      annual_rev_budget: Decimal = Decimal("0"),
      rev_ytd: Decimal = Decimal("0"),
      expense_threshold: float = 101.0,
      materiality_dollar: int = 5000,
  ) -> str:
  ```

  Drops `available` and `calendar_pct`. Logic:
  1. `Spent without budget` — both budgets zero, no revenue, exp_ytd > 0.
  2. Zero exp budget + no spend → `On track`.
  3. Threshold gate: `used_pct = exp_ytd / annual_exp_budget × 100`.
     If `used_pct ≤ expense_threshold` → `On track`.
  4. Overrun bucketed: `>$100K OR >50pp` → Urgent;
     `>$25K OR >25pp` → Significant; else Slightly over.
  5. Hard $500 noise floor, $5K materiality fallback floor.
- **`_STATUS_VALUES`** tuple shrank from 6 → 5 (No spend yet removed).
- **`_recompute_is_over()`** lost its `calendar_pct` parameter and the
  pacing computation.
- **`_write_monthly_sub_program_sheet()`** now calls `compute_status_pill`
  with the new signature; auto-fill no longer special-cases the
  No-spend-yet pill.
- **`generate_report()`** no longer extracts calendar_pct or carries
  it on the returned `ReportSummary`.

### Frame (`tools/sub_program/frame.py`)

- **Pacing column** dropped from `_TABLE_COLUMNS` and
  `_WATCHLIST_COLUMNS`.
- **`_PACING_WATCH_THRESHOLD`** constant removed.
- **`_fmt_pacing()`** function removed.
- **`_watchlist_why()`** simplified — only over-budget triggers.
- **Watchlist filter** changed from
  `(is_over and is_material) or pacing >= _PACING_WATCH_THRESHOLD`
  to `is_over and is_material`.
- **Pacing card** removed from `metric_cards`.
- **Watchlist card** removed from `metric_cards` (Watchlist count is
  already in the tab label, e.g. "Watchlist (3)").
- **Sub-programs card** no longer carries the faculty count
  (`f"{n_lines} · {n_faculties} fac"` → `f"{n_lines}"`).
- **`_cached_calendar_pct`** class attribute + the assignment in
  `run()` + the parameter in the `preview_update()` call to
  `_recompute_is_over` removed.
- Pacing references in row dicts (data rows + comment sub-rows +
  watchlist rows) removed.

### Tests

- **`test_logic.py`** — `TestStatusPill` rewritten end-to-end for the
  new contract (drops `available=`/`calendar_pct=` from every call
  site); boundary tests rewritten with threshold-based scenarios; the
  No-spend-yet xlsx tests rewritten to expect `On track` for budgeted-
  no-spend; `test_watchlist_sort_separates_underspend_from_overspend`
  renamed to `test_watchlist_excludes_unspent_programs` and rewritten
  to assert the unspent row is absent from the Watchlist (Round 56
  narrows the Watchlist to over-budget only).
- **`test_frame.py`** — table_columns assertion drops the `pacing` key;
  comment-sub-row test drops the `assert sub_row["pacing"] == ""`
  check.
- **`test_output_has_correct_header`** — pre-existing test was pinned
  to the legacy 12-column header from before Round 49 (Status) +
  Round 54 (Trend) added their columns. Updated to match the current
  14-column layout (Status at col 3, Trend at col 4).

### Files touched

| File | Change |
|---|---|
| `tools/sub_program/logic.py` | Drop pacing field, calendar_pct, calendar_pct_from_period_label, _MONTH_TO_PCT. Redesign compute_status_pill (new threshold contract). Drop No-spend-yet pill. Update _recompute_is_over, generate_report, _write_monthly_sub_program_sheet. |
| `tools/sub_program/frame.py` | Drop pacing column, _PACING_WATCH_THRESHOLD, _fmt_pacing. Simplify _watchlist_why. Watchlist filter strict to over-budget. Drop Pacing + Watchlist cards. Drop faculty suffix from Sub-programs card. Drop _cached_calendar_pct + related plumbing. |
| `tools/sub_program/tests/test_logic.py` | Rewrite TestStatusPill (10 tests), TestF1Round1Fixes (3 tests), TestF1Round2Fixes (5 tests), boundary tests (5 tests). Update test_xlsx_status_no_spend_yet → On track. Rename watchlist sort test. Fix test_output_has_correct_header for 14-col layout. |
| `tools/sub_program/tests/test_frame.py` | Drop pacing from table_columns assertion + comment-sub-row test. |
| `app_metadata.py` | `APP_VERSION` 2.4.11.0 → 2.4.12.0 (BUILD increment). |
| `CHANGELOG.md` | New v2.4.12.0 section. |

---

## Quality gates

```
ruff format --check .                       # 79/79 clean
ruff check .                                # All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache tools/sub_program/ toolkit/
                                            # 0 new errors
                                            # 4 pre-existing in
                                            # tools/master_budget/logic.py,
                                            # toolkit/crypto_win.py,
                                            # toolkit/updates.py
pytest tools/sub_program/tests/ tests/test_tokens_drift.py tests/test_user_errors.py
                                            # 294 passed
```

Sub-program test count: Round 55 → 269; Round 56 → 269 (same — the No-
spend-yet tests rewrote in place; one watchlist test renamed; one
header test updated). The full test suite (`pytest tools/sub_program/
tests/ tests/`) passes 458 / fails 9 — the 9 failures are pre-existing
Tk init errors on this Windows box, not Round 56 regressions.

---

## Behaviour change at the user-visible level

| Scenario | Pre-R56 (with pacing) | R56 (threshold only) |
|---|---|---|
| $50K budget, $0 YTD, April (33% calendar) | `No spend yet` (calendar > 25%, budget allocated) | `On track` |
| $10K Curriculum exp, $3.5K YTD, April | `On track` (within ±15% pacing band of 33%) | `On track` (within 101% threshold) |
| $100K Curriculum exp, $11K past 101% threshold | (depended on pacing band; could land Slightly over or On track) | `Slightly over` (always) |
| $582K Admin exp, $192K YTD + $1.7M outstanding orders | `Investigate urgently` (committed pace = 3.3×) | `On track` (192K well under 588K threshold) |
| $0 budget on both sides, $X spent, no revenue | `Spent without budget` | `Spent without budget` (unchanged) |

The Admin-style "$1.7M unfunded orders" case is the most material
regression in surfaceable behaviour: the new contract trusts YTD spend
only; outstanding orders (commitments) are no longer factored into the
pill. Mitigation: schools tracking that scenario would still see the
Variance $ column tip past zero only when the orders convert to spend.

---

## Future / next round

Per the user's earlier note: `excel 里面需要有公式显示计算逻辑` — make
the XLSX cells use Excel formulas (e.g. `=H3-G3` for variance) instead
of pre-computed numeric values, so a school auditor can see how each
number is derived. Substantial writer change, deferred.

---

## Status

- All pacing computation removed from the codebase.
- Watchlist narrowed to over-budget rows only.
- Sub-programs card no longer shows the faculty count.
- Pacing column + Pacing card + Watchlist card all gone from the in-app
  view.
- 294 tests pass; ruff format + ruff check clean; 0 new mypy errors.
- 2.4.12.0 ready for `pwsh msix\build_msix_package.ps1 -StoreUpload`.

— end of round —
