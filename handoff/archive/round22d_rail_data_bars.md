# Round 22d — Faculty rail data-bars

**Date:** 2026-05-01
**Scope:** Round 22's last visual-polish item that materially changes
how the dashboard reads.  Sliders side-by-side and auto-collapse
inputs are deferred to Round 22e.

---

## What changed

### Faculty rail data-bars

Each row in the in-tool side rail now carries a thin (3 px) progress
bar at the bottom showing the faculty's used % visually.  Bar colour
is driven by the value:

| Used % | Colour | Token |
| --- | --- | --- |
| ≤ 100 | green | `tokens.OK_FG` (`#0B6E0B`) |
| 100-110 | amber | `tokens.WARN_FG` (`#9A6700`) |
| > 110 | red | `tokens.DANGER_FG` (`#B00020`) |

The bar widens proportionally to the used %, clamped to 0-100% for
display purposes — a faculty over 100% still shows a fully-filled
red bar (the badge text is the precise value).

The bar sits on a thin track (`tokens.BORDER_SUBTLE`) so partial fills
read clearly even on light row backgrounds.

### Why this matters

Pre-22d the rail showed `[Faculty name]   65 %` — readable but you had
to compare numbers row-by-row to spot the under-performing faculty.
With the data-bar the rail becomes a one-glance heat-map: a row of
short red bars jumps out as "these faculties are over budget"; a
mostly-green column reads as "everyone's tracking well".

### Backwards-compatible

`RailItem.value_pct` defaults to `None`.  Tools that don't set it get
the rail unchanged from Round 22c.  Only Sub-Program currently emits
the field (other tools that use SelectableList — none right now in
the live rail — would opt in by adding `value_pct=...` to their
RailItem).

---

## Files touched

```
MOD   toolkit/base_tool.py
       - RailItem.value_pct: float | None = None  (new optional field)

MOD   toolkit/primitives.py
       - SelectableList._build_rows: when item.value_pct is set, pack a
         3px bar at the bottom of the row (tk.Frame with .place() for
         proportional width).  Pack ordering matters — bar is packed
         BEFORE the label/badge so it claims the bottom strip; label
         and badge fill the remaining height.

MOD   tools/sub_program/frame.py
       - _build_result populates RailItem.value_pct from the same
         used % the badge already shows (faculty_used_pct[fac]).
```

No new tests added — the behaviour is rendered by Tk widgets that skip
on Linux CI.  Existing rail tests confirm `RailItem` instantiates +
the rail builds without value_pct.

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict toolkit/ tools/ tests/  → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 534 passed (no regressions)
```

---

## What remains for Round 22e

1. **Sliders side-by-side** — Revenue + Expense thresholds in one row
   sharing a hint line.  Saves a vertical row of input chrome.
2. **Auto-collapse inputs** after first run into a summary chip.
   Reclaims ~250 px of input chrome real estate after the user has
   committed to inputs.
3. **Tab-aware faculty filter** — currently disabled when tabs are
   present (rail click is a silent no-op).  Re-enable by filtering
   the active tab's rows.

---

## Cross-FS sync gotcha hits this round

Three truncations:
- `toolkit/base_tool.py` (mid-`preview_update` docstring)
- `toolkit/primitives.py` (mid-`CommentaryDialog` button block, plus
  one duplicated `command=` keyword from a sloppy append)
- `tools/sub_program/frame.py` (mid-`_merge_commentary_overrides`)

All recovered via the standard `head -n N file > /tmp/head ; cat
/tmp/head /tmp/tail > /tmp/full ; cp /tmp/full file ; touch file`
pattern.  The `command=_do_ok` duplication was a fresh failure mode —
when appending a tail block that overlapped the existing last line,
`sed -i '<dup_line>d' file` is the right one-shot fix.

---

## What to manually verify on Windows

1. Open Sub-Program, run Generate report.
2. The faculty rail (right of the Revenue / Expense / Combined data
   table) should now show, per row:
   - `[Faculty name]   65 %` text as before.
   - A 3 px coloured bar along the bottom of the row, width
     proportional to 65/100, in green (under 100%), amber
     (100-110%), or red (over 110%).
3. Faculties with `highlight=True` (i.e. carrying an over-budget
   line) still get their pink background; the bar sits at the bottom
   of the pink fill.
4. Switching between tools should not leak rail bars to tools that
   don't use them.
