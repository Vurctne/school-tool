# Round 47 — Multi-personality audit + fixes

**Date:** 2026-05-09
**Trigger:** User: "用不同性格的opus 4.7来测试，并改进，优化视觉效果，
逻辑，包括生成的excel"
**Method:** Spawned 4 Opus agents in parallel, each with a different
lens (logic skeptic, UX/visual critic, Excel QA, test-coverage
auditor). Synthesized findings, applied highest-impact fixes,
deferred the rest with explicit Phase B.2 / future-round notes.

---

## What shipped (10 fixes)

### XLSX (highest user impact — the file principals see)

1. **Percent columns now render as percents.** `_PERCENT_AS_PERCENT_FMT
   = "0.0%"` applied to columns 10 (Available Balance % YTD) and 11
   (Revenue Budget % Received YTD). Previously the cells stored
   fractions like `0.398` with no number_format → Excel rendered
   them as decimals.
2. **Print page setup configured.** Landscape A4, fit-to-width,
   `print_title_rows = "1:2"` so title + header repeat on every
   printed page, half-inch margins, page header carries the period
   ("Sub-Program Budget Report — April 2026"), footer has tool
   attribution at left and `Page X of Y` at right. Without this
   the 12-column report overflowed portrait A4 onto 3-4 pages with
   rows split across page breaks.
3. **Pink fill respects materiality.** XLSX now mirrors the in-app
   row_style: a row whose Available Balance is overdrawn AND the
   magnitude meets the dollar materiality floor gets the pink fill;
   below-floor over-drawn rows render plain. Stops the "$50 over a
   $30 budget" XLSX-vs-screen divergence Phase A introduced.
4. **Comments column wraps.** `Alignment(wrap_text=True,
   vertical="top")` on the Comments cell so long commentary doesn't
   overflow horizontally and push the print width past one page.

### Logic (correctness)

5. **Zero-budget-with-spend trigger.** `_recompute_is_over` now
   flags `is_over=True` when `budget == 0 and ytd != 0`, regardless
   of percentage threshold. Previously these rows had `used_pct=0`
   from the parser (defended divide-by-zero) and slipped past the
   percentage gate, even though they're unambiguously over budget.

### UX (small, safe wins)

6. **Watchlist Why microcopy.** `"Over $ + pace"` → `"Over budget +
   pace"`, `"Over $"` → `"Over budget"`, `"Pace"` → `"Ahead of
   pace"`. Reads as natural English, not as cryptic labels.
7. **Faculty rail value spacing.** `"38 %"` → `"38%"` to match every
   other percent render in the file (`_fmt_pct`,
   `_fmt_signed_pct`, threshold_label).
8. **Help text updated.** Removed the stale "Used %" reference from
   the IMPORTANT NOTES section; replaced the user-visible
   `(#F4CCCC)` hex code with `pink`. Dropped the now-pointless
   `f""""` prefix on `_HELP_TEXT` since no placeholders remain.
9. **Empty Watchlist label.** When the count is 0 the tab now reads
   `"Watchlist · all clear"` instead of `"Watchlist (0)"`. Less
   broken-looking when a school is genuinely on track.

### Tests

10. **Updated test for new zero-budget trigger.** The existing
    `test_generate_report_custom_threshold_changes_over_count`
    test asserted "no over-budget lines at threshold 9999%" — now
    splits the assertion: no PERCENTAGE-driven flags fire at 9999%,
    but zero-budget-with-spend rows are allowed to remain.

---

## What was deferred (with rationale)

### From Agent A (logic skeptic)

