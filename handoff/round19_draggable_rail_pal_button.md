# Round 19 — Draggable left rail + larger PAL Search button

**Date:** 2026-04-29
**Scope:** Two UX polish requests on the v2.1.x free-tier shell. Both are
deliberate exceptions to the locked-by-design surfaces from ADR-0014, made
because real users hit limits the original spec didn't anticipate.

---

## What changed

### 1. Draggable left rail (`toolkit/shell.py::_build_layout`)

The rail used to be a fixed 220 px `tk.Frame` packed into the body. Long tool
labels and group headers had to fit inside that width, with no way for the
user to make room.

The body's horizontal split now uses a `tk.PanedWindow`:

```python
self._body_paned = tk.PanedWindow(
    self._body_frame,
    orient=tk.HORIZONTAL,
    sashwidth=4,
    sashrelief=tk.FLAT,
    bg=tokens.BORDER_SUBTLE,
    borderwidth=0,
    showhandle=False,
    opaqueresize=False,
)
self._body_paned.pack(side="left", fill="both", expand=True)

self._rail_frame = self._build_rail(parent=self._body_paned)
self._content_outer = tk.Frame(self._body_paned, bg=tokens.BG_MUTED)

self._body_paned.add(self._rail_frame, minsize=180, stretch="never")
self._body_paned.add(self._content_outer, minsize=400, stretch="always")
```

Properties preserved:

- **220 px default**: rail is still built with `width=220` + `pack_propagate(False)`,
  so the PanedWindow uses 220 as its initial sash position.
- **180 px floor**: `minsize=180` stops the rail from collapsing past the
  point at which tool labels truncate.
- **400 px content floor**: `minsize=400` keeps the action button row visible
  even if a user drags the rail very wide.
- **No window-resize drift**: rail has `stretch="never"`, content has
  `stretch="always"`, so the rail width stays as the user left it when the
  window itself resizes.
- **Sash colour matches the existing 1 px right border** (`BORDER_SUBTLE`),
  so the divider is visually identical to the previous static border.

`_build_rail` now takes an optional `parent` argument (defaults to
`self._body_frame` for backward compatibility) so the existing internal
structure (border + scroll_container) is untouched. Existing tests that
walk `_rail_frame.winfo_children()[1]` still work.

### 2. Larger PAL Search button

Two changes — a generic shell hook plus a per-tool opt-in:

**Shell side** (`toolkit/shell.py::_build_layout`)

```python
_style.configure(
    "Large.Accent.TButton",
    font=(self._fonts.sans_family, tokens.FS_14, "bold"),
    padding=(tokens.SP_4, tokens.SP_3),  # 16 px horizontal, 12 px vertical
)
```

**Shell side** (`toolkit/shell.py::_build_tool_frame`)

```python
_primary_style = getattr(tool, "primary_button_style", "Accent.TButton")
primary_btn: ttk.Button = ttk.Button(
    btn_inner,
    text=tool.primary_button,
    command=lambda t=tool: self._run_tool(t),
    style=_primary_style,
)
```

The `getattr` keeps every existing tool unchanged — none of them declare
`primary_button_style`, so they all stay on the standard `Accent.TButton`.

**Tool side** (`tools/refined_pal_search/frame.py`)

```python
class RefinedPalSearchTool:
    ...
    primary_button = "Open Refined PAL Search"
    primary_button_style = "Large.Accent.TButton"
    ...
```

Reusable for any future launcher-style tool that has a single, oversized CTA.

---

## Why these are deliberate ADR-0014 exceptions

`docs/02_ARCHITECTURE.md` ADR-0014 lists the left rail's 220 px fixed width
and the per-tool action row sizing as locked surfaces — changing them needs
a deliberate design decision. Both changes here qualify:

- Rail width: user explicitly requested it; default + minsize preserve the
  original visual intent.
