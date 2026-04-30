# Round 21 — HYIA press-to-reveal, About→Privacy, comments bug, threshold split

**Date:** 2026-04-30
**Scope:** Phase A of a four-item batch.  Items 5+6 (Sub-Program view
tabs and Combined-mode subsidy visualisation) are deferred to Round 22.

---

## What changed

### 1. HYIA — press-and-hold "Show formula" button

The HYIA result used to always show the calculation formula in the log
area. Anyone glancing at the screen could see the SIN-derived breakdown
(masked SIN + amount + DD + MM + YY = code).  The user wants the
formula hidden by default and revealed only while the verifier holds a
button down.

Implementation:

- **New shell hook** — `BaseTool.press_hold_actions()` (optional,
  read via `getattr` so the Protocol doesn't change).  Returns
  `list[tuple[str, Callable[[], str]]]` — each entry becomes a button
  paired with a small grey label.  While the user holds the left mouse
  button on the button, the label shows `get_text()`.  On release (or
  pointer leave), the label clears.
- **`toolkit/shell.py::_make_press_hold_button`** — packs the button
  + sibling label and wires `<ButtonPress-1>` / `<ButtonRelease-1>` /
  `<Leave>` bindings.
- **`HyiaTool.run()`** — caches the formula in `self._last_formula`,
  emits a placeholder log line ("Calculation hidden. Press and HOLD
  'Show formula' below…") instead of the raw formula.
- **`HyiaTool.press_hold_actions()`** — returns
  `[("Show formula", lambda: self._last_formula)]`.
- **`HyiaTool.clear()`** — resets `_last_formula = ""` so a stale
  value can't leak after the user clicks Clear.
- Help text rewritten to explain the press-and-hold pattern.

Tests added:
- `test_run_log_lines_show_placeholder_only` — formula is NOT in
  log_lines, placeholder mentions "Show formula"
- `test_press_hold_formula_text_masks_sin` — revealed text masks SIN
  but contains amount + final code
- `test_press_hold_formula_six_digit_sin_masked` — six asterisks for
  six-digit SINs
- `test_press_hold_empty_before_run` — returns "" before any run()
- `test_clear_resets_cached_formula` — Clear wipes the cache

### 2. Rail "About" → "Privacy Policy"

The static "About" entry in the left rail used to show a `messagebox`
with the version + support email — useful to nobody.  Round 16 already
authored a complete privacy policy at `docs/store_privacy_policy.md`
for the Microsoft Store submission.  We surface it now.

- Rail entry renamed "About" → "Privacy Policy".
- New `_show_privacy_policy()` reads `docs/store_privacy_policy.md`,
  strips the leading `# Heading` line (the help-window's navy header
  bar already shows the title), and renders the body using the
  existing `_show_help_window` primitive (scrollable, headings styled,
  hex colours rendered as swatches).
- The old `_show_about` method is kept (no callers) for backward
  compatibility with any legacy tests that still reference it.

### 3. Sub-Program prior-period comments — bug fix

**Root cause.** Pre-Round-21 the loader ran:

```python
try:
    txt_col = next(i for i, h in enumerate(header) if "comment" in h)
except StopIteration:
    txt_col = 2  # ← the bug
```

When the user's prior-period file had no header containing the word
"comment" (e.g. their template used "Notes" / "Remarks" / a non-English
header / a multi-row header), the loader silently fell through to
column 2.  In our exported workbooks column 2 is **"Last year actual"
— a dollar amount**.  So users saw last-year-actual budget values
copied into the new report's comments column.

**Fix in `tools/sub_program/logic.py::load_prior_period_comments`:**

- Accept synonyms: `comment`, `commentary`, `note`, `remark`, `memo`.
- If NO sheet has any of those headers, raise a descriptive
  `ValueError` listing the headers we did find — never silently
  default to a budget column.
- Read **every worksheet**, not just the first one — exports of this
  tool produce Revenue + Expenditure as separate sheets and both
  carry comments.
- Account-column synonyms expanded: `account`, `gl`, `code`.  When
  none match (true for our own exports, which intentionally drop the
  Account column), fall back to the Title / Description column for
  the second join key.
- Skip rows whose first column isn't a sub-program code (purely
  numeric) — stops "Total" / blank rows from polluting the dict.

**Fix in `generate_report` join logic:**

- Try `(sub_program, account)` first (canonical, used by raw CASES21
  exports).
- Fall back to `(sub_program, description)` when the first lookup
  misses — handles the case where the prior file is one of our own
  exports.

Tests added (`tools/sub_program/tests/test_logic.py`):
- `test_notes_synonym` — "Notes" header is accepted
- `test_no_account_column_falls_back_to_title` — exports without an
  Account column still join correctly via title
- `test_missing_comment_column_raises` — bug guard: no comment column
  ⇒ ValueError, not silent budget-column copy
- `test_reads_all_sheets` — Revenue + Expenditure sheets both contribute

### 4. Sub-Program — split single threshold into Revenue + Expense

Schools care about Expense over-runs (the "watch this" case) but
rarely flag Revenue over-collections (over-collecting is usually fine).
Round 11's single 100–120% slider applied the same threshold to both
sections.

- **`SubProgramLine.is_over` semantics unchanged** — still
  `used_pct > threshold`, threshold is now per-section.
- **`logic._recompute_is_over`** gained two keyword-only params:
  `revenue_threshold` and `expense_threshold`.  When supplied, the
  function picks the right threshold per row using the existing
  `account.lower().startswith("revenue")` test that already drives
  sheet splitting in the XLSX writer.  Backward-compatible: if neither
  is supplied, both default to the legacy `threshold` arg.
- **`logic.generate_report`** gained the same two keyword-only params
  with the same fallback behaviour.
- **`ReportSummary`** gained `revenue_threshold` and `expense_threshold`
  fields (default 101.0).  Existing callers that only set
  `over_budget_threshold` still work — the per-section fields default
  to the same value.
- **`tools/sub_program/frame.py`** replaced the single
  `over_budget_threshold` RangeInput with two stacked sliders:
  `revenue_threshold` and `expense_threshold`.  Each behaves
  identically to the old slider (100–120%, default 101%, live preview).
  The `run()` method also accepts the legacy
  `over_budget_threshold` key as a fallback so older code paths /
  tests keep working.
- **`preview_update`** handles either of the two new keys
  independently, plus the legacy `over_budget_threshold` key as an
  alias for `expense_threshold`.
- **Banner copy** — when both thresholds match, the old `>X%`
  display is preserved; when they differ, shows
  `Rev >X%, Exp >Y%` so the user can tell which side flagged what.

Tests added (`TestPerSectionThreshold` in
`tools/sub_program/tests/test_logic.py`):
- `test_revenue_threshold_only_flags_revenue` — high Rev + low Exp
  thresholds flags only Expense rows
- `test_expense_threshold_only_flags_expense` — symmetric case
- `test_legacy_single_threshold_still_works` — backward compat
- `test_generate_report_passes_thresholds_to_summary` — Summary
  preserves user choices

Inputs tests in `tools/sub_program/tests/test_frame.py` updated:
- `test_inputs_has_four_items` (was three)
- `test_third_input_is_revenue_threshold` (was the threshold check)
- `test_fourth_input_is_expense_threshold` (new)

---

## What did NOT change (deferred to Round 22)

- View-mode tabs (Revenue / Expense / Combined) above the result table
- Per-sub-program horizontal stacked bar in Combined mode showing the
  "school subsidised" portion (Expense > Revenue)

These are the two structural items from the user's request.  They
restructure result rendering, so isolating them in their own round
gives a cleaner rollback path if the visualisation needs iteration.

---

## Files touched

```
NEW   handoff/round21_phase_a.md                            (this file)

MOD   docs/                  (none)
MOD   toolkit/shell.py
       - new _make_press_hold_button helper
       - new _show_privacy_policy method (replaces "About")
       - rail static entry "About" → "Privacy Policy"
       - render press_hold_actions() if defined on the active tool
       - import collections.abc.Callable
MOD   tools/hyia/frame.py
       - cache _last_formula in run()
       - placeholder log line; press_hold_actions() returns the reveal
       - clear() resets _last_formula
       - help text rewritten
MOD   tools/hyia/tests/test_frame.py
       - new placeholder + press-hold tests
MOD   tools/sub_program/logic.py
       - load_prior_period_comments rewritten: synonyms, multi-sheet,
         hard error on missing comments column, title fallback
       - generate_report: optional revenue/expense thresholds, two-key
         comment lookup
       - _recompute_is_over: optional per-section thresholds
       - ReportSummary: revenue_threshold, expense_threshold fields
MOD   tools/sub_program/frame.py
       - two RangeInput sliders (revenue + expense thresholds)
       - run() reads both, accepts legacy over_budget_threshold alias
       - preview_update routes by key, accepts legacy alias
       - clear() resets per-section caches
       - banner shows "Rev >X%, Exp >Y%" when they differ
MOD   tools/sub_program/tests/test_logic.py
       - new TestLoadComments cases (synonyms, missing column, title
         fallback, multi-sheet)
       - new TestPerSectionThreshold class
MOD   tools/sub_program/tests/test_frame.py
       - inputs assertions updated for 4 inputs
       - new threshold-key tests
```

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict toolkit/ tools/ tests/  → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 467 passed, 66 skipped (excluding pre-existing
                            sub_program tkinter-stub pollution)
pytest tools/sub_program/tests/test_frame.py
                         → 55 passed
```

The pre-existing failures in `tools/operating/tests/test_logic.py` are
unchanged — they look for a sample PDF at the wrong path and are
unrelated to this round.

---

## Cross-FS sync gotcha hit (yet again)

Round 21 hit the bash-mount truncation pattern on five files this
round: `tests/test_user_errors.py` (precursor from Round 20),
`tools/hyia/frame.py`, `tools/hyia/tests/test_frame.py`,
`tools/sub_program/logic.py`, `tools/sub_program/frame.py`,
`tools/sub_program/tests/test_logic.py`,
`tools/sub_program/tests/test_frame.py`, and `toolkit/shell.py`.
Each recovered via the standard `head -n N file > /tmp/head ; cat
/tmp/head /tmp/tail > /tmp/full ; cp /tmp/full file ; touch file`
pattern.  CLAUDE.md already documents this — recommending we keep the
existing snippet there.

---

## What to manually verify on Windows

The Tk smoke tests skip on Linux CI so the user should sanity-check:

1. **Privacy Policy** — click the Privacy Policy entry in the left
   rail.  A scrollable modal should appear with the policy text from
   `docs/store_privacy_policy.md`.
2. **HYIA Show formula** — generate a code, press and hold the
   "Show formula" button.  The formula should appear next to the
   button while held; release it and the formula should disappear.
3. **Sub-Program two thresholds** — open Sub-Program, the inputs
   area should now show two sliders ("Revenue over-budget threshold
   (%)" and "Expense over-budget threshold (%)") instead of one.
   Drag each independently and watch the banner / pink fills update.
4. **Sub-Program prior comments** — re-export a previous sub-program
   workbook with comments filled in, then run Sub-Program again with
   that file as the comments input.  The new export should carry the
   comments forward (not last-year-actual values).
