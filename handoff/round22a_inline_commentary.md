# Round 22a — Inline commentary + banner names the over-budget line

**Date:** 2026-04-30
**Scope:** First slice of Round 22's UI overhaul.  The full
Round 22 brief covers seven items (view tabs, Combined subsidy viz,
collapsible inputs, faculty rail data-bars, banner naming,
side-by-side sliders, output pill).  This phase ships the highest-impact
behaviour change requested by the user (inline row-click commentary)
plus the trivial banner-naming win.  Everything else stays queued for
Round 22b.

---

## What changed

### 1. "Edit commentary..." button is gone

`secondary_actions()` previously returned three buttons:
`[Edit commentary..., Export to Excel, Open output folder]`.  The Edit
commentary button opened a modal `CommentaryDialog` listing every
sub-program for bulk editing.  That UX put commentary editing in a
modal that hides the very table the user wants to comment on.

Round 22a removes the button.  The action row now reads
`[Generate report, Export to Excel, Open output folder, Clear]`.

The `CommentaryDialog` primitive itself is kept (no callers, but its
tests still exist) so the change is reversible if needed.  The
`_edit_commentary` method on `SubProgramBudgetReportTool` was renamed
to `_open_inline_comment_editor` and rewritten — see below.

### 2. Click any row → inline single-row comment editor

`TableSpec.on_row_click` is now wired in `_build_result`:

```python
def _on_row_click(row: dict[str, Any]) -> None:
    if row.get("_is_comment_row"):
        return
    self._open_inline_comment_editor(row)
```

`_open_inline_comment_editor` is a focused single-line editor:

- Modal `Toplevel` 520×240 px, centred on the main window, `grab_set()`.
- Title: `Comment — 4400 Photography (Revenue)` (sub-program +
  description + account).
- Header label same.
- `tk.Text` widget pre-filled from this priority chain:
  1. `_commentary_overrides[sub_program]` (live edit cache)
  2. The line's own `commentary` field (carries the prior-period join)
  3. Empty
- Footer: `Cancel` + `Save` (Accent.TButton).

On Save:
- Non-empty text → `_commentary_overrides[sub_program] = text`.
- Empty text → pop the override (clears the comment + its sub-row).
- `_refresh_after_comment_edit()` rebuilds the result panel and pushes
  it through the shell's `_render_result` path so the table immediately
  shows the new comment as a sub-row.

On Cancel: window destroyed, no state changed.

### 3. Comments shown as italic muted sub-rows

Each `SubProgramLine` with non-empty commentary gets a synthetic
"comment sub-row" inserted **immediately after** its parent data row
in `table_rows`:

```
4400  Revenue   Photography           $4,400   $2,880   $1,520   65.4%
                  💬  Reviewed by council
4001  Revenue   Art                  $18,950  $13,760   $5,190   72.6%
1251  Revenue   Design, Creativity    $7,575   $4,720   $2,855   62.3%
```

The sub-row carries:
- `_is_comment_row=True` — for the click-handler early-return + style
  detection.
- `_data_row_idx=N` — index of the parent data row (kept for future
  use; not consumed yet).
- `_faculty` and `_over` inherited from the parent so the existing rail
  filter and pink-fill paths keep grouping working visually.
- All numeric/account/sub-program columns blanked.

Styling is driven by the existing `row_style` callable.  Round 22a
extends that callable's return type from `dict[str, str]` to
`dict[str, Any]` so the `font` key can carry a Tk font tuple
`(family, size, "italic")`.  The Table primitive's `set_rows` reads
the optional `font` from the style dict and applies it to the
per-row tag.

### 4. Banner names the over-budget line

Old (single-line case):

> 1 line over budget (Rev >120%, Exp >110%): 4400/Revenue.

New (Round 22a):

> 1 line over budget (Rev >120%, Exp >110%): 4400 Photography (Revenue) — over by $19,213.00.

