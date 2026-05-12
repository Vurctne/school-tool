# Round 23 — UI polish + filter bug fix + Combined surplus/subsidy colors

**Date:** 2026-05-01
**Scope:** Five fixes from Windows live-testing of Round 22.

---

## What changed

### 1. BUG: Faculty filter showed empty data after click

**Root cause** (introduced in Round 22e): the tab-aware filter path
called `_filter_rows(sub._rows, filter_key)` — i.e. filtering each
tab's CURRENT (already-narrowed) rows.  After the first click, each
tab's `sub._rows` was the filtered subset for the previous filter
key; clicking a different faculty narrowed THAT subset down to zero.

**Fix:** cache the original per-tab spec on the shell when the
Notebook is built (`self._tool_table_tabs[tid]`), and filter from
that cache instead of `sub._rows`.

```
self._tool_table_tabs[tid] = list(result.table_tabs or [])
...
cached_tabs = self._tool_table_tabs.get(tool_id, [])
tab_specs_by_index = {
    i: list(spec.rows) for i, (_, spec) in enumerate(cached_tabs)
}
for idx, child_path in enumerate(notebook.tabs()):
    sub = ...find Table inside tab_frame...
    original = tab_specs_by_index.get(idx, sub._rows)
    sub.set_rows(_filter_rows(original, filter_key))
```

`_clear_filter` uses the same cache to restore each tab's full row set.

### 2. Default-show log; remove the redundant banner + footer

User feedback: "默认显示log，移除图1里面的东西，都是重复的".  The yellow
banner duplicated the first log line; the "Please send feedback to
…" footer duplicated the email already in the status bar.

- **Log toggle default flipped to expanded.**  `Show log ▾` → starts
  visible as `Hide log ▴`.  Reset on each fresh result also goes to
  expanded.
- **Banner suppressed entirely.**  `_render_result` no longer creates
  a `Banner` widget for any banner level (success / warning / danger).
  The status bar at the bottom of the window still picks up
  `result.banner_text[:100]`.
- **"Please send feedback to …" footer removed** from
  `_build_tool_frame`.  Status bar already shows
  `v{APP_VERSION} · {SUPPORT_EMAIL}`.

### 3. Combined view: surplus = green, subsidy = blue

User feedback: "Surplus绿色 对应 subsidy蓝色".  Pre-23 the Combined view
only rendered subsidy (red/pink).  Round 23 distinguishes:

- **Subsidy** (Expense > Revenue) — school filling the gap → soft
  BLUE row tint (`tokens.INFO_BG`).  Imbalance value gets a `↓`
  marker.
- **Surplus** (Revenue > Expense) — sub-program over-collecting →
  soft GREEN row tint (`#` + `tokens.HL_SOURCE_ONLY`).  Imbalance
  value gets a `↑` marker.

`_build_combined_rows` now returns `(rows, total_subsidy, total_surplus)`.
Combined tab title shows both totals when present:
`Combined · subsidy $19,213 · surplus $14,000`.

The unicode bar in the "Budget shape" column now uses a
`min(Rev,Exp)` common base + `▓` blocks for whichever side is bigger
— so subsidy and surplus both render visibly proportional regardless
of direction.

### 4. Threshold slider label drops the live `: X%` suffix

Pre-23: `Revenue over-budget threshold (%): 120%` — the value was
shown both in the label AND in the entry box right below it.

Post-23: `Revenue over-budget threshold (%)` — label is now a static
string.  The entry box on the next row remains the canonical value
display.

### 5. Threshold slider hint text removed

Pre-23: italic line under each slider "Type any value > 0 — drag
limited to 100–120%".  Cluttered the input row.

Post-23: removed.  The slider's min/max labels (100% / 120%) already
convey the drag range; typing values outside that range still works
silently (just snaps the knob to the nearest end).

---

## Files touched

```
MOD   toolkit/shell.py
       - _tool_table_tabs cache for tab-aware filter
       - _apply_filter / _clear_filter use the cache instead of sub._rows
       - log block default flipped to expanded; reset goes to expanded
       - banner widget no longer rendered
       - "Please send feedback" footer removed
       - threshold label simplified to static text (drops live suffix)
       - threshold hint text removed

MOD   tools/sub_program/frame.py
       - _build_combined_rows returns (rows, subsidy, surplus) triple
       - Surplus rows carry _surplus=True
       - Imbalance text gets ↓ for subsidy, ↑ for surplus
       - Combined tab title shows both totals when present
       - _combined_row_style: blue for subsidy, green for surplus
         (uses canonical INFO_BG + HL_SOURCE_ONLY tokens)

MOD   tools/sub_program/tests/test_frame.py
       - Round 22b combined-tab tests updated for new
         (rows, subsidy, surplus) tuple shape and new column copy
```

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict toolkit/ tools/ tests/  → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 534 passed, no regressions
```

The token drift guard (`test_no_rogue_hex_in_tool_strings`) is happy
— Round 23 uses only canonical token-derived hex strings for the
new blue / green tints.

---

## What to manually verify on Windows

1. **Faculty filter** — click any faculty in the side rail.  All
   three tabs (Revenue / Expense / Combined) should narrow to that
   faculty's rows.  Click another faculty — tabs should re-narrow
   from the FULL data each time, not from the previous narrow.
   Click the chip's `× clear filter` — tabs restore to full.

2. **Log shown by default** — log block is expanded after a run.
   Click `Hide log ▴` to collapse.

3. **No banner / no "Please send feedback" footer.**  Banner area is
   blank; result reads as: action buttons → output pill (when set)
   → log → tabs → table → faculty rail.

4. **Combined view colours** — sub-programs where Expense > Revenue
   render with a soft BLUE row tint and `$X ↓` in the Subsidy column.
   Sub-programs where Revenue > Expense render with a soft GREEN tint
   and `$X ↑`.  Combined tab title shows both totals when both
   exist: `Combined · subsidy $19,213 · surplus $14,000`.

5. **Threshold sliders** — labels read just `Revenue over-budget
   threshold (%)` (no live percentage suffix).  No italic hint
   line under the slider.  The entry box on the right still shows
   and accepts the typed value.

---

## Cross-FS sync gotcha hits this round

Three: `toolkit/shell.py`, `tools/sub_program/frame.py`, and
`tools/sub_program/tests/test_frame.py` all truncated mid-edit on
the bash mount.  Recovered via the standard `head -n N file > /tmp ;
cat /tmp/head /tmp/tail > /tmp/full ; cp /tmp/full file ; touch file`
pattern.  One file ended with stray null bytes that needed
truncation before the file would parse.
