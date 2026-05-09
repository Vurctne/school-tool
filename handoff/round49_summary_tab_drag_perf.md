# Round 49 — Summary tab + drag perf

**Date:** 2026-05-09
**Trigger:** User: "continue to optimize the window dragging speed
and complete the work as you suggested"
**Scope:** Two parts — (1) the deferred Phase B.3 Summary tab from
Round 48's handoff (the "actually basic basic report" the user
asked for), and (2) one additional drag-speed optimization.

---

## Part 1 — Summary tab

Now the first tab when a Sub-Program report finishes. A two-column
read-down card; renders as a borderless table that reads like a
narrative.

### Content rendered

```
Period            April 2026
Sub-programs      47 across 9 faculties
Spent so far      32% of annual budget
Spending pace     +4% (slightly ahead)

Need attention    5 sub-programs need attention
  IT general      Over budget by $18,000
  Library books   Over budget by $8,400
  Welfare         Over budget by $4,640
  Sport equipment Spending too fast
  Music           Spending too fast
```

When the watchlist is empty: `Need attention · All clear — no
sub-programs flagged`.

When more than 5 lines: shows top 5 by `abs(variance_amount)` plus
`+ N more (see Watchlist tab)`.

### Pace phrasing

`pace_phrase` is built from `macro_pacing` (Σ used_pct ÷ Σ
calendar_pct), with adjective banding rather than the raw multiplier:

| `macro_pacing` | Phrase |
|---|---|
| `0` (period not parseable) | `Unknown (period not detected)` |
| within 0.5% of 1.0 | `On track` |
| 0–10% over | `+4% (slightly ahead)` |
| ≥10% over | `+15% (well ahead)` |
| 0–10% under | `−4% (slightly behind)` |
| ≥10% under | `−15% (well behind)` |

Same banding logic as the Pacing metric card from Round 48, just
expanded into sentences.

### Where it sits in the tab order

| Index | Tab | Audience |
|---|---|---|
| 0 | Summary | Non-finance reader, default view |
| 1 | Watchlist (n) | Power user, prioritised work list |
| 2 | Revenue (n) | Power user, full detail |
| 3 | Expense (n) | Power user, full detail |
| 4 | Combined | Power user, YTD net per sub-program |

### What this is NOT

- A new shell primitive — uses the existing `TableSpec` /
  `_SUMMARY_COLUMNS` mechanism with no shell-side changes.
- A live narrative — content is rebuilt on every `_build_result`
  call, including threshold-slider previews.

---

## Part 2 — Drag-speed optimization

The drag pipeline has been optimized over many rounds (14, 22d, 23,
43). Round 43 added the per-canvas `_latest_drag_width` holder so
each canvas only does work once at drag-end. Round 49 closes one
remaining mid-drag gap:

**Before:** the inner-frame's `<Configure>` handler scheduled a
debounced 100ms scrollregion update on every Configure event, even
while `_drag_active` was True. Most of those got cancelled by the
next Configure, but the last one fired ~100ms into the drag-settle
window.

**Now:** during an active drag, `_on_inner_configure` skips the
debounced scheduling entirely and registers `_do_inner_configure`
as a flush hook on `_pending_canvas_configures`. The drag-settle
callback fires it once at drag end, alongside all the other
deferred canvas configures.

Net effect: one fewer ~100ms `after()` round-trip during drag.
Small in absolute terms; consistent with the drag-pipeline
architecture established in Round 43.

For further drag-speed gains beyond this, the only remaining
levers are (a) Treeview replacement with a Canvas-based table
(architectural change, several rounds of work), or (b) Tk
build-time optimizations outside the codebase. Neither
proportionate to the perceived improvement at this point.

---

## Files touched

| File | Change |
|---|---|
| `tools/sub_program/frame.py` | New `_SUMMARY_COLUMNS`. Summary build (pace banding + watchlist top-5) inserted before `table_tabs`. Summary prepended as the first tab. |
| `toolkit/shell.py` | `_on_inner_configure` defers scrollregion update to drag-settle when `_drag_active`. |
| `tools/sub_program/tests/test_frame.py` | Renamed `test_result_has_four_tabs` → `test_result_has_five_tabs` (asserts Summary is index 0, Watchlist is 1). Index bumps in 4 tab tests. |
| `app_metadata.py` | `APP_VERSION` 2.2.7.0 → 2.2.8.0 |
| `CHANGELOG.md` | New v2.2.8.0 section. |

---

## Quality gates

```
ruff format --check .                  # 79/79 ok (one auto-format applied)
ruff check .                           # All checks passed!
mypy --strict (--cache-dir=/tmp/...)   # 79 source files, no issues
pytest -q --ignore=tools/operating/... # 507 passed, 66 env-only skips
                                       # (sub_program: 128/128)
```

---

## Carried over (still pending)

Same as Round 47/48:

- Revenue under-collection signal (Phase B.2).
- Pacing direction inversion for Revenue (Phase B.2).
- Faculty rail bar tone for contribution-pct values (Phase B.2).
- Variance + Pacing columns in XLSX (decision needed).
- Conditional formatting / data bars on the monthly XLSX sheet.
- School-name extraction for print header.
- ~25 P0 tests proposed by Round 47 Agent D.

---

## Status

- Code changes in.
- 507 tests pass (66 env-only skips). 128/128 in sub_program.
- `APP_VERSION = "2.2.8.0"`. Ready for `pwsh
  msix\build_msix_package.ps1 -StoreUpload` on Windows.
- Task #67 → completed.
