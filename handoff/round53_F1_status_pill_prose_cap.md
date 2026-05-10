# Round 53 F1 — Status pill, prose commentary, percent cap

**Date:** 2026-05-10
**Trigger:** User: "start and do /tdd with 4 opus agents to test and
optimize."
**Methodology:** Test-driven development (red → green → refactor)
followed by 4-lens parallel Opus 4.7 review (logic, UX, Excel QA,
test coverage), then 12 R1 fixes applied with regression tests.

**What ships:** Round 52's redesign brief F1 phase — three renderer-
only changes to the Sub-Program Budget Report XLSX output, no
schema changes, safe patch on top of v2.3.0.0.

---

## What changed

### Move B — Plain-English Status pill (col 13)

The XLSX gains a new column 13 `Status` whose value is one of six
plain-English pills computed per-sub-program:

| Pill | When | Bold? |
|---|---|---|
| `On track` | Surplus / under-spend / overrun below the materiality dollar floor / Expenditure-only program within ±15% pacing band of calendar | — |
| `Slightly over` | $5K–$25K overrun OR 10–25% of budget | — |
| `Significant overspend` | $25K–$100K overrun OR 25–50% of budget | **bold** |
| `Investigate urgently` | >$100K overrun OR >50% of budget | **bold** |
| `No spend yet` | Budget > $5K AND $0 YTD on both sides AND calendar past 25% | **bold** |
| `Spent without budget` | $0 budget on BOTH sides AND non-zero expenditure YTD (truly unbudgeted capital spend) | **bold** |

The pill is computed from the same `available` value the Available
Balance YTD column carries, so the two columns always tell the same
story. Bolding the four call-for-attention pills makes them stand
out on print before the eye reaches the colour cue.

**R1-fix logic improvements** (caught by the logic-skeptic agent):

- **Expenditure-only sub-programs** (no revenue side) used to misread
  as "Significant overspend" once exp_y ≥ $5K — because the raw
  `available = -exp_y` always reads as deficit. R1 fix: when
  `annual_rev_budget == 0` AND there's a calendar value, compute a
  pacing-aware status (`actual_pace = exp_y / eb`, compare to
  `expected_pace = calendar_pct / 100`, ±15% band → on track).
- **`Spent without budget`** now requires `annual_exp_budget == 0
  AND annual_rev_budget == 0 AND exp_ytd > 0`. Prior gate
  mis-classified fundraising programs (rev_b > 0, exp_b = 0) as
  unbudgeted.

### Move E — Plain-English commentary in the visible cell

The Phase D structured triplet (Driver / Outlook / Action) now
renders as one or two short sentences in the visible Comments cell
instead of the bracketed prefix. Examples:

| Triplet | Cell |
|---|---|
| `Driver: Ongoing, Action: Monitor`, notes "Reviewed by council" | `Ongoing variance. Being monitored. Reviewed by council.` |
| `Action: Investigate`, notes "Cross-check with HOD" | `Needs investigation. Cross-check with HOD.` |
| `Driver: Timing-late, Outlook: Expected to continue`, no notes | `Spend later than planned, expected to continue.` |
| `Action: Update forecast`, notes "Budget needs amending" | `Forecast update needed. Budget needs amending.` |
| All blank | (cell empty) |

Round-trip via prior-period files is preserved for cells written by
Round 51 — `decode_commentary` still parses the `[Driver: …]` prefix
when present. New Round 53+ cells round-trip as Notes-only (the
graceful fallback `decode_commentary` already returns when no
prefix is found).

**R1-fix prose improvements:**

- **Em-dash splice replaced with period+capital** — was `"Ongoing
  variance — being monitored."`, now `"Ongoing variance. Being
  monitored."`. Reads as natural English instead of template output.
- **Contradictory triplet combinations are dropped:**
  - `Structural` + `One-time` outlook → outlook dropped (structural
    means permanent)
  - `One-time` + `Expected to continue` outlook → outlook dropped
  - `Investigating` + `None` action → action dropped (investigating
    IS an action)
- **Auto-fill for empty Comments + non-OK Status** — when Status is
  Urgent / Significant / Spent-without-budget / No-spend-yet AND the
  prose is empty, the cell auto-fills with `(no commentary
  recorded)`. Without this, an Urgent row with blank Comments looks
  like the BM ignored the alert.

### Move F — Percent cap with print-visible marker

Available Balance % YTD (col 10) and Revenue Budget % Received YTD
(col 11) cap at ±999% for display. Without the cap, schools see
values like `2,136%` (Mathematics row in the actual KMAR file from
April 2026) which read as nonsense to a non-finance reader.

**R1-fix print readability:**

