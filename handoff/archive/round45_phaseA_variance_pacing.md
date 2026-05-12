# Round 45 Phase A — Variance + Pacing columns, dollar materiality

**Date:** 2026-05-09
**Trigger:** User: "I love this interface and visual, start phase A
and can we make the whole shell and tool this style?"
**Scope:** Phase A only (data model + columns + materiality + metric
strip on Sub-Program). Phase A.5 (apply the visual style across the
whole shell within Tkinter's constraints) deferred to its own round.

---

## What ships

### 1. Three new fields on `SubProgramLine`

```python
variance_amount: Decimal   # signed YTD - Budget
variance_pct:    Decimal   # variance_amount / budget * 100, signed
pacing:          Decimal   # used_pct / calendar_pct, multiplier (0 if unknown)
is_material:     bool      # |variance_amount| >= materiality_dollar
```

Variance carries one sign convention (`YTD - Budget`); the UI does
account-aware tinting at render time so an Expense over-spend reads
red while a Revenue under-collect reads amber.

### 2. Calendar-position derivation

`calendar_pct_from_period_label()` parses the GL21157 footer date
("April 2026" → 4/12 → 33.33). When the period label is missing or
unrecognisable it returns 0.0, which the formatter renders as an
em-dash so the user sees "pacing unknown" rather than a misleading
"0.00".

The denominator is **calendar year** (Jan-Dec, 12 months) because
CASES21 budgets themselves are struck on a calendar year — the
"Annual budget" column in the export proves it. Don't flip this to
a Vic school year (Feb-Dec) without a clear request from the field.

### 3. New input — `materiality_dollar`

`NumberInput(default=5000)` slotted directly under the two
threshold sliders. Lines whose `|variance_amount| >= materiality`
flag `is_material=True`; lines below the floor still flag pink when
they exceed the percentage threshold but render with `FG_2` (muted)
foreground instead of `DANGER_FG`. Stops the "$50 over a $30
stationery budget" rows from competing with "$18,000 over the IT
budget" rows.

### 4. Headline-column swap

`_TABLE_COLUMNS` in `tools/sub_program/frame.py`:

| Was | Now |
|---|---|
| Sub-program · Account · Description · Budget · YTD · Remaining · Used % | Sub-program · Account · Description · Budget · YTD · **Variance $** · **Var %** · **Pacing** |

`Used %` is still computed on the dataclass and still goes to the
XLSX export — only the in-app headline display loses it.

### 5. Metric-card strip

`ToolResult.metrics` populated with four cards:

| Card | Tone |
|---|---|
| Sub-programs · `n` · `f` fac | neutral |
| YTD spend · `xx%` | neutral |
| Pacing · `1.04` | ok / warn / danger (1.00 / 1.10 thresholds) |
| Watchlist · `n` | ok if 0 else danger |

The shell already supports `result.metrics` via
`toolkit.primitives.Metric` (label / big mono number / tone) —
zero shell-level changes were needed. Verified at `toolkit/shell.py`
lines ~2176-2196.

### 6. Two formatters added in `frame.py`

```python
_fmt_signed_dollar(Decimal) -> str   # "+$18,000" / "−$2,100" / "$0"
_fmt_signed_pct(Decimal)    -> str   # "+45.0%"   / "−12.3%"  / "0.0%"
_fmt_pacing(Decimal)        -> str   # "1.04"     / "—"  (em-dash for unknown)
```

Uses U+2212 minus per the design-handoff numerics contract — not
the ASCII hyphen.

---

## Files touched

| File | Change |
|---|---|
| `toolkit/base_tool.py` | Added `NumberInput.default: float \| None = None` field |
| `toolkit/shell.py` | NumberField pre-fill: cache hit → `inp.default` → `""` |
| `tools/sub_program/logic.py` | Added 4 fields to `SubProgramLine` (variance/pacing/material), 2 fields to `ReportSummary` (calendar_pct/materiality_dollar). New `calendar_pct_from_period_label()`. Extended `_recompute_is_over` to compute variance/pacing/materiality. New `materiality_dollar` keyword on `generate_report` |
| `tools/sub_program/frame.py` | Added `materiality_dollar` to `inputs[]`. Swapped table columns. Three new formatters. Metric-card strip. `_row_style` mutes below-floor pink rows. Cache state for materiality + calendar_pct. Live preview path passes them through |
| `tools/sub_program/tests/test_frame.py` | Updated 3 tests for renamed inputs count and new column keys |
| `app_metadata.py` | `APP_VERSION` 2.2.3.0 → 2.2.4.0 |
| `CHANGELOG.md` | New v2.2.4.0 section above v2.2.3.0 |

---

## Quality gates

```
ruff format --check .                    # 79 files already formatted
ruff check .                             # All checks passed!
mypy --strict (--cache-dir=/tmp/mypy_cache)  # 79 source files, no issues
pytest -q --ignore=tools/operating/tests # 507 passed, 66 env-only skips
```

The 9 failures in `tools/operating/tests/test_logic.py` are
pre-existing and unchanged — sample-PDF filename mismatch in parked
code. Tracked under Round 39 audit follow-ups.

---

## Sandbox truncation incidents (info only)

The cross-FS sync truncation hit four files this round, each
recovered via the standard pattern (read full content from Windows
view → `head -n N > /tmp/head.py` → write tail via heredoc → cat
both → AST-parse → `cp` over the bash mount → `touch`):

- `tools/sub_program/logic.py` (truncated at line 1287, 49258 B)
- `tools/sub_program/frame.py` (truncated at line 1099, 46130 B)
- `toolkit/base_tool.py` (truncated at line 287, 10934 B)
- `toolkit/shell.py` (truncated at line 2758, 115141 B)
- `tools/sub_program/tests/test_frame.py` (truncated at line 1235)

Stale `.pyc` files masked one of these recoveries until tests were
re-run with `PYTHONDONTWRITEBYTECODE=1 python3 -B`. Worth keeping in
mind: when bash sees a truncated file but pytest reports
inconsistent results, suspect cached bytecode and disable it
explicitly. (CLAUDE.md gotchas section lists the deletion blocker
for `__pycache__` folders.)

---

## What Phase A does NOT include (deferred)

- **Watchlist tab** — the new fourth tab in the Sub-Program tabs
  row. Move #2 in the redesign brief. Phase B.
- **Bridge waterfall view** — replaces today's Combined tab.
  Move #3. Phase C.
- **Structured commentary** (Driver / Outlook / Action pills).
  Move #5. Phase C.
- **Faculty rail keyed by contribution-to-variance** instead of
  used %. Move #6. Phase B.
- **Shell-wide visual style refresh** ("can we make the whole
  shell this style"). The metric-card strip on Sub-Program is the
  first beachhead — same primitive will roll out to HYIA, Master
  Budget Compass, Refined PAL Search, SRP in Phase A.5.

The redesign brief at `handoff/round44_subprogram_redesign_brief.md`
has the full phasing.

---

## Carried over

- Operating Statement test fixtures (rename / glob `... Detailed Feb.pdf`).
- Partner Center "Support contact info" → `contact@schooltool.com.au`.
- 4 open questions in the redesign brief — period-label parsing,
  multi-period scope, freeform-commentary migration path,
  materiality default of $5k / 1%.

---

## Status

- Code changes in.
- 507 tests pass (66 env-only skips).
- `APP_VERSION = "2.2.4.0"`. Ready for `pwsh
  msix\build_msix_package.ps1 -StoreUpload` on Windows.
- Task #63 → completed (after this write).
