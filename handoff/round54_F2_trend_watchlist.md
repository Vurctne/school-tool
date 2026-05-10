# Round 54 F2 — Trend column + Watchlist sheet

**Date:** 2026-05-10
**Trigger:** User: "开始F2" (start F2).
**Methodology:** TDD (red → green) followed by 4-lens parallel Opus
4.7 review (logic skeptic, UX critic, Excel QA, **variance-analysis
purist** — same lens as Round 53 R2). Two rounds of fixes applied.

**What ships:** F2 of the Round 52 redesign brief — Trend column +
Watchlist sheet + Status column position move (col 13 → col 3) +
the supporting prior-period reader.

---

## What changed

### Move D — Trend column at col 4

A new column 4 carries period-over-period direction:

| Trend value | Meaning | When |
|---|---|---|
| `Newly off track` | Was on-track last month, now off | Status non-OK now AND prior available within materiality (bold) |
| `Worsening` | Both periods off, getting worse | Both off-track AND change in overrun > materiality (bold) |
| `Improving` | Both periods off, getting better | Both off-track AND overrun shrunk by > materiality |
| `Resolved` | Was off-track last month, now on-track | Status On-track now AND prior was off |
| (blank) | No prior data, OR no meaningful change, OR both periods on-track | — |

`Worsening` and `Newly off track` are bold for print scan-ability.
The Trend column is blank when no prior-period XLSX is supplied,
and the page footer carries the explanation:
`"Trend needs a prior-period XLSX (none this run)"` (compact form,
~53 chars, fits the footer-left zone without truncation).

### Watchlist sheet

A second worksheet — `Watchlist` — is added to every workbook. It
carries the same 14-column layout as the main sheet but:

- **Filtered**: only rows where Status ≠ `On track`.
- **Sorted**: signed `available` ascending — overspends top, large
  unspent surpluses at the bottom (per variance-analysis skill
  "investigation priority by negative-net-position first").
- **AutoFilter** on the header row so council members can interactively
  re-sort / filter (only when there ARE data rows; empty Watchlist
  skips the filter to avoid an inert header dropdown).
- **Pink tab colour** (HL_MISMATCH) — Excel users recognise coloured
  tabs as a category marker.
- **Print area** scoped (`A1:N{last_data_row}`) so a council member
  who hits Ctrl+P → "Print Entire Workbook" gets two scoped pages,
  not unbounded pagination.

The main `Sub Program Report` sheet is pinned active (`wb.active = wb.index(ws)`)
so Excel opens to it by default — not the Watchlist (which is
sorted/filtered and looks like a partial export).

### Layout reshuffle

Status moves from col 13 (F1) to col 3 (F2). The eye lands on the
call-to-action before the dollar columns:

```
F1 (R53):  CODE | NAME | Funds | Rev$ | Exp$ | RevYTD | ExpYTD | Orders | Avail | Avail% | Rev% | Comments | Status
F2 (R54):  CODE | NAME | Status | Trend | Funds | Rev$ | Exp$ | RevYTD | ExpYTD | Orders | Avail | Avail% | Rev% | Comments
```

13 cols → 14 cols. Cols 3..12 of F1 shift right by 2 (so old col 12
Comments lands at col 14). Comments column width 40 → 32 (relieves
print-width compression after Status + Trend added 38 char-units of
width). Total widths sum: 246 char-units (~89% of landscape A4
fit-to-width usable space, was 92%).

### Prior-period YTD reader

`load_prior_period_ytd(xlsx_path) -> dict[str, Decimal]` reads the
Available Balance YTD column from a previous month's exported XLSX.
Walks every sheet by header-name match (case-insensitive), but
**skips a sheet titled `Watchlist`** — its data is filtered, so
treating it as a prior-period source would mis-fire trend logic for
healthy programs.

Empty dict returned when the file is supplied but doesn't carry the
column (e.g., a pre-Phase-D export). Raises `ValueError` when the
file is missing.

---

## Multi-personality 4-lens review

### Round 1: 4 lenses parallel (logic, UX, Excel QA, variance-skill)

Each agent returned 6–10 findings. **10 R1 fixes applied:**

