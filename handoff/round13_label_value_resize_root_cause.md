# Round 13 — Threshold value in label header + resize-lag root cause

**Date:** 2026-04-28
**Orchestrator:** Opus 4.7
**Builder:** Sonnet 4.6 (Agent O, ~128K tokens, 85 tool uses, ~8 min)
**Quality gates:** all green (ruff format, ruff check, mypy --strict 0 issues, pytest **424 passed / 51 skipped / 0 failed** in main scope)

---

## Two fixes landed

### Fix 1 — Threshold value in label header

The threshold input row's left-side label was static `"Over-budget threshold (%)"`. The right-side value was small and far away. User said it was hard to see.

The label is now a `tk.StringVar`-backed Label that shows `"Over-budget threshold (%): 101%"` and updates live as the slider/entry changes. Format: `f"{inp.label}: {value:.Nf}%"` where N derives from `RangeInput.step` (0 decimals when step >= 1). Bound to a trace on `actual_var` from Round 12.

This is in addition to the existing right-side rendering (slider · range labels · entry · `%` suffix · hint). Now the value is visible at both ends of the row — matching what the user asked for.

Tests: `test_range_input_label_includes_live_value`, `test_range_input_label_updates_on_value_change`.

### Fix 2 — Resize lag — root cause finally identified

Round 9 + Round 11 added 50ms `<Configure>` debouncing on `SelectableList` and on user_frame + per-tool canvas wrappers. The user reported it was STILL bad on every tool page. Round 13 finally found the structural issue.

**Root cause #1 (primary):** All tool frames were pre-`place(relwidth=1.0, relheight=1.0)`-ed at `_build_layout` time, with inactive ones `lower()`-ed. **Tk fires `<Configure>` on every placed child whenever the parent resizes — including lowered (invisible) ones.** With 5 tools each having a canvas + inner-frame `<Configure>` pair, that's 10 deferred handlers fanning out per resize tick (debounced to ~one per 50ms each, but still 10 separate `after()` schedules). The active tool's content was the ONLY one any user could see, but Tk was busy laying out the other 4.

**Root cause #2:** `Table.column(stretch=True)` was set on **every column** of the Treeview. Tk recomputes width for every stretch=True column on each resize tick. Sub-Program's table has 7 columns — 7× width recompute per tick. SRP's has 8 columns. Operating's has 8.

**Fixes:**

- `toolkit/shell.py::_build_layout` — removed the eager `frame.place(relwidth=1.0, relheight=1.0)` + `frame.lower()` loop. Frames are now built (widget tree exists) but **not placed** until activated.
- `toolkit/shell.py::_activate_tool` — replaced `frame.lower()` / `frame.lift()` with `frame.place_forget()` for inactive frames + `frame.place()` for the active one. Same pattern in `_show_unlock_cta` and `_activate_user_tab`.
- `toolkit/shell.py::_on_root_configure` (NEW) — 50ms debounce on root window's `<Configure>` event as a global safety net for any future resize work. `_root_configure_after: str | None` tracks the pending `after()` ID.
- `toolkit/primitives.py::Table.__init__` — column-stretch logic changed: only the **last** column gets `stretch=True`, all others fixed-width. Eliminates O(n_columns) per-tick reflow.

**Net effect:**

- During drag: previously O(n_tools × 2) Configure handlers fired per pixel → now only 1 (active tool's canvas + inner). Inactive frames are fully removed from Tk's geometry manager.
- Treeview width compute: O(n_columns) per tick → O(1).
- Sub-Program (worst case: 7-col table + side rail) should improve the most.

---

## Files changed

| File | What |
|---|---|
| `toolkit/shell.py` | `_build_range_widget` live label; `_build_layout`/`_activate_tool`/`_show_unlock_cta`/`_activate_user_tab` switched to `place()`/`place_forget()` pattern; `_on_root_configure` debounce |
| `toolkit/primitives.py` | `Table.__init__` only last column stretches |
| `tests/test_primitives.py` | 3 new tests (label + Table stretch) |
| `tests/test_shell_smoke.py` | 1 new test (inactive frames not placed) |

---

## Final quality gates

```
ruff format --check ........ 64 files already formatted
ruff check ................. All checks passed!
mypy --strict .............. Success: no issues found in 64 source files
pytest (excl. Operating) ... 424 passed, 51 skipped, 0 failed
Operating tests ............ 9 failed, 24 passed, 12 errors (PRE-EXISTING — missing
                              "Samples/Operating Statement/GL21150_Operating Statement
                              Detailed.pdf"; actual files have Feb/Mar suffixes)
```

---

## How to verify on Windows

1. Restart School Tool to pick up Round 13.
2. Open any tool. Drag the window edge from narrow to wide repeatedly. Should feel **smooth on every tab** (HYIA, Master Budget, SRP, Sub-Program, Operating).
3. The Sub-Program page with a loaded report (rail + 7-col table) is the worst stress test — if that's smooth, everything is.
4. Check the threshold row: label on the left should show `"Over-budget threshold (%): 101%"` updating as you drag the slider or type in the box. Value on the right shows `[ 101 ] %` with the same number.

---

## Pending items

- **Operating sample PDFs** — 12 setup errors in `tools/operating/tests/test_logic.py` reference `'Samples/Operating Statement/GL21150_Operating Statement Detailed.pdf'` which doesn't exist. The actual files are `GL21150_Operating Statement Detailed Feb.pdf` and `GL21150_Operating Statement Detailed Mar.pdf`. Either rename the sample files or fix the test fixture path. Not orchestrator work — small fix when convenient.
- **Mailer FROM** — gmail.com still rejected by Resend; manual `/verify-email` curl works.
- **Argon2 in Workers** — degraded to PBKDF2-100k.
- **M4** — paused.
- **M8 — Camps** — blocked on samples.
