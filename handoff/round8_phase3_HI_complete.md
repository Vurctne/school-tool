# Round 8 Phase 3 H + I — Clear button + click-to-filter complete

**Date:** 2026-04-27
**Orchestrator:** Opus 4.7
**Builders:** Sonnet 4.6 — Agent H (~102K tokens, 7 min) + Agent I (~163K tokens, 13 min) + orchestrator inline fixes
**Quality gates:** all green (ruff format, ruff check, mypy --strict, pytest **434 passed / 38 skipped / 0 failed**)

---

## Phase 3 — ADR-0015 implementation status

| Step (per ADR §11) | Status | Owner |
|---|---|---|
| 1. Extend ToolResult + add RailItem/TableSpec | ✅ done | F |
| 2. Extract SelectableList from CommentaryDialog | ✅ done | F |
| 3. Extend Table primitive with row_style + on_row_click | ✅ done | F |
| 4. Extend `_render_result` with conditional 2-col branch | ✅ done | F |
| 5. Refactor Sub-Program to populate the new fields | ✅ done | G |
| 6. Add Open output folder to secondary_actions() | ✅ done | G |
| 7. Click-to-filter wiring inside Sub-Program's frame | ✅ done | I |
| (Bonus) Clear button — shell-level convention | ✅ done | H |
| (Beyond ADR) Sub-Program XLSX export rewrite to Jan26 spec | ✅ done | J |

**Sub-Program design fidelity is feature-complete** end-to-end.

---

## What landed this round

### Phase 3 H — Clear button

