# Round 27 — Master Budget Compare two files (per sub-program, 3 metrics)

**Date:** 2026-05-02
**Scope:** New "Compare" mode on the existing **Master Budget Compass
Autofill** tool. User can upload two Master Budget XLSM files and review
sub-programs whose **Total Estimated Revenue**, **Total Proposed
Expenditure Current Year**, or **Total Estimated Funds Held future
years** values differ between the two files.

---

## User ask (verbatim)

> 在master budget中，增加对比功能，用户可以上传两个master budget，可以
> 对比每个subprogram 的 Total Estimated Revenue, Total Proposed
> Expenditure Current Year, 和 Total Estimated Funds Held future years

Translation: add a Compare feature in the Master Budget tool — user
uploads two Master Budgets; compare each sub-program's three target
metrics.

Decisions captured up-front via AskUserQuestion:

| Q | Choice |
| --- | --- |
| Packaging | New mode inside existing Master Budget tool (no new tool entry on the rail) |
| Source rows | Read from the **Master** sheet (same sheet Autofill writes to) |
| Output | In-app table + optional Excel export |
| Mismatch | Show only differences (rows where any of the 3 metrics differ; sub-programs only in one file are always included) |
| Label match | Tier 1 exact (case-insensitive) → Tier 2 substring → Tier 3 fuzzy (Jaccard ≥ 0.5) — find the more relevant one when no exact match |

---

## How mode is picked (no extra UI primitive)

The tool has **three** FileInputs now. The mode is detected automatically
from which combination is non-empty — no SelectInput / radio button /
mode toggle. The user just leaves blank what doesn't apply:

| File 1 (Compass Expense) | File 2 (Master Budget A) | File 3 (Master Budget B) | Mode |
| --- | --- | --- | --- |
| filled | filled | empty | **Autofill** (existing) |
| empty | filled | filled | **Compare** (new) |
| anything else | | | Error: clear instruction |

This sidesteps adding a SelectInput primitive to `BaseTool`. The labels
on the file pickers carry the affordance:

* "Compass Expense file (Autofill mode only — leave blank for Compare)"
* "Master Budget template (or Master Budget A in Compare mode)"
* "Master Budget B (Compare mode only — leave blank for Autofill)"

The help text up the top spells out the two flows explicitly.

---

## Compare flow output

### In-app table

Eleven columns:

| Sub-program | Description | Revenue A | Revenue B | Δ Revenue | Expense A | Expense B | Δ Expense | Funds A | Funds B | Δ Funds |

* Δ cells render as `$X.XX ↑` (B − A positive) or `$X.XX ↓` (B − A
  negative) or em-dash (zero / either-side missing) — same direction
  glyph language as the Sub-Program Combined view (Round 24).
* Sub-programs that exist in **only A** or **only B** get the canonical
  pink **HL_MISMATCH** row tint via `TableSpec.row_style`. Their unknown
  side reads as em-dash.
* Sub-programs whose three values are identical between A and B are
  filtered out — only differences show up in the table (per user spec
  "Show only the differences").

### Log

```
COMPARE SUMMARY
Differences: 12  |  Only in A: 1  |  Only in B: 2
File A: 'Total Estimated Revenue' matched via substring → 'Total Estimated Revenue 2026'
File B: 'Total Estimated Funds Held future years' not found — values treated as blank
Sub-programs only in A (1):
  4400
Sub-programs only in B (2):
  1320
  6201
```

The label-match summary surfaces fuzzy/substring/missing matches so the
user knows when a fallback fired.

### Optional Excel export

A second secondary action button **"Export comparison Excel"** opens a
Save dialog (default filename `MasterBudget_Compare_<YYYYMMDD_HHMM>.xlsx`,
default folder = next to Master Budget A). The XLSX has the same 11
columns + a merged title row, accounting number format on all numeric
cells, frozen panes at A3, and pink HL_MISMATCH fill on Δ cells where
the two files actually differ.

`Export comparison Excel` is a no-op (with a friendly info dialog) until
a Compare run has populated `_last_compare_summary`.

---

## Label matching — three tiers

`_locate_compare_target_rows(ws)` scans column B of the Master sheet for
each canonical target label, in this order:

1. **Exact** (case-insensitive) — `label.lower() == target.lower()`.
2. **Substring** — every word of the canonical target appears as a whole
   token in the label (`target_tokens <= label_tokens`).
3. **Fuzzy** — Jaccard token overlap `|A∩B| / max(|A|,|B|) >= 0.5`. The
   highest-scoring candidate wins.

Each row index is consumed once (`used_rows`), so the three target keys
can't all map to the same row by accident.

When a tier finds no candidate, the entry is `None` and that metric
reads as `None` (em-dash) for every sub-program in that file. The log
surfaces it via a yellow `tag="warning"` line.

---

## Files touched

