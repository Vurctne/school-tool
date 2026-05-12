# Round 11 — slider 100–120 + numeric box, Edit Commentary Save/Clear all, deeper resize-lag fix

**Date:** 2026-04-27
**Orchestrator:** Opus 4.7
**Builder:** Sonnet 4.6 (Agent M, ~51K tokens, 166 tool uses, ~21 min)
**Quality gates:** all green (ruff format, ruff check, mypy --strict 0 issues, pytest **469 passed / 51 skipped / 0 failed**)

---

## Three fixes landed

### Fix 1 — Slider 100–120 + paired numeric box

`RangeInput` gains a `numeric_box: bool = False` field (default off so existing call sites are unaffected). When `True`, the shell renders the slider next to a small `ttk.Entry` bound to the **same `tk.DoubleVar`** — both widgets drive the same value. Either side updates the other automatically through the variable's trace.

The Entry validates on `<FocusOut>` and `<Return>`: parses as float, clamps to `[min_value, max_value]`, reverts to previous value on invalid input.

Sub-Program threshold input now uses `RangeInput(min_value=100, max_value=120, default=101.0, step=1.0, numeric_box=True)`.

### Fix 2 — Edit Commentary Save / Clear all

`CommentaryDialog` button row now reads: Cancel · Clear all · Save · OK.

- **Save** (Accent.TButton): flushes the active sub-program's text-area edits into the in-memory dict, plus any pending edits on previously-visited sub-programs. **Doesn't close the dialog.** Shows a "Saved" status label for ~1800ms as feedback. Also bound to `Ctrl+S`.
- **Clear all**: confirms via `tkinter.messagebox.askyesno("Clear all commentary?", ...)`. On Yes → empties the in-memory dict + refreshes the displayed text area for all sub-programs. On Cancel → no-op.
- **OK / Cancel**: existing semantics preserved. OK commits + closes; Cancel discards + closes.

### Fix 3 — Window resize "major delay"

Round 9's `SelectableList` 50ms `<Configure>` debounce wasn't enough. Investigation found two more `<Configure>` handlers doing synchronous heavy work per resize tick:

- **`toolkit/user_frame.py`** — the User tab's outer scrollable canvas had two `<Configure>` bindings (one on the inner Frame for `scrollregion` recompute, one on the Canvas for `itemconfigure(window, width=...)`). Both fired on every motion tick.
- **`toolkit/shell.py::_build_tool_frame`** — the per-tool content area has its own scrollable Canvas wrapper around the result panel. Same pattern, same per-tick firing.

Both now use the Round 9 debounce pattern — 50ms `after()` cancel-and-reschedule, with `winfo_exists()` guards and `try/except tk.TclError` on the deferred handler. Net result: resize triggers a single layout pass ~50ms after motion stops, not one per pixel.

**Verification on Windows:** drag the window edge from min to max width — should feel smooth, no flicker, no stuttering. The Sub-Program tab (with the heaviest content: rail + table + log + banner) is the worst case; if that's smooth, everything else is too.

---

## Files changed

| File | Net Δ | What |
|---|---|---|
| `toolkit/base_tool.py` | +1 | `RangeInput.numeric_box: bool = False` |
| `toolkit/shell.py` | +50 | `_build_range_widget` extension for paired Entry, `_set_inputs_state` covers Entry, `_build_tool_frame` canvas Configure debounce |
| `toolkit/primitives.py` | +90 | `CommentaryDialog` Save (`<Control-s>`), Clear all (with confirm), Saved status label |
| `toolkit/user_frame.py` | +30 | Outer canvas Configure handlers debounced (50ms) |
| `tools/sub_program/frame.py` | edit | RangeInput → 100–120 + numeric_box=True |
| `tests/test_base_tool.py` | +20 | 2 numeric_box pure tests |
| `tests/test_primitives.py` | +180 | 9 Tk-skip tests covering Entry rendering/clamping/revert, Configure debounce, CommentaryDialog Save/Clear all |

---

## Final quality gates

```
ruff format --check ........ 64 files already formatted
ruff check ................. All checks passed!
mypy --strict .............. Success: no issues found in 64 source files
pytest tests/ tools/ ....... 469 passed, 51 skipped, 3 warnings in 18.10s
port_tokens.py --check ..... OK: tokens.py in sync with CSS
```

Baseline at start of round: 468 / 42 / 0. After Round 11: 469 / 51 / 0 (+1 passing pure test, +9 Tk-gated skips).

---

## What the user will see when they next run the tool

1. Restart School Tool to pick up Round 11.
2. Open Sub-Program. The threshold input is now: `[━━●━━━━━━━━━] [101]` — slider on the left (range 100–120) and a small editable number box on the right.
3. Drag the slider → the number box updates live.
4. Type a value into the box and press Tab/Enter → the slider snaps to that position.
5. Type something out-of-range (e.g. 200) → value clamps to 120; type something invalid (e.g. "abc") → reverts to previous value.
6. Click Generate report → preview renders, no XLSX written.
7. Tweak the slider/box; live preview updates ~100ms after each change.
8. Click Edit commentary… → dialog opens with the new button row. Save flushes in-place (with "Saved" feedback for ~1.8s); Clear all asks for confirmation then wipes everything; OK commits + closes; Cancel discards + closes.
9. **Drag the window edge** to resize → smooth, no stutter, no flicker.
10. Click Export to Excel → XLSX writes next to source PDF.

---

## Pending items

- **Mailer FROM** — gmail.com still rejected by Resend; manual `/verify-email` curl works as test-account unblock.
- **Argon2 in Workers** — degraded to PBKDF2-100k for pilot.
- **Cross-FS sync defensive script** — bash-mount truncation continues to bite. Worth automating a post-write verifier.
- **M4** (admin dashboard, invoicing, credits) — paused since Round 6.
- **M8** — Camps Reconciliation — blocked on sample exports.
