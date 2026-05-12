# Round 10 — Threshold slider + two-phase Generate/Export workflow

**Date:** 2026-04-27
**Orchestrator:** Opus 4.7
**Builder:** Sonnet 4.6 (Agent L, ~62K tokens, 203 tool uses, ~21 min) + orchestrator inline cleanups
**Quality gates:** all green (ruff format, ruff check, mypy --strict 0 issues, pytest **468 passed / 42 skipped / 0 failed**)

---

## What landed

### New shell surface

- **`RangeInput`** frozen dataclass added to `toolkit/base_tool.py`:
  ```python
  @dataclass(frozen=True)
  class RangeInput:
      key: str
      label: str
      min_value: float
      max_value: float
      default: float
      step: float = 1.0
      live: bool = True
  ```
  Added to the `InputSpec` discriminated union.

- **`BaseTool.preview_update(key, value) -> ToolResult | None`** Protocol method, default returns None.

- **Slider rendering** in `toolkit/shell.py::_build_range_widget`: `ttk.Scale` with a live numeric value label that updates as the user drags. When `live=True`, the slider's variable trace fires a debounced (100 ms `after()` cancel-and-reschedule) callback that calls `tool.preview_update(key, value)`. If the tool returns a ToolResult, `_render_result` is invoked.

- **`_set_inputs_state(tid, state)`** new method to disable inputs during run, including special handling for the Scale widget inside the RangeInput container.

- **Per-tool dict** `self._range_debounce: dict[str, dict[str, str]]` tracks `after()` IDs so successive drag events cancel the previous pending callback.

### Sub-Program two-phase workflow

`tools/sub_program/frame.py`:

- Threshold input is now `RangeInput("over_budget_threshold", "Over-budget threshold (%)", min_value=0, max_value=300, default=101.0, step=1.0, live=True)` — slider with a live value badge.
- `run()` parses + caches: `self._cached_summary = summary`, `self._cached_threshold = threshold`. **No XLSX written.**
- New `preview_update(key, value)` method recomputes `is_over` flags via `logic._recompute_is_over(summary.lines, threshold=value)`, builds a fresh `ReportSummary`, and returns a new `ToolResult` for live re-render. Returns None if no cached summary (user hasn't clicked Generate yet).
- New `_export_xlsx()` secondary action writes the XLSX using `_cached_summary` + `_cached_threshold`. Output path auto-derives next to source PDF (Round 9 Fix 4 logic moved here).
- `secondary_actions()` returns `[("Edit commentary...", ...), ("Export to Excel", ...), ("Open output folder", ...)]` — the Export to Excel button is the new explicit "write the file" trigger.
- `clear()` extended to reset `_cached_summary = None` and `_cached_threshold = 101.0` alongside the existing reset of `_last_summary`, `_commentary_overrides`, `_last_output_path`.

`tools/sub_program/logic.py`:

- `generate_report(...)` gains a `write_xlsx: bool = True` parameter. When False, `_write_xlsx` is skipped and progress reports "Preparing preview…" instead of the write step. Sub-Program's `run()` calls with `write_xlsx=False`; its `_export_xlsx` calls `_write_xlsx` directly.

### Other tools

- `tools/hyia/frame.py`, `tools/master_budget/frame.py`, `tools/srp/frame.py`, `tools/operating/frame.py` — explicit `preview_update(self, key, value): return None` declarations added (Protocol structural-type rule from Round 8 H precedent).
- `tests/test_registry.py::_StubTool` — same explicit no-op for the test stub.

---

## Files changed

| File | Net Δ | What |
|---|---|---|
| `toolkit/base_tool.py` | +24 | `RangeInput` dataclass + Protocol `preview_update` method |
| `toolkit/shell.py` | +110 | `_build_range_widget`, `_set_inputs_state`, `_range_debounce`, `_run_tool`/`_render_result` integration |
| `tools/sub_program/frame.py` | +60 / -10 | `RangeInput` instead of `NumberInput`, `preview_update`, `_export_xlsx`, secondary_actions reorder, `clear()` extension |
| `tools/sub_program/logic.py` | +5 | `write_xlsx: bool = True` param on `generate_report` |
| `tools/hyia/frame.py`, `tools/master_budget/frame.py`, `tools/srp/frame.py`, `tools/operating/frame.py` | +3 each | explicit `preview_update` no-op |
| `tests/test_base_tool.py` | +60 | 7 new RangeInput tests + preview_update default test |
| `tests/test_primitives.py` | +35 | 2 RangeInput rendering tests (Tk-skip) |
| `tests/test_shell_smoke.py` | +35 | RangeInput integration test |
| `tests/test_registry.py` | +3 | _StubTool.preview_update no-op |
| `tools/sub_program/tests/test_frame.py` | +180 | TestTwoPhasePreviewExport (11 tests) |

---

## Final quality gates

```
ruff format --check ........ 64 files already formatted
ruff check ................. All checks passed!
mypy --strict .............. Success: no issues found in 64 source files
pytest tests/ tools/ ....... 468 passed, 42 skipped, 3 warnings in 24.50s
port_tokens.py --check ..... OK: tokens.py in sync with CSS
```

Baseline at start of round: 448 / 41 / 0. After Round 10: 468 / 42 / 0 (+20 tests, +1 skip).

---

## Recovery work this round (cross-FS sync)

The bash mount truncated `toolkit/shell.py` at line 1559 (lost ~135 lines including `_set_inputs_state`, `_handle_tk_exception`, `rail_item_ids`, `active_tool_id`, `_small_font`, `_rail_font`, `_group_header_font` definitions). mypy then reported 14 "no attribute" errors against these methods.

Fix: read the missing tail from Windows-side via Read tool, append to bash via Python heredoc, `touch` to invalidate Python's mtime cache. After the rewrite, mypy went from 14 errors to 1 (an unused `# type: ignore[assignment]` on the slider's `after_id` assignment), which I removed.

