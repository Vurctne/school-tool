# Round 22c — Output pill

**Date:** 2026-05-01
**Scope:** A single focused fix: surface the output filename + an
"Open folder" link as a small chip below the banner, now that the log
block (which used to carry the path) is collapsed by default after
Round 22b.  Sliders side-by-side, faculty rail data-bars, and
auto-collapse inputs are deferred to Round 22d.

---

## What changed

### Output pill widget

`toolkit/shell.py::_build_tool_frame` now reserves a small
`__output_pill_frame__` section between the banner and the metrics
row.  It starts hidden (`pack_forget`) and is only packed when
`_render_result` has a `result.output_path` that exists on disk.

When shown, the pill renders one line:

```
💾  Saved → Annual_SubProgram_GL21157_Annual…_AUTO_20260501_1200.xlsx   Open folder
```

- `💾  Saved →` prefix — `tk.Label` in muted FG_2.
- Filename only (`path.name`) — keeps the chip narrow even when the
  full path is deep.
- `Open folder` — clickable `tk.Label` styled as a navy pseudo-link.
  `<Button-1>` calls `toolkit.files.open_output_folder(path)`.
  `<Enter>` / `<Leave>` swap the font to underline-on-hover.

The pill respects the disk check (`Path.exists()`) so it never
appears for tools that emit `output_path` as a "would-save-here"
preview value rather than an actual saved file.

### Why this matters now

Round 22b collapsed the log block by default.  The "Output: D:\…"
log line — previously the user's only durable confirmation that
their report had been written and where — is now hidden until they
click `Show log ▾`.  Without the pill, users had to either click
`Open output folder` blindly (where does it open to?) or expand the
log just to see the filename.  The pill restores a one-glance
confirmation.

### Generic — not Sub-Program-specific

The pill lives in `_render_result`, so any tool that emits a
`ToolResult.output_path` pointing at an existing file gets it for
free: Master Budget Compass Autofill, SRP Comparison, Sub-Program,
and any future tool.

---

## Files touched

```
MOD   toolkit/shell.py
       - _build_tool_frame: __output_pill_frame__ section reserved
       - _render_result: pill rendered when result.output_path exists
         on disk; clickable Open folder link with hover underline
```

No new tests added — the pill is rendered by the shell and Tk smoke
tests skip on Linux CI.  Manual verification on Windows covers it
(see below).

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict toolkit/ tools/ tests/  → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 467 passed (no regressions)
pytest tools/sub_program/tests/test_frame.py
                         → 67 passed
```

---

## What remains (Round 22d / future)

- **Sliders side-by-side** — Revenue + Expense thresholds in one row
  sharing a hint line.
- **Auto-collapse inputs** after first run into a summary chip.
- **Faculty rail data-bars** behind each rail row scaled to usage %.
- **Tab-aware faculty filter** — currently disabled when tabs are
  present (rail click is a silent no-op).

---

## Cross-FS sync gotcha hits this round

Two truncations on `toolkit/shell.py` (the file is the largest in
the project — bash mount truncates at ~2300-2400 lines on each
edit).  Recovered via the standard `head -n N file > /tmp/head ;
cat /tmp/head /tmp/tail > /tmp/full ; cp /tmp/full file ; touch file`
pattern.

---

## What to manually verify on Windows

1. **Run Sub-Program Generate report** — the pill should NOT appear
   (file isn't written yet; only `Export to Excel` triggers a write).
2. **Click Export to Excel** — pill should appear below the banner
   showing `💾  Saved → {filename}.xlsx   Open folder`.
3. **Hover the "Open folder" link** — should underline.
4. **Click "Open folder"** — Windows File Explorer opens at the
   output folder with the file selected.
5. **Click Clear** — pill disappears (no output_path to render).
6. **Switch to a different tool then back** — pill state should
   reset cleanly per tool.