Description first (most informative), account suffix in parentheses,
the over-by dollar amount in the same line so the user doesn't have to
scan the table for it.  Multi-line case unchanged for now (still shows
just `n lines over budget` because the names would be too long for one
banner — Round 22b's view tabs solve that differently).

---

## What did NOT change (still queued for Round 22b)

- **View tabs** above the data area (Revenue / Expense / Combined).
- **Combined subsidy viz** — per-sub-program horizontal stacked bar.
- **Auto-collapse inputs** after first run.
- **Faculty rail data-bars** behind each row.
- **Sliders side-by-side** instead of stacked.
- **Output pill** — promote `Output: D:\…` log line to a clickable
  chip near Open output folder.
- **Log collapse** — `Show log ▾` toggle, hidden by default.

The biggest absolute UX win here will be the view tabs + log collapse
because they unlock real estate for the data area.  Saving them for
Round 22b keeps each round independently shippable and testable.

---

## Files touched

```
MOD   toolkit/base_tool.py
       - TableSpec.row_style return type widened from dict[str, str]
         to dict[str, Any] so callers can pass a Tk font-spec tuple

MOD   toolkit/primitives.py
       - Table.set_rows: tag_configure now accepts an optional 'font'
         key in the row_style dict

MOD   tools/sub_program/frame.py
       - secondary_actions(): "Edit commentary..." removed
       - _build_result():
           - over-budget banner names the line
           - table_rows interleaves _is_comment_row sub-rows
           - _row_style returns italic muted style for comment rows
           - TableSpec.on_row_click wired to inline editor
       - _edit_commentary() replaced with _open_inline_comment_editor()
         (focused single-row Toplevel)
       - new _refresh_after_comment_edit() walks the Tk widget tree to
         find the shell's _render_result hook

MOD   tools/sub_program/tests/test_frame.py
       - test_secondary_actions assertion updated (2 buttons not 3)
       - new TestRound22aInlineCommentary class:
           - test_comment_subrow_inserted_after_parent_with_commentary
           - test_no_subrow_for_line_without_commentary
           - test_subrow_inherits_over_budget_flag
           - test_table_spec_has_on_row_click
           - test_on_row_click_skips_comment_subrows
           - test_banner_names_the_single_over_line
```

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict toolkit/ tools/ tests/  → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 528 passed, 66 skipped (pre-existing
                            sub_program tkinter-stub pollution and
                            Windows-only pywin32 paths skipped on Linux)
```

The 528 figure includes 6 new Round 22a tests in
`TestRound22aInlineCommentary`.

The pre-existing failures in `tools/operating/tests/test_logic.py`
(sample-PDF naming drift) are unchanged and unrelated.

---

## Cross-FS sync gotcha hits this round

Encountered three: `tools/sub_program/frame.py`, `toolkit/base_tool.py`,
and `toolkit/primitives.py`.  Each truncated mid-edit on the bash mount
while the Windows-side Read tool still showed the full file.  Recovered
via `head -n N file > /tmp/head ; cat /tmp/head /tmp/tail > /tmp/full ;
cp /tmp/full file ; touch file`.  Pattern is well-documented in
CLAUDE.md.

---

## What to manually verify on Windows

1. **Click any data row in the Sub-Program dashboard.**  A small
   modal should appear titled `Comment — {sub} {desc} ({Revenue|Expense})`.
   Type a comment, click Save.  The dialog closes and the comment
   appears as an italic muted sub-row immediately below the data row.
   Click the same row again — the editor pre-fills with the comment
   you just typed.  Clear the text and Save → the sub-row disappears.

2. **Click a comment sub-row.**  Should be a no-op (no editor pops).

3. **Banner naming.**  With exactly one line over budget, the banner
   should read e.g. `1 line over budget (Rev >120%, Exp >110%):
   4400 Photography (Revenue) — over by $19,213.00.`

4. **No "Edit commentary..." button.**  The action row under the
   thresholds should now be:
   `[Generate report] [Export to Excel] [Open output folder] [Clear]`
   — no `[Edit commentary...]`.

5. **Existing prior-period commentary** (loaded from a Round 21
   prior-period file) should also render as sub-rows on first paint
   without any clicks needed.