Plus a final null-byte cleanup pass: 28 trailing nulls after the new tail had to be `rstrip(b'\\x00')`-ed before quality gates would settle.

CLAUDE.md gotcha is now hitting **every** round. Worth a defensive automation effort — a post-write verifier that hashes the file from both sides and refuses to proceed on mismatch.

---

## What the user will see when they next run the tool

1. Restart School Tool to pick up Round 10.
2. Open Sub-Program Budget Report. Inputs are now: Sub-Program report (file) · Prior-period comments (file) · **Over-budget threshold (%) — slider, default 101**.
3. Pick the report PDF (and optionally the comments file). Set the slider to your starting threshold (or leave at 101).
4. Click **Generate report**. The tool parses the PDF, displays the result panel (banner + faculty rail + table), but **does not write the XLSX yet**.
5. **Drag the threshold slider.** The value label next to it updates live; ~100 ms after you stop, the result panel re-renders with the new threshold applied — over-budget rows in the table re-color, faculty rail `highlight` flags refresh, banner count updates.
6. When you're happy with the threshold, click **Export to Excel** (secondary button next to Edit commentary…). The XLSX writes next to the source PDF as `Annual_SubProgram_<stem>_AUTO_<YYYYMMDD_HHMM>.xlsx` and `_last_output_path` is set so **Open output folder** opens Explorer at the right location.
7. **Clear** also resets the cached summary + threshold; next Generate starts fresh.
8. Re-running Generate replaces the cache; subsequent slider drags use the new run's data.

---

## Pending items (post Round 10)

- **Mailer FROM** — gmail.com still rejected by Resend; manual `/verify-email` curl works as test-account unblock.
- **Argon2 in Workers** — degraded to PBKDF2-100k for pilot.
- **Cross-FS sync defensive script** — bash-mount truncation hits every round now. Worth automating a post-write verifier that catches truncation BEFORE the agent reports "done".
- **M4** (admin dashboard, invoicing, credits) — paused since Round 6.
- **M8** — Camps Reconciliation — blocked on sample exports.
- **Operating Statement / SRP** — could optionally adopt the same slider-preview pattern in a future round if desired (Operating already has `$ threshold` + `% threshold` fields that could become sliders).
