# Round 29 — Hide Clear button on Refined PAL Search

**Date:** 2026-05-02
**Scope:** Tiny one-flag UX cleanup — Refined PAL Search no longer
shows the shell's `Clear` button.

---

## User ask

> don't need clear button in Refined PAL search

Refined PAL Search is a pure launcher tool: no inputs, no result table,
no output file. The shell's automatic `Clear` button has nothing to do
on it, so it just adds visual noise next to the big primary button.

---

## Change

New optional class-level attribute `show_clear_button: bool = True`
(default). Tools that set it to `False` get rendered without the
shell-level `Clear` button.

`RefinedPalSearchTool` opts out:

```python
show_clear_button = False
```

The shell's render code now wraps the existing Clear button in a
`getattr(tool, "show_clear_button", True)` guard, so every existing
tool keeps its Clear button without code changes.

---

## Files touched

```
MOD   toolkit/shell.py
       - _build_tool_frame: Clear button render wrapped in
         ``if getattr(tool, "show_clear_button", True):``

MOD   tools/refined_pal_search/frame.py
       - new class attribute: show_clear_button = False
```

---

## Quality gates

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 70 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 543 passed, 66 skipped (env)
```

---

## What to manually verify on Windows

1. Open Refined PAL Search. Action row shows just the big
   "Open Refined PAL Search" button — no Clear button next to it.
2. Open any other tool (HYIA, Master Budget Compass Autofill,
   Sub-Program Budget Report). Action row still ends with the Clear
   button as before.