```
MOD   tools/master_budget/logic.py
       - new dataclasses: CompareRow, CompareSummary
       - new public API: compare_master_budgets, write_compare_xlsx,
         suggest_compare_output_name
       - new internals: _extract_compare_data, _locate_compare_target_rows
       - module-level _COMPARE_TARGET_LABELS constant

MOD   tools/master_budget/frame.py
       - inputs[]: 3rd FileInput master_file_b added
       - run() dispatches between _run_autofill and _run_compare based
         on which paths are filled
       - _build_compare_result builds the 11-column TableSpec + log
       - secondary_actions(): added "Export comparison Excel"
       - _export_compare_xlsx opens Save dialog → write_compare_xlsx
       - module-level _fmt_money / _fmt_delta helpers
       - help_text rewritten to describe both modes

MOD   tools/master_budget/tests/test_frame.py
       - test_inputs_declares_two_file_inputs → renamed to ..._three_...
         (expect 3 FileInputs now; "master_file_b" key)
       - test_returns_open_output_folder_action: now expects 2 actions
         ('Open output folder' + 'Export comparison Excel')
       - new test_export_compare_handles_no_prior_compare

MOD   tools/master_budget/tests/test_logic.py
       - 7 new tests in "Round 27 — Compare two Master Budget files":
           test_compare_no_differences
           test_compare_value_differences
           test_compare_sub_program_only_in_one_file
           test_compare_label_match_substring_fallback
           test_compare_label_match_missing_treated_as_blank
           test_compare_write_xlsx_creates_file
           test_compare_rejects_same_file
       - new helper _build_compare_master writes synthetic XLSMs for
         the compare tests
```

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 542 passed, 66 skipped (env), 1 warning
                           (was 534 passed — +8 from new compare tests
                            + extended secondary-action test)
```

The token-drift guard stays happy — the only hex used is `HL_MISMATCH`
via `argb()` for the pink fill on Δ cells / only-in rows, identical to
the existing pattern in `_apply_mismatch_highlights`.

---

## What to manually verify on Windows

### Autofill mode (regression check — must still work)

1. Pick a Compass Expense XLSX **and** a Master Budget XLSM template,
   leave Master Budget B blank, click **Generate budget workbook**.
2. Output saves as `<stem>_AUTO_<timestamp>.xlsm` next to the template.
3. **Open output folder** secondary action reveals it in Explorer.
4. Banner + log behave as before (mismatch counts, source-only items).

### Compare mode (new)

1. Pick two Master Budget XLSM files — one as Master Budget (A), one as
   Master Budget B. Leave the Compass file blank. Click **Generate**.
2. Banner shows either "No differences found across …" (green) or
   "Found N sub-program difference(s) …" (amber).
3. Table appears with 11 columns, only the differing sub-programs.
4. Δ columns show ↑ / ↓ glyphs; em-dash on zero / missing-side.
5. Sub-programs only in A or only in B render with pink row tint.
6. Log lists `COMPARE SUMMARY` totals + any only-in-A / only-in-B codes
   + label-match notes when a fallback fires.
7. Click **Export comparison Excel** — Save dialog appears with
   `MasterBudget_Compare_<timestamp>.xlsx` default name. Save it.
8. Open the saved XLSX: row 1 has the merged title; row 2 the headers;
   data rows from row 3; A3 freeze pane stays visible while scrolling;
   Δ cells with non-zero values are pink-filled; numbers use the
   accounting format.
9. Click **Export comparison Excel** before any Compare run → friendly
   info dialog "No Compare run yet. …" — must not raise.

### Error edge cases

* Pick same file twice for A and B → friendly error "Master Budget A
  and B must be two different files."
* Pick only the Compass file → friendly error "Autofill mode requires
  both the Compass Expense file and the Master Budget template."
* Pick only Master Budget B → friendly error "Compare mode requires
  Master Budget A."
* Pick a Master Budget where the Master sheet doesn't have the three
  target labels → log lines flag each missing target; the affected
  metric reads as em-dash for every sub-program.

---

## Cross-FS sync gotcha hits this round

Heavy. `tools/master_budget/logic.py`, `tools/master_budget/frame.py`,
and **both** test files (`test_frame.py`, `test_logic.py`) all
truncated mid-edit on the bash mount, multiple times each. The
`test_frame.py` truncation was particularly nasty — at one point my
attempted recovery via `cp` from a partial /tmp file overwrote the
Windows-side file with only 61 lines, dropping ~315 lines of
pre-existing tests. Recovered via `git show HEAD:tools/master_budget/
tests/test_frame.py > /tmp/test_frame_orig.py` and re-applied the
Round 27 test edits.

CLAUDE.md's recommendations (head+tail recovery via `/tmp` files,
`touch` to bump mtime, prefer batched edits over incremental Edit
calls) all applied. New nuance worth recording: when bash mount is
truncated, doing a `cp /tmp/partial path` **also** overwrites the
Windows view — so always reconstruct the FULL file content (from git
or from a Read tool view) before cp'ing back. Never cp a partial.

---

## Why two distinct File inputs instead of a SelectInput

Considered adding a `SelectInput` primitive to `BaseTool` so the user
sees an explicit "Mode: ⦿ Autofill ◯ Compare" radio. Rejected because:

* It needs new shell rendering (ttk.Combobox / Radiobutton), input-cache
  wiring, and updates to every `_build_input_widget` dispatch — high
  surface-area change for a one-tool need.
* The current "leave blank what doesn't apply" approach mirrors how the
  SRP Compare tool already works (any-2-of-4 inputs, Round 18) — the
  user is already familiar with this pattern.
* Help text + label suffixes on each FileInput communicate the mode
  affordance clearly without a separate widget.

If a third tool eventually needs "modes", the SelectInput primitive
becomes worth it. For now, the discriminated-union approach is
zero-cost on `BaseTool` / `toolkit/shell.py`.
