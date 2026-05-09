# Round 24 — Combined view YTD comparison + drop Budget shape

**Date:** 2026-05-01
**Scope:** Two redesign asks for the Combined tab.

---

## Before / after

**Before (Round 23):**

| Sub-program | Description | Revenue | Expense | Subsidy | Subsidy % | Budget shape |
| --- | --- | --- | --- | --- | --- | --- |
| 4400 | Photography | $4,400 | $23,613 | $19,213 ↓ | 81.4% | ████▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ |
| 1320 | Textiles | $14,000 | $0 | $14,000 ↑ | 100.0% | ··················· |

Issues:
- Numbers were ANNUAL BUDGET only — not what's actually happened YTD.
- "Budget shape" unicode bar was visually noisy at narrow column widths.
- "Subsidy %" overlapped semantically with the Net column.

**After (Round 24):**

| Sub-program | Description | Revenue YTD | Expense YTD | Net YTD | Annual budget net |
| --- | --- | --- | --- | --- | --- |
| 4400 | Photography | $2,200 | $11,806.50 | $9,606.50 ↓ | $19,213.00 ↓ |
| 1320 | Textiles | $7,000 | $0.00 | $7,000.00 ↑ | $14,000.00 ↑ |

Net YTD is the headline.  Annual budget net gives the planned position
for context (is YTD on track for the annual plan, ahead, or behind?).
The unicode bar is gone.

---

## What changed

### `_build_combined_rows` rewrite

- Aggregates Revenue + Expenditure **YTD** per sub-program (in addition
  to budget).
- Computes `Net YTD = Revenue YTD - Expense YTD` per row.
- Computes `Annual budget net = Revenue budget - Expense budget` for the
  context column.
- Returns `(rows, total_ytd_subsidy, total_ytd_surplus)` keyed off
  Net YTD direction (negative = subsidy, positive = surplus).
- Sort: Net YTD ascending → biggest YTD subsidy (most-negative) first,
  biggest YTD surplus last.
- Row tint flags: `_subsidised` when Net YTD < 0, `_surplus` when
  Net YTD > 0.

### `_COMBINED_COLUMNS` simplified

```python
[
    {"key": "sub_program", "label": "Sub-program", "width": 90, "mono": True},
    {"key": "description", "label": "Description"},
    {"key": "revenue_ytd", "label": "Revenue YTD", "width": 110, "align": "right", "mono": True},
    {"key": "expense_ytd", "label": "Expense YTD", "width": 110, "align": "right", "mono": True},
    {"key": "net_ytd", "label": "Net YTD", "width": 120, "align": "right", "mono": True},
    {"key": "net_budget", "label": "Annual budget net", "width": 130, "align": "right", "mono": True},
]
```

Dropped: `subsidy`, `subsidy_pct`, `shape`.

### Direction marker formatter

New `_fmt_signed(value)` helper:
- `value > 0` → `$X.XX ↑` (surplus / over-collecting)
- `value < 0` → `$X.XX ↓` (subsidy / school-funded)
- `value == 0` → `—`

Used for both Net YTD and Annual budget net columns so the same
glyph language carries direction in both.

### Combined tab title

`Combined · YTD subsidy $X · YTD surplus $Y` — now explicitly labels
the totals as YTD-derived (vs annual-budget-derived in pre-Round-24).

### Row tint unchanged from Round 23

- `_subsidised=True` → soft BLUE (`tokens.INFO_BG`)
- `_surplus=True` → soft GREEN (`tokens.HL_SOURCE_ONLY`)

---

## Files touched

```
MOD   tools/sub_program/frame.py
       - _COMBINED_COLUMNS schema (6 cols, dropped 'shape' + 'subsidy_pct')
       - _build_combined_rows YTD-driven + new (rev_b, exp_b, rev_y, exp_y) accumulators
       - new _fmt_signed helper
       - Combined tab title labelled "YTD subsidy" / "YTD surplus"

MOD   tools/sub_program/tests/test_frame.py
       - test_combined_tab_aggregates_per_sub_program rewritten for YTD math
       - test_combined_columns_are_ytd_driven (renamed; checks new keys)
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

---

## What to manually verify on Windows

1. **Combined tab columns** — Sub-program · Description · Revenue YTD ·
   Expense YTD · Net YTD · Annual budget net.  No unicode bar, no
   "Subsidy %" column.
2. **Net YTD** carries the headline number with `↓` (subsidy) or `↑`
   (surplus) direction marker.
3. **Annual budget net** shows the planned full-year position for
   context — useful to compare YTD trajectory against the budget.
4. **Sorting** — biggest YTD subsidy at the top (most negative Net YTD),
   biggest YTD surplus at the bottom.
5. **Row tints** — blue for subsidy rows, green for surplus rows
   (carried over from Round 23).
6. **Tab title** — `Combined · YTD subsidy $X · YTD surplus $Y` when
   totals exist.

---

## Variance-analysis lens (for the curious)

Round 24 turns the Combined tab into a YTD vs Annual budget comparison
at the sub-program level — the same shape as the canonical "Actuals
vs Budget" comparison in `finance:variance-analysis`.  The Net YTD
column is the real-time variance signal; the Annual budget net is the
plan.  Sub-programs where YTD direction disagrees with budget direction
(e.g. budgeted surplus but YTD shows subsidy) are the ones worth
investigating.

A future Round 25 could surface this disagreement explicitly with a
"YTD vs Budget" column that highlights direction flips, but Round 24
keeps the table simple by giving the user both numbers and letting them
eyeball it.
