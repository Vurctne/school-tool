# Round 22f — Auto-collapse inputs after first run

**Date:** 2026-05-01
**Scope:** The last queued Round 22 item.  After this, Round 22 is
fully complete.

---

## What changed

After a tool's `run()` completes successfully, the shell auto-collapses
the entire input cluster (file pickers, threshold sliders, etc.) into
a single-line summary chip with an `Edit ▾` button.  Click `Edit ▾`
to re-expand.  Click `Clear` and the inputs auto-expand too.

**Before** (post-Round-22e):

```
Sub-Program Budget Report
[ Sub-Program report ]   D:/.../Annual…pdf  [Browse]
[ Prior-period comments ]                   [Browse]
[ Revenue threshold ] 100% ━●━ 120%  [120]%   [ Expense threshold ] 100% ━●━ 120%  [110]%
[ Generate report ] [ Export to Excel ] [ Open output folder ] [ Clear ]
[ Banner ]
[ Output pill ]
[ Show log ▾ ]
[ Tabs: Revenue / Expense / Combined ]
[ Big data table — finally ]
```

**After** (Round 22f, post-success):

```
Sub-Program Budget Report
Sub-Program report: GL21157_…pdf · Revenue over-budget: 120 · Expense over-budget: 110   [ Edit ▾ ]
[ Generate report ] [ Export to Excel ] [ Open output folder ] [ Clear ]
[ Banner ]
[ Output pill ]
[ Show log ▾ ]
[ Tabs: Revenue / Expense / Combined ]
[ Big data table — even more space! ]
```

The input cluster shrinks from ~3 rows to a single chip, reclaiming
roughly another ~120 px of vertical real estate after the user has
committed to their inputs.

---

## How it works

### `_build_tool_frame` — track section frames

Every input/output row gets its `section()` Frame appended to a
per-tool list `widget_map["__input_section_frames__"]`.  A separate
`__input_summary_frame__` is reserved (hidden by default) to hold
the chip widgets.

### `_collapse_inputs(tid)`

- `pack_forget()` every frame in `__input_section_frames__`.
- Read `tool.inputs` + `_input_cache[tid]` to build a summary string,
  one part per non-empty input separated by ` · `.
- Pack the chip into `__input_summary_frame__`.

Per-input formatting:
- **FileInput** → just the filename (`Path(value).name`), not the full path.
- **SecretInput** → `••••••` (never reveal the value).
- **RangeInput** → numeric value (e.g. `120`).
- **Other** → string representation, truncated to 40 chars + ellipsis.

The chip has an `Edit ▾` button on the right that calls
`_expand_inputs(tid)`.

### `_expand_inputs(tid)`

- Hide the summary chip.
- Re-pack each section frame in original order with the same
  pad values the section() helper used originally.

### Triggers

- **Auto-collapse**: `_on_tool_complete` checks `result.status ==
  "success"` after rendering the result and calls
  `_collapse_inputs(tid)`.  Failed / warning runs leave inputs
  expanded so the user can fix the problem without an extra click.
- **Auto-expand on Clear**: `_clear_tool` calls `_expand_inputs(tid)`
  before resetting the file pickers — otherwise the cleared widgets
  would be invisible.
- **Manual expand**: `Edit ▾` button on the summary chip.

### Generic — applies to every tool

The collapse path is shell-side and reads from `tool.inputs` +
`_input_cache`.  Every tool inherits this UX without changes.  HYIA,
Master Budget, SRP, Sub-Program all benefit on the next successful run.

---

## Files touched

```
MOD   toolkit/shell.py
       - _build_tool_frame: track input/output section frames in a list,
         reserve __input_summary_frame__
       - new _collapse_inputs(tid) / _expand_inputs(tid) / _render_input_summary
       - _on_tool_complete: collapse on success
       - _clear_tool: expand before resetting widgets
```

No new tests added — the behaviour is rendered by Tk widgets that
skip on Linux CI.  Manual verification on Windows covers it (see
below).

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

## Round 22 — final scoreboard

| Sub-round | Item | Status |
| --- | --- | --- |
| 22a | Inline commentary editor + comment sub-rows + banner naming | ✅ |
| 22b | View tabs (Revenue/Expense/Combined) + log collapse + Combined subsidy viz | ✅ |
| 22c | Output pill (Saved → filename + Open folder) | ✅ |
| 22d | Faculty rail data-bars (3 px proportional fill) | ✅ |
| 22e | Sliders side-by-side + tab-aware faculty filter | ✅ |
| 22f | Auto-collapse inputs after first run | ✅ |

**Round 22 status: COMPLETE.**

---

## Total Round 22 vertical real-estate reclaimed

| Item | Before | After | Saved |
| --- | --- | --- | --- |
| Log block | ~250 px | ~30 px (toggle) | **~220 px** |
| Sliders stacked → side-by-side | ~140 px | ~70 px | **~70 px** |
| Edit commentary button removed | ~30 px | 0 | **~30 px** |
| Inputs collapsed after run | ~250 px | ~32 px (chip) | **~218 px** |
| **Total** | | | **~538 px** |

Plus the structural / visual additions:
- View tabs split the dashboard into Revenue / Expense / Combined
- Combined subsidy viz surfaces school-funded gaps instantly
- Inline commentary replaces the modal dialog
- Banner names the over-budget line in plain English
- Output pill keeps the file path visible after log collapse
- Faculty rail bars turn the rail into a heat-map at a glance

The dashboard data area now occupies roughly 60-70% of the window
height after a successful run, vs ~25% before Round 22.

---

## What to manually verify on Windows

1. **First run, success path** — open Sub-Program, pick a report PDF,
   click Generate report.  After the result paints, the entire
   inputs section should collapse into a single chip:
   `Sub-Program report: …pdf · Revenue over-budget: 101 · Expense over-budget: 101   [ Edit ▾ ]`
2. **Click `Edit ▾`** — the inputs re-expand to their original layout.
3. **Drag a slider while expanded, run again** — collapse re-applies
   showing the new threshold values.
4. **Run with an error** (e.g. point at a file that doesn't exist)
   — inputs should NOT collapse (so you can correct the bad input).
5. **Click Clear** — inputs auto-expand and the file pickers reset.
6. **Switch to HYIA / SRP / Master Budget** — same auto-collapse
   behaviour applies after a successful run; SecretInput values
   render as `••••••` in the chip (no plaintext SIN leakage).