- When capped, the cell now renders as a **text marker** (`>999%`
  or `<-999%`) instead of the capped fraction `999.0%`. The marker
  survives print; the original cell-comment tooltip ("Capped from
  2,136.5% for display (Revenue % Received).") is screen-only and
  invisible on the printed copy.
- When NOT capped, the cell stays a fraction with `0.0%` format —
  pre-F1 behaviour preserved for the common case.

### Move B/E/F integration polish

- **Row height** auto-sizes per row based on prose length
  (`row_dimensions[i].height = 15 * visual_lines`). Prevents
  multi-line commentary from clipping on print at the default 15pt.
- **Pink fill range** extended from `range(1, 13)` to `range(1, 14)`
  so the new Status column also takes the row tint on materially-
  over rows. Verified by regression test
  `test_xlsx_pink_fill_extends_to_status_column`.
- **Title row merge** extended from 12 to 13 columns to span the
  new Status column.

---

## Multi-personality 4-lens review

Per the user's preference, four Opus 4.7 sub-agents ran in parallel
after TDD-green:

| Lens | Focus | Top finding |
|---|---|---|
| **Logic skeptic** | Correctness, edge cases | Expenditure-only programs misclassify; "Spent without budget" misfires on fundraising programs; prose contradictions exist |
| **UX critic** (non-finance reader) | Plain-English readability | "Material concern" is jargon; capped percent prints as fake-real `999.0%` value; em-dash prose reads software-y |
| **Excel QA** | Print, layout, file integrity | Row height not set → prose clips; print width compression risks 3pt body font; cell comments don't print |
| **Test coverage auditor** | Regression risk | Pink-fill-on-Status not tested; prose round-trip not pinned; boundary values ($5K/$25K/$100K exact) not pinned |

**12 fixes applied** from the consolidated findings:
1. Rename `Material concern` → `Significant overspend`
2. Pacing-aware compare for Expenditure-only programs
3. Tighten Spent-without-budget gate (require both budgets == 0)
4. Drop conflicting Driver/Outlook combinations
5. Drop conflicting Driver/Action combinations
6. Em-dash → period+capital in prose
7. Capped percent → `>999%` / `<-999%` text marker (print-visible)
8. `row_dimensions[i].height` heuristic for multi-line prose
9. Bold "No spend yet" pill
10. Auto-fill empty Comments when Status is non-OK
11. Pink-fill-on-Status regression test
12. Boundary value parametrize ($5K, $25K, $100K, calendar 25%)

**4 deferred items** documented for future rounds:
- Status column position (col 13 vs col 3) — UX critic recommended col 3 for left-to-right scan; deferred to F2 redesign opportunity to avoid mid-round layout churn
- Print width compression — needs real Excel print preview to validate; not a code change
- Cell comment loss on read_only round-trip — only matters if downstream consumer changes
- Long-notes / em-dashes-in-user-notes / 200+ char tests — rare edge cases

---

## Files touched

| File | Change |
|---|---|
| `tools/sub_program/logic.py` | New `_STATUS_*` constants + `_STATUS_VALUES` tuple + `compute_status_pill` (~150 lines including R1 pacing-aware compare). New `_DRIVER_PROSE` / `_OUTLOOK_PROSE` / `_ACTION_PROSE` mappings + `_CONTRADICTORY_DRIVER_OUTLOOK` / `_CONTRADICTORY_DRIVER_ACTION` frozensets + `render_commentary_prose` (~80 lines). New `cap_percent_for_display` + `_PERCENT_CAP` (~30 lines). Writer integration (~80 lines): `_write_capped_percent` inner function with text-marker render path; commentary block calls `render_commentary_prose` + auto-fill + row-height heuristic; status pill block computes pill + bolds the four attention pills + extends pink-fill range to col 14. Title-row merge extended 12→13. |
| `tools/sub_program/tests/test_logic.py` | New `TestStatusPill` (12 tests), `TestCommentaryProse` (11), `TestPercentCap` (7), `TestF1XlsxIntegration` (7), `TestF1Round1Fixes` (17). Two existing tests updated for the prose + pill-name + capped-marker contract changes. Total new: ~54 tests. |
| `app_metadata.py` | `APP_VERSION` 2.3.0.0 → 2.3.1.0 (patch — renderer-only changes). |
| `CHANGELOG.md` | New v2.3.1.0 section. |

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
                                            # 204 passed, 2 skipped
                                            # 9 failed, 15 error — all
                                            # env-only PDF-dependent
                                            # (pre-existing, unchanged from
                                            # Round 51 baseline)
```

The 24 env-only failures all stem from the missing `Samples/Annual
Subprogram Budget Report/GL21157_*.pdf` fixture, which isn't in
this Cowork worktree but lives in the parent repo's `Samples/`
directory.

---

## What's left for next rounds

Per Round 52's redesign brief:

| Phase | Moves | Effort | Ship |
|---|---|---|---|
| ✅ **F1 (this round)** | Move B + E + F | done | 2.3.1.0 |
| **F2** | Move D (Trend column vs prior period) + Watchlist sheet | ~1 round | 2.4.0.0 |

F2 needs prior-period YTD extraction (currently `load_prior_period_comments`
only reads commentary). When that lands, the Detail sheet gets a
Trend column (`New issue` / `Worsening` / `Stable` / `Improving` /
`Resolved`) and a council-targeted Watchlist sheet filtered to
`Status ≠ "On track"` rows.

Other deferred items from Round 52's brief:
- Status column position revisit (col 3 vs col 13) — only worth
  doing alongside the F2 layout churn, not as standalone change.
- Print-scale audit — verify 13-column landscape A4 fit-to-width
  doesn't compress to illegible body font. Real Excel print
  preview required.

---

## Status

- 12 R1 fixes applied + 17 regression tests pin them.
- 2.3.1.0 ready for `pwsh msix\build_msix_package.ps1 -StoreUpload`
  on Windows.
- Brief at [handoff/round52_output_redesign_brief.md](round52_output_redesign_brief.md)
  documents F2 + F3.
- Round 52 brief's F1 phase is COMPLETE.

— end of round —