- New `BaseTool.clear()` Protocol method (default no-op) — tools override to reset session state.
- Shell-level **Clear** button rendered as the LAST item in every tool's action row (per design).
- `TkShell._clear_tool(tool)` performs an 8-step UI reset: file pickers + `_input_cache`, banner, progress bar, metrics, log, table, primary button re-enable, then `tool.clear()`.
- Tool overrides:
  - `tools/sub_program/frame.py` — resets `_last_summary`, `_commentary_overrides`, `_last_output_path`
  - `tools/master_budget/frame.py` — resets `_last_output_path`
  - `tools/hyia/frame.py`, `tools/srp/frame.py`, `tools/operating/frame.py` — explicit no-op (Protocol implementors don't inherit defaults)

### Phase 3 I — Click-to-filter on faculty rail

- Click a rail row → `_on_rail_select(filter_key)` fires → `_apply_filter(tool_id, filter_key)` filters cached `TableSpec.rows` by `row["_faculty"] == filter_key` → `Table.set_rows(filtered)` re-renders → `SelectableList.set_active(filter_key)` highlights the active rail row in blue.
- **Footer chip** below the table: `"Showing 12 of 84 — clear filter ×"` when filter is active. Clicking the × clears the filter.
- Shell-level Clear button (Phase 3 H) also clears the active filter.
- New ToolResult (e.g. re-run Generate report) resets the filter state and hides the stale chip.
- Filter is **transient shell-side state**, not in `ToolResult` — original `TableSpec.rows` is never mutated; filtered rows derived fresh each time.

### New shell state slots

```python
self._tool_filter: dict[str, str | None] = {}        # tool.id → active filter_key
self._tool_table_specs: dict[str, TableSpec] = {}     # tool.id → original TableSpec (for filter re-derive)
self._tool_rails: dict[str, SelectableList] = {}      # tool.id → rail widget
self._tool_filter_chips: dict[str, tk.Frame] = {}     # tool.id → chip frame
```

### New shell methods

- `_filter_rows(rows, filter_key)` — pure function, module-level. Extracted for CI-testability without Tk.
- `_apply_filter(tool_id, filter_key)` — applies the filter; updates table + rail + chip.
- `_clear_filter(tool_id)` — restores full row set; clears active rail row; hides chip.
- `_update_filter_chip(tool_id, shown, total)` — renders or hides the chip.
- `_clear_tool(tool)` — extended with step 8 to also reset filter state.

---

## Files changed (H + I combined)

| File | Net Δ | What |
|---|---|---|
| `toolkit/base_tool.py` | +12 | `clear()` Protocol method on BaseTool |
| `toolkit/shell.py` | +231 | Clear button, `_clear_tool`, filter state, `_apply_filter`, `_clear_filter`, chip widget, `_filter_rows` pure function |
| `tools/sub_program/frame.py` | +12 | `clear()` override resets session caches |
| `tools/master_budget/frame.py` | +8 | `clear()` override resets `_last_output_path` |
| `tools/hyia/frame.py` | +4 | explicit no-op `clear()` |
| `tools/srp/frame.py` | +4 | explicit no-op `clear()` |
| `tools/operating/frame.py` | +4 | explicit no-op `clear()` |
| `tests/test_shell_clear.py` | NEW (+179) | 5 tests for `clear()` behaviour across tools |
| `tests/test_primitives.py` | +266 | 4 pure-logic + 7 Tk-gated tests for filter wiring |
| `tools/sub_program/tests/test_frame.py` | +31 | TestClearResetsState class |
| `tests/test_registry.py` | corrupted-and-restored | `_StubTool` now declares `clear() -> None`; final test rewritten after ruff format truncation |

---

## Recovery work (cross-FS sync issue, again)

The CLAUDE.md gotcha bit Phase 3 H particularly hard:

| File | Damage | Fix |
|---|---|---|
| `tools/srp/frame.py` | Truncated mid-`_guess_year` body (line 309 incomplete) | Read full content from Windows side, append missing tail via Python heredoc, `touch` to invalidate Python's mtime cache |
| `tools/operating/frame.py` | bash mount didn't pick up the Edit tool's `clear()` addition | Force-touch + retry |
| `tests/test_registry.py` | After a ruff format pass, last test (`test_register_does_not_affect_other_tools_in_registry`) truncated mid-assertion at `_registere` (missing `d` and rest of test) | Rewrote test body via bash Python heredoc |

This gotcha is now hitting **every** Phase-3 dispatch. Worth investing in a defensive script next session — e.g. a post-write verifier that hashes the file from both sides and refuses to proceed on mismatch. Tracked as a follow-up.

---

## Final quality gates

```
$ python3 -m ruff format --check toolkit/ tools/ tests/
64 files already formatted

$ python3 -m ruff check toolkit/ tools/ tests/
All checks passed!

$ python3 -m mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
Success: no issues found in 64 source files

$ python3 -m pytest tests/ tools/ --tb=line -q
434 passed, 38 skipped, 1 warning in 19.24s

$ python3 scripts/port_tokens.py --check
OK: toolkit/tokens.py is in sync with the CSS.
```

38 skips break down to expected env-absent skips:
- 16× Tk-absent on Linux CI (test_primitives, test_shell_clear, test_shell_smoke, test_user_frame, test_clear_button_in_action_row_tk, the 7 new I-tests)
- 1× pywin32 Windows-only (master_budget integration)
- ~21 other Tk/pywin32 environmental skips

---

## What the user will see when they next run the tool

1. Restart School Tool to pick up the code changes.
2. **Every tool's action row now ends with a Clear button** — last position, after Generate + secondary actions.
3. Open Sub-Program Budget Report, run a real GL21157 PDF.
4. Result panel shows the 220 px faculty rail on the left + 7-col table on the right (per Phase 3 F+G).
5. **Click any faculty in the rail** — the table immediately filters to show only that faculty's lines, and the clicked row gets a blue highlight in the rail.
6. **A chip appears below the table**: "Showing 12 of 84 — clear filter ×".
7. Click the × → filter clears, table returns to all rows, chip disappears, rail row deselects.
8. Click the **Clear button** → file pickers, banner, log, table, rail, and filter all reset.
9. Generate report again → filter starts fresh.

The exported XLSX (Phase 3 J) is unaffected by the in-app filter — exports always include all rows.

---

## Pending items (post Phase 3)

- **Mailer FROM** — still using gmail.com which Resend rejects; manual `/verify-email` curl still needed for any new test accounts. Stopgap: switch to `onboarding@resend.dev`. Production: verify `schooltool.com.au` once registered.
- **Argon2 in Workers** — currently falling back to PBKDF2-100k (security degraded but acceptable for pilot).
- **Cross-FS sync defensive script** — every Phase-3 dispatch this round had at least one file truncated. Need an automated post-write verifier.
- **M4 — Invoice PDF + admin dashboard + PO upload UI** (with credit pricing per docs/06_PRICING.md). Paused since Round 6.
- **M8 — Camps Reconciliation** — blocked on sample exports.