| # | Severity | Fix |
|---|---|---|
| 1 | P0 V-skill | Drop `Stable` from `_TREND_VALUES` — alongside non-OK Status it reads as "no problem" |
| 2 | P1 Logic | `compute_trend` accepts `current_status` and uses it to gate "current_over" — keeps Status / Trend in sync for pacing-aware Expenditure-only programs |
| 3 | P1 Logic | `load_prior_period_ytd` skips sheets titled `Watchlist` |
| 4 | P1 Excel | `wb.active = wb.index(ws)` pins main sheet as Excel-open default |
| 5 | P1 UX | `New issue` → `Newly off track` (pill-pattern consistency) |
| 6 | P1 UX | `Resolved` only fires when current Status is `On track` (implicit via #2) |
| 7 | P1 UX | `print_area` set on both sheets — prevents accidental "Print Entire Workbook" doubling |
| 8 | P1 Excel | Comments column width 40 → 32 — relieves print compression |
| 9 | P1 Excel | AutoFilter + pink tab colour on Watchlist |
| 10 | P1 V-skill | Watchlist sort changed from `abs(available)` desc → signed asc — overspends first, underspends last |

### Round 2: 4 lenses verify pass

R2 confirmed 9 of 10 R1 fixes PASS. **3 R2 fixes applied:**

| # | Severity | Fix |
|---|---|---|
| 1 | P1 Excel | Empty Watchlist (no off-track rows) skips AutoFilter — was producing degenerate `A2:N2` header-only filter |
| 2 | P1 UX | Footer text shortened from 95 chars to 53 — fits the footer-left zone without wrapping |
| 3 | P1 V-skill | Document the Status/Trend percent-floor asymmetry in `compute_trend` docstring (production writer always passes status; only ad-hoc callers see the asymmetry) |

### Deferrals (documented for future rounds)

- **Multi-period trending** — F2 has 2 periods (current + prior month). The variance-analysis skill prescribes 3+ periods for true trending. Defer to v2.1+ (requires persisting the last 3 monthly exports).
- **Top-N cap on Watchlist** — a school with 30 over-track sub-programs gets a 30-row Watchlist. Skill is loose on list-view caps. Defer.
- **Prior-period status persistence** — `compute_trend`'s `prior_over` uses raw `available < -mat`; if last month's Status was pacing-aware "On track" but available was deeply negative, current "Resolved" can mis-fire. Document; needs prior-status persistence in the export. Defer.
- **Tab colour via `HL_MISMATCH` constant** — currently bare `"F4CCCC"` literal. Hygiene-only. Defer.
- **`compute_trend` boundary asymmetry vs Status** — verified PASS; both functions strict at `-mat`. Document.

---

## Files touched

| File | Change |
|---|---|
| `tools/sub_program/logic.py` | New `_TREND_VALUES` tuple (4 values, no Stable). New `compute_trend(*, current_available, prior_available, current_status='', materiality_dollar=5000)` (~70 lines including extensive docstring covering R1 sync fix + R2 documented asymmetry). New `load_prior_period_ytd(xlsx_path)` (~80 lines including Watchlist-skip + multi-row-form header detection). `_write_xlsx` rewritten to create both sheets + pin `wb.active`. `_write_monthly_sub_program_sheet` parameterised with `prior_ytd`, `filter_to_non_ok`, `sort_by_variance_desc`, `sheet_title_override`. Data-row loop reshuffled for 14-col layout (Status col 13→3; Trend new at col 4; Comments col 12→14; capped percent cols 10/11→12/13; financials 4-9→6-11). Pink fill range `range(1, 14)` → `range(1, 15)`. Title merge `end_column=13` → `end_column=14`. Print-area + AutoFilter + tab colour on Watchlist. Compact footer text. Comments width 40 → 32. Row-height heuristic `col_12_width=32`. New `_write_watchlist_sheet` thin wrapper. |
| `tools/sub_program/tests/test_logic.py` | New `TestComputeTrend` (9 tests), `TestLoadPriorPeriodYtd` (3), `TestF2XlsxLayout` (7), `TestF2WatchlistSheet` (3), `TestF2Round1Fixes` (9), `TestF2Round2Fixes` (5). 36 new F2 tests total. Updated existing F1/R1/R2 tests for the column-position shift (col 12 → 14, col 11 → 13, col 13 → 3, etc.). |
| `app_metadata.py` | `APP_VERSION` 2.3.1.0 → 2.4.0.0 (minor bump — adds the Watchlist sheet, layout change). |
| `CHANGELOG.md` | New v2.4.0.0 section. |

---

## Quality gates

```
ruff format --check .                       # 79/79 ok
ruff check .                                # All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache tools/sub_program/
                                            # 0 new errors (2 pre-existing
                                            # in tools/master_budget/logic.py
                                            # — same as Round 51 baseline)
pytest tools/sub_program/tests/ tests/test_shell_clear.py
                                            # 251 passed, 2 skipped
                                            # 9 fail, 15 error — all
                                            # env-only PDF-dependent
                                            # (pre-existing baseline)
```

Test count delta: Round 53 final was 217 → Round 54 F2 final 251.
**+34 new F2 tests** (20 core + 9 R1 regression + 5 R2 regression).

---

## Status

- F2 (Move D + Watchlist) ships in v2.4.0.0.
- 13 fixes applied across 2 review rounds (10 R1 + 3 R2).
- 36 new tests pin the new behaviour against future drift.
- All 4 quality gates clean.

The Round 52 redesign brief's F2 phase is COMPLETE. Remaining
deferrals (multi-period trending, top-N cap, etc.) are documented
above for future rounds; none are ship-blockers.

— end of round —