- PAL Search button: launcher tools have a fundamentally different shape
  (single CTA, no inputs) than the rest of the toolkit. The original 4×3 px
  padding made the one button look lonely on a mostly-empty pane. The
  larger style stays opt-in via `primary_button_style`, so the broad rule
  ("primary = Accent.TButton") still holds for the 99% case.

If a third tool ever wants the bigger button, no shell changes are needed —
just set `primary_button_style = "Large.Accent.TButton"` on the class.

---

## Files touched

```
toolkit/shell.py
  - register Large.Accent.TButton style at _build_layout entry
  - replace pack-side body layout with tk.PanedWindow
  - _build_rail accepts optional parent= argument
  - _build_tool_frame reads tool.primary_button_style via getattr

tools/refined_pal_search/frame.py
  - add primary_button_style = "Large.Accent.TButton"

tools/refined_pal_search/tests/test_frame.py
  - new TestStructuralConformance.test_primary_button_style_is_large

tests/test_shell_smoke.py
  - test_body_uses_paned_window — body wraps rail+content in tk.PanedWindow
  - test_rail_default_width_preserved — rail.cget('width') == 220
  - test_large_accent_button_style_registered — style.lookup returns config
  - test_default_tool_uses_accent_tbutton_style — backward-compat regression
```

---

## Quality gates

All green:

```
ruff format --check .          → 75 files already formatted
ruff check .                    → All checks passed!
mypy --strict toolkit/ tools/ tests/  → no issues found in 68 source files
pytest --ignore=tools/operating/tests/test_logic.py
                               → 494 passed, 66 skipped, 1 warning
```

The 13 skips on the new test_shell_smoke tests are CI-environment skips —
the Linux sandbox has no `tkinter` module, so all Tk smoke tests skip
gracefully. They run on Windows where the live shell renders.

The pre-existing failures in `tools/operating/tests/test_logic.py` (12 errors
+ 7 failures) are **unrelated** to Round 19 — they look for
`Samples/Operating Statement/GL21150_Operating Statement Detailed.pdf` but
the Samples folder only contains `…Feb.pdf` and `…Mar.pdf`. The Operating
Statement tool is parked under "In development" anyway (Round 15 decision),
so the test file's path mismatch is a pre-existing data drift to fix when
the tool is unparked.

---

## What did not change

- Rail's internal structure (border + scroll_container + group labels) is
  untouched.
- `_content_outer` is still the parent for tool frames, the unlock CTA frame,
  and the user frame. All existing `place(in_=self._content_outer, ...)`
  calls continue to work.
- Default tools (HYIA, Master Budget, Sub-Program, SRP Compare) still render
  with the standard `Accent.TButton`.
- No version bump — the changes ship in the next 2.1.x build.

---

## Cross-FS gotcha hit again

`tests/test_shell_smoke.py` truncated on the bash mount mid-write while the
Windows-side Read tool showed the full file. Recovered via the standard
`/tmp/<file>` + `cp` + `touch` pattern from CLAUDE.md. Worth noting: a
mypy `--strict` run with a stale `.pyc` cache reported a `[no-untyped-call]`
error on a line that no longer existed in the Windows view; clearing the
mypy cache (`rm -rf /tmp/mypy_cache`) and rebuilding the file via /tmp
resolved both the truncation and the phantom error.

---

## What to validate manually on Windows

The Tk smoke tests skip on Linux CI, so the user should sanity-check:

1. **Rail drag**: open the app, hover the right edge of the rail, the cursor
   should change to a horizontal-resize cursor; drag left/right; release;
   the rail keeps the new width and content area absorbs the rest.
2. **Rail floor**: try dragging the rail past 180 px to the left — it should
   stop.
3. **PAL Search**: click the Refined PAL Search entry in the rail; the
   "Open Refined PAL Search" button should be visibly larger than the action
   buttons on the other tools (bigger font, more padding).
4. **Other tools unchanged**: open HYIA, Master Budget, Sub-Program, SRP —
   their primary buttons should look exactly as before.
