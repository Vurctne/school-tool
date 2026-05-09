# Round 46 Phase B — Watchlist tab + rail-by-contribution

**Date:** 2026-05-09
**Trigger:** User: "other tools have different source file and
function, don't apply the same metric. Star phase b"
**Scope:** Phase B from the redesign brief — moves #2 (Watchlist
tab) and #6 (faculty rail keyed by contribution-to-variance).
Phase A.5 (visual-style refresh across other tools) deferred and
deliberately NOT generic — feedback memory recorded.

---

## What ships

### 1. Watchlist tab — new first tab

A new entry at the top of `table_tabs`. A line lands on the
Watchlist if either:

- `is_over AND is_material` — over budget AND above the dollar
  materiality floor (default $5,000); or
- `pacing >= 1.10` — at least 10% ahead of calendar.

Sort: `abs(variance_amount)` descending so the dollar-largest
concerns bubble to the top.

New **Why** column on the right names which trigger fired:

| Why text | Meaning |
|---|---|
| `Over $ + pace` | Both triggers fired — biggest priority |
| `Over $` | Material dollar overspend, but on calendar |
| `Pace` | Ahead of pace, not yet over budget — early warning |

Tab label includes the row count: `Watchlist (5)`. Empty Watchlist
shows `Watchlist (0)` rather than hiding the tab — user still gets
the click target and the count is itself reassuring.

### 2. Faculty rail by contribution-to-variance

Replaced the old "used %" badge with each faculty's share of total
dollar variance:

```
contribution[fac] = Σ |variance_amount|_fac
                  ÷ Σ |variance_amount|_all_faculties × 100
```

Sort: contribution descending — biggest-impact faculties at the
top. "Unknown" still tiebreaks last when contributions match.

Rail data-bar tint (green / amber / red bands from
`SelectableList`) stays the same; just re-keyed to contribution
magnitude rather than used %.

### 3. Watchlist sort + label live-updates with the threshold sliders

Because the Watchlist criteria depend on `is_over`, `is_material`,
and `pacing`, all three of which `_recompute_is_over` already
refreshes during slider drag, the existing `preview_update` flow
re-emits a new ToolResult and the Watchlist tab automatically
re-sorts and re-counts. No new live-preview wiring.

---

## Files touched

| File | Change |
|---|---|
| `tools/sub_program/frame.py` | New `_WATCHLIST_COLUMNS` constant. New `_PACING_WATCH_THRESHOLD = 1.10` module constant. New `_watchlist_why()` helper. Faculty rail loop replaced: contribution-to-variance computation + descending sort. Watchlist tab built and inserted at index 0 of `table_tabs`. |
| `tools/sub_program/tests/test_frame.py` | Renamed `test_result_has_three_tabs` → `test_result_has_four_tabs` (and asserts Watchlist is index 0). Index bumps in 4 tab tests: Revenue 0→1, Expense 1→2, Combined 2→3 (twice). |
| `app_metadata.py` | `APP_VERSION` 2.2.4.0 → 2.2.5.0 |
| `CHANGELOG.md` | New v2.2.5.0 section above v2.2.4.0 |

---

## Quality gates

```
ruff format    # 79/79 ok (one auto-format applied to frame.py)
ruff check     # All checks passed!
mypy --strict  # 79 source files, no issues
pytest         # 507 passed, 66 env-only skips
              # (sub_program: 128/128)
```

---

## Sandbox truncation incidents (info only)

This round hit two truncations, both recovered via the standard
head-cut + heredoc-tail + AST-check + `cp` over pattern:

- `tools/sub_program/frame.py` truncated at line 1260 mid
  `_open_output_folder` after the rail + Watchlist edits — entire
  back half of the file (output folder, inline comment editor,
  refresh, `clear`, `_merge_commentary_overrides`) was missing.
  Recovered to 1457 lines.
- `tools/sub_program/tests/test_frame.py` truncated at line 1242
  mid-string in `test_combined_tab_surplus_when_revenue_covers_expense`.
  Recovered to 1255 lines.

Pattern is now well-rehearsed; each recovery takes one bash call.

---

## What Phase B does NOT include (deferred)

- **"Newly off-track" + "Deteriorating" Watchlist triggers**
  (move #2.4 + #2.5 in the redesign brief). Both need a prior-
  period **report** file (current commentary file is comments-
  only). Wiring that's its own round — call it Phase B.2.
- **Bridge waterfall view** — replaces today's Combined tab.
  Move #3. Phase C.
- **Structured commentary** (Driver / Outlook / Action pills).
  Move #5. Phase C.
- **Visual-style refresh across other tools** — explicitly
  deferred per user feedback "other tools have different source
  file and function, don't apply the same metric." Memory note
  saved at `feedback_per_tool_metric_strip.md`.

---

## Carried over

- Operating Statement test fixtures (rename / glob `... Detailed Feb.pdf`).
- Partner Center "Support contact info" → `contact@schooltool.com.au`.
- Phase A's 4 open questions still open (period-label parsing,
  multi-period scope, freeform-commentary migration path,
  materiality default of $5k / 1%).

---

## Status

- Code changes in.
- 507 tests pass (66 env-only skips).
- `APP_VERSION = "2.2.5.0"`. Ready for `pwsh
  msix\build_msix_package.ps1 -StoreUpload` on Windows.
- Task #64 → completed (after this write).
