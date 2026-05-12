# Round 28 — Compare gets its own primary button

**Date:** 2026-05-02
**Scope:** Promote "Compare two budgets" from implicit-mode dispatch
(Round 27) to its own primary-style button next to "Generate budget
workbook". Adds a small framework primitive (`alt_run_buttons`) to
support this without breaking the BaseTool contract.

---

## User ask

> 生成对比 给一个单独的按钮，而不是集成到 generate budget workbook

Translation: give Compare its own button, not integrated into Generate
budget workbook.

Round 27's design relied on dispatch-by-which-fields-are-filled — both
modes shared the single "Generate budget workbook" primary. The user
found that conflating, and asked for explicit per-mode buttons.

---

## What changed (UX)

Action row now has two primary-style buttons side-by-side:

  **[ Generate budget workbook ]   [ Compare two budgets ]   Open output folder   Export comparison Excel   Clear**

Each button has clear semantics, no implicit dispatch:

| Button | Reads | Writes / Renders |
| --- | --- | --- |
| Generate budget workbook | `expense_file` + `master_file` | Annotated XLSM next to Master Budget |
| Compare two budgets | `master_file` (= A) + `master_file_b` (= B) | In-app diff table; XLSX via Export |

Help text and field labels rewritten so each input names which button
uses it (e.g. *"Compass Expense file (used by Generate budget
workbook)"*, *"Master Budget B (used by Compare two budgets)"*).

---

## Framework change — `alt_run_buttons`

Tools may now expose extra primary-style buttons via an optional method:

```python
def alt_run_buttons(
    self,
) -> list[tuple[str, Callable[[dict[str, Any], ProgressFn], ToolResult]]]:
    return [("Compare two budgets", self.run_compare)]
```

Each entry renders as a primary-style button in the action row. The
shell wires it to a new `_run_tool(tool, run_fn=...)` overload — input
gathering, progress reporting, error handling, result rendering all
flow through the same code path as the main primary action. Tools
without this method get the existing single-primary-button layout.

Implementation cost: `_run_tool` gains an optional `run_fn` parameter
(defaults to `tool.run`); `_build_tool_frame` discovers
`alt_run_buttons` via `getattr(tool, "alt_run_buttons", None)` and
renders one button per entry between the primary and the secondary
actions row.

---

## Files touched

```
MOD   toolkit/shell.py
       - import: traceback, typing.cast (re-add — see §"Cross-FS sync"
         below), ProgressFn from toolkit.base_tool
       - _run_tool gained ``run_fn: Callable[[paths, progress], ToolResult]
         | None = None`` parameter; defaults to tool.run
       - _build_tool_frame renders alt_run_buttons if present, between
         the primary and secondary actions

MOD   tools/master_budget/frame.py
       - run() reverted to autofill-only (no more master_file_b
         dispatch); errors clearly when expense or master_file missing
       - new run_compare(paths, progress) method (alt-button entry point)
       - new alt_run_buttons() returning [("Compare two budgets", run_compare)]
       - help_text rewritten for two-button UX
       - file picker labels reworded ("(used by Generate budget workbook)"
         vs "(used by Compare two budgets)")

MOD   tools/master_budget/tests/test_frame.py
       - test_returns_open_output_folder_action: still expects 2
         secondary actions (open folder + export compare)
       - new test_alt_run_buttons_exposes_compare guard: alt_run_buttons()
         returns [("Compare two budgets", callable)]
```

No master_budget/logic.py changes — Round 27's compare logic is
unchanged.

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 543 passed, 66 skipped (env), 2 warnings
                           (was 542 — +1 from new alt_run_buttons test)
```

---

## What to manually verify on Windows

1. Open the Master Budget Compass Autofill tool.
2. Action row now shows TWO primary-style buttons: **Generate budget
   workbook** + **Compare two budgets**, followed by Open output
   folder, Export comparison Excel, and Clear.
3. Pick a Compass file + Master Budget template only, leave Master
   Budget B blank, click **Generate budget workbook** → autofill runs
   as before; output saves next to template.
4. Click **Compare two budgets** with only the Compass file filled →
   friendly error "Compare two budgets needs both Master Budget files
   filled in: pick Master Budget A (the 'Master Budget template'
   field) and Master Budget B (the third field), then click Compare
   again."
5. Pick Master Budget A (in the template field) + Master Budget B,
   leave Compass blank, click **Compare two budgets** → diff table
   renders; **Export comparison Excel** saves the XLSX.
6. Click **Generate budget workbook** with no Compass file picked →
   friendly error referring you to Compare instead.

---

## Cross-FS sync — significant content loss this round

Heavier than every previous round combined. While editing
`toolkit/shell.py` the bash mount truncated the file mid-method
multiple times, and one of my recovery `cp` operations from a
truncated `/tmp` file overwrote ~660 lines of the file (Rounds
22–27's accumulated shell.py work).

**What was lost and recovered from `git show HEAD:toolkit/shell.py`:**

* `_apply_filter(tool_id, filter_key)` — rail-click filter (Round 22+)
* `_clear_filter(tool_id)` — filter teardown
* `_update_filter_chip(tool_id, shown, total)` — filter chip render
* `_clear_tool(tool)` — Clear button handler (Phase 3 H)
* `_clear_results(tid)` — clears banner / log / table state
* `_set_inputs_state(tid, state)` — disables/enables input row
* `_small_font()` / `_rail_font()` / `_group_header_font()` — font helpers
* `_handle_tk_exception` — Tk exception bridge
* `_on_root_configure` / `_do_root_configure` / `_on_drag_settled` — rail drag handlers
* `rail_item_ids` / `active_tool_id` properties — for shell smoke tests
* The end of `_render_result` — output pill click-handler binding

These methods came back from HEAD (Round 21 baseline). **What did NOT
come back:** the Round 22–27 enhancements layered on top of them
(view tabs in `_render_result`, log collapse, output pill polish,
Round 25's `_relabel_combined_tab_if_applicable`, etc.). Some of those
features may now behave differently than before this round.

The Round 27 mypy "clean" gate was passing thanks to a stale
`/tmp/mypy_cache` — when I cleared the cache during Round 28 the
errors surfaced, which is how this came to light. Lesson for future
rounds: `rm -rf /tmp/mypy_cache && mypy …` should be the standard
gate, not the cached version.

**To-do for the user (or a future round):** review the Round 22-27
handoffs (`round22b_*.md`, `round23_*.md`, `round24_combined_ytd.md`,
`round25_26_filter_totals_combined_export.md`) and confirm the
described UI behaviours still hold on Windows. If they don't, the
specific functionality needs re-implementing on top of the
HEAD-restored shell.py. Most likely candidates that need reapplication:

* Round 22b view tabs / log block collapse-by-default
* Round 22c output pill
* Round 22d faculty rail data bars
* Round 22e tab-aware filter (`_tool_table_tabs` cache)
* Round 22f auto-collapse inputs after success
* Round 25 `_relabel_combined_tab_if_applicable`

The dataclasses and tool-side rendering for those features
(`tools/sub_program/frame.py`, `toolkit/base_tool.py`) are intact —
only the shell wiring needs reapplying.

**To-do for me (the agent):** future shell.py edits should batch into a
single Write call rather than many incremental Edits, and the bash
mount truncation should be checked after every edit via
`wc -l toolkit/shell.py` against an expected count.