- **Revenue under-collection invisible to `is_over`** [P0 in Agent
  A's report]. `is_over = used_pct > threshold` only fires for
  over-collect. Under-collected Revenue is currently silent — a
  Revenue line collecting $0 against a $200,000 budget at month 11
  doesn't appear anywhere except buried in the Revenue tab with no
  flag. **Why deferred:** introducing a separate `is_concern` field
  (or inverting `is_over` semantics for Revenue) touches the
  parser, XLSX writer, faculty rail, watchlist, materiality logic,
  and live-preview path. Phase B.2.
- **Pacing direction inverted for Revenue** [Agent A P0]. Same
  blast radius — Revenue pacing > 1.10 is *good* (over-collecting).
  Tagged as Phase B.2.
- **Pacing column missing for `used_pct=0, budget>0` rows** —
  renders em-dash but should show 0 or a "no spend" indicator.
  Sentinel-design call best made when Revenue inversion lands.

### From Agent B (UX critic)

- **Rail bar tinting always green for contribution-pct values.**
  SelectableList's >100/>110 thresholds were keyed for "used %";
  contribution-pct can't exceed 100. **Why deferred:** needs a new
  `bar_tone` field on `RailItem` + primitive-side branching, which
  touches three files including the toolkit primitive used by other
  tools too. Phase B.2.
- **`_fmt_signed_dollar` whole dollars vs Budget/YTD 2dp**
  inconsistency. Cosmetic; design-call needed (which precision
  wins?).
- **Comment-row pink-bg on empty numeric cells reads as broken.**
  Suggests filling with em-dash or skipping the pink-bg-on-comment
  treatment. Polish.
- **Banner repeats metric-card stats** (over-overwhelming top of
  screen). Worth a design pass — touches the banner build path.
- **Combined view ↑/↓ glyphs vs `_fmt_signed_dollar` signs.** Two
  different conventions for "negative number" on the same screen.

### From Agent C (Excel QA)

- **Variance + Pacing absent from XLSX.** Screen leads with
  Variance $ / Var % / Pacing; XLSX still uses the Kate Marshall
  monthly shape. Decision needed: extend the shape or add a second
  "Variance Analysis" sheet.
- **Conditional formatting / data bars on monthly sheet** — the
  legacy Revenue / Expenditure sheets had a green data bar; new
  monthly shape lost it. Bring it back on the Available Balance %
  column.
- **School-name extraction for header.** GL21157 carries the school
  name in a page header; parser currently discards it via
  `_SKIP_RE`. Capture it and embed in the print header.
- **Carry-forward column visible distinction from "$0".** Currently
  blank; suggest italic "n/a" or a comment cell.

### From Agent D (test coverage)

- **25 P0 tests proposed.** Calendar pct parser tests, variance /
  pacing / materiality field math tests, Watchlist build /
  filtering / sort tests, rail-by-contribution tests, metric strip
  tests, materiality-mute row_style tests. **Why deferred:** that's
  ~30 new test cases, multi-round work. Will pull in tranches of
  3-5 alongside future feature rounds.

All deferred items are listed in this handoff so future rounds can
reach back without re-running the audit.

---

## Files touched

| File | Change |
|---|---|
| `tools/sub_program/logic.py` | New `_PERCENT_AS_PERCENT_FMT` constant. Number format on % cols 10/11. Materiality-aware pink fill. Print page setup (orientation, fit-to-width, title rows, margins, header/footer). Comments cell wrap_text. Materiality plumbed through `_write_xlsx` → `_write_monthly_sub_program_sheet`. Zero-budget-with-spend trigger in `_recompute_is_over`. |
| `tools/sub_program/frame.py` | Watchlist Why microcopy reworded. Rail value spacing. Help text updated (lost stale Used %, hex code, `f` prefix). Empty Watchlist label. |
| `tools/sub_program/tests/test_logic.py` | Updated `test_generate_report_custom_threshold_changes_over_count` for zero-budget trigger. |
| `app_metadata.py` | `APP_VERSION` 2.2.5.0 → 2.2.6.0 |
| `CHANGELOG.md` | New v2.2.6.0 section. |

---

## Quality gates

```
ruff format --check .                       # 79/79 ok
ruff check .                                # All checks passed!
mypy --strict (--cache-dir=/tmp/mypy_cache) # 79 source files, no issues
pytest -q --ignore=tools/operating/tests    # 507 passed, 66 env-only skips
                                            # (sub_program: 128/128)
```

---

## Sandbox truncation incidents (info only)

This round was the worst yet for cross-FS sync truncation — multiple
recoveries on logic.py, frame.py, test_logic.py, plus a null-byte-
padding incident in logic.py (27 trailing nulls). All recovered via
the standard pattern. Stale `.pyc` masked one issue until pytest was
re-run with `PYTHONDONTWRITEBYTECODE=1 python3 -B`. Worth keeping in
mind that file modification by a linter (which has happened mid-Edit
several times this round) can also reset the truncation cycle.

---

## Status

- 10 fixes shipped, 14+ deferred with explicit Phase B.2 / future-
  round labels.
- 507 tests pass (66 env-only skips).
- `APP_VERSION = "2.2.6.0"`. Ready for `pwsh
  msix\build_msix_package.ps1 -StoreUpload` on Windows.
- Task #65 → completed.
