# Round 48 — Plain-English labels for non-finance users

**Date:** 2026-05-09
**Trigger:** User: "another problem is that most of my users do not
have finance background, so the basic report needs to be simple
and can be easily understood."
**Scope:** Re-language the Sub-Program Budget Report so a school
business officer with no formal finance training reads every label
correctly on first try. Code-light, copy-heavy.

---

## What shipped

| Surface | Was | Now |
|---|---|---|
| Pacing column header | `Pacing` | `Spending pace` |
| Pacing values | `1.04`, `2.41`, `—` | `+4%`, `+141%`, `On track`, `Unknown` |
| Watchlist Why column header | `Why` | `Issue` |
| Watchlist trigger label (both) | `Over budget + pace` | `Over budget; spending too fast` |
| Watchlist trigger label (pace only) | `Ahead of pace` | `Spending too fast` |
| Materiality input label | `Materiality threshold ($)` | `Ignore amounts under ($)` |
| Pacing metric card value | `1.04` (sub: "slight ahead") | `+4%` (sub: "slight ahead") |

The signed `Variance $` (+$18,000 / −$5,000) and `Var %` columns
were already readable — kept. `Watchlist` is plain English already
— kept.

---

## Why this matters

The variance-analysis lens that produced the redesign brief is
useful for *what to surface*, but its vocabulary ("variance",
"materiality", "pacing as a multiplier") assumes a reader with
formal training. School business officers — especially newer ones
or those who took the role on top of an admin role — read finance
columns the way I read SQL execution plans: it's information, but
the affordances are missing.

The biggest single comprehension uplift was the pacing format:

- `1.04` reads as "one point oh four" with no inherent meaning.
- `+4%` reads as "four percent over" with the direction baked in.

The same logic applies to "Issue" (a question word a non-finance
reader can answer) vs "Why" (which begs a sentence-long
explanation).

---

## Files touched

| File | Change |
|---|---|
| `tools/sub_program/frame.py` | `_fmt_pacing` now returns relative-percent / "On track" / "Unknown". `_TABLE_COLUMNS["pacing"].label` → "Spending pace". `_WATCHLIST_COLUMNS` same + `["why"].label` → "Issue". `_watchlist_why()` text rewritten. Materiality input label updated. Metric strip pacing value uses the new format. |
| `app_metadata.py` | `APP_VERSION` 2.2.6.0 → 2.2.7.0 |
| `CHANGELOG.md` | New v2.2.7.0 section. |

---

## Quality gates

```
ruff format --check .                  # 79/79 ok (one auto-format applied)
ruff check .                           # All checks passed!
mypy --strict (--cache-dir=...)        # 79 source files, no issues
pytest -q --ignore=tools/operating/tests
                                       # 507 passed, 66 env-only skips
                                       # (sub_program: 128/128)
```

---

## What this round did NOT do (deferred to Phase B.3)

The user's broader complaint — "the basic report needs to be
simple and can be easily understood" — points beyond labels at
the **information architecture**. A school business officer who
hasn't run this tool before still lands on a four-tab Notebook with
three numeric columns + a side rail full of percent values. Even
with plain-English labels, that's denser than a first-time user
needs.

**Phase B.3 idea (deferred):** add a **Summary** tab as the new
default first tab. A single read-down narrative card:

```
Sub-Program Budget Report — April 2026

47 sub-programs across 9 faculties.
32% of the annual budget spent so far. Spending is +4% ahead
of plan.

5 sub-programs need attention:
  ▸ IT general — over budget by $18,000
  ▸ Library books — over budget by $8,400
  ▸ Welfare programs — over budget by $4,640
  ▸ Sport equipment — spending too fast
  ▸ Music instruments — spending too fast

[ View full report ]   [ Open in Excel ]
```

That would be the actual "basic report" the user is asking for.
Watchlist / Revenue / Expense / Bridge become the power-user
drill-down. Worth its own round once labels and core columns
settle.

Not building it this round to keep changes scoped — single round =
single concern. Phase B.3 belongs after we've seen the new labels
in user hands and confirmed they read correctly.

---

## Carried over (still pending from Round 47)

- Revenue under-collection signal (Phase B.2).
- Pacing direction inversion for Revenue (Phase B.2).
- Faculty rail bar tone fix (Phase B.2).
- Variance + Pacing columns in XLSX (decision needed: extend
  Kate Marshall's monthly shape vs add a second sheet).
- Conditional formatting / data bars on the monthly sheet.
- School-name extraction for print header.
- ~25 P0 tests proposed by Agent D (will pull in tranches).

---

## Status

- Code changes in.
- 507 tests pass (66 env-only skips).
- `APP_VERSION = "2.2.7.0"`. Ready for `pwsh
  msix\build_msix_package.ps1 -StoreUpload` on Windows.
- Task #66 → completed.
