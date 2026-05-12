# Round 8 Phase 3 F + G — complete (Sub-Program design fidelity, foundation + migration)

**Date:** 2026-04-26
**Orchestrator:** Opus 4.7
**Sub-agents:** F (Sonnet 4.6, ~140K tokens), G (Sonnet 4.6, ~84K tokens)
**Quality gates:** all green (ruff format, ruff check, mypy --strict, pytest 396/30/0)

---

## Result at a glance

The Sub-Program Budget Report tool now emits both the legacy `table_columns`/`table_rows` path
**and** the new `side_rail` + `table` (TableSpec) fields per ADR-0015. The shell renders the
2-col grid (220 px faculty rail | result table) when `side_rail` is populated; over-budget rows
get pink bg + danger-fg text via the new `row_style` callback. Master Budget's `Open output
folder` lifted into a shared `toolkit/files.py` helper with the OneDrive-safe single-string form;
Sub-Program now exposes the same action.

Click-to-filter wiring (rail row click → table filtered to that faculty) is **not yet wired** —
that's Agent I, the next dispatch.

---

## Files changed (Phase 3 F + G combined)

| File | Δ | What |
|---|---|---|
| `toolkit/base_tool.py` | +50 | `RailItem`, `TableSpec` (frozen), `side_rail` + `table` fields |
| `toolkit/primitives.py` | +340 / -150 | `SelectableList` extracted; `CommentaryDialog` refactored to use it; `Table` extended with `row_style` + `on_row_click` |
| `toolkit/shell.py` | +40 | `_render_result` 2-col branch; `_build_table_widget` helper |
| `toolkit/files.py` | NEW (+50) | `open_output_folder()` — Win32 single-string form for OneDrive paths |
| `toolkit/tokens.py` | regenerated | `RAIL_HL_BG = "#F9DDDD"` added |
| `design_system/.../colors_and_type.css` | +1 | `--rail-hl-bg` |
| `tools/master_budget/frame.py` | -50 / +1 | delegates to `toolkit.files.open_output_folder` |
| `tools/master_budget/tests/test_frame.py` | net delta | open-folder regression test moved to `tests/test_files.py` |
| `tools/sub_program/logic.py` | +20 | `ReportSummary` gains `faculty_budget` / `_ytd` / `_used_pct`; computed in existing per-line loop |
| `tools/sub_program/frame.py` | +95 | `RailItem` + `TableSpec` builders, `_row_style`, `_last_output_path`, `_open_output_folder`, secondary_actions update |
| `tools/sub_program/tests/test_logic.py` | +60 | 4 new tests for per-faculty stats |
| `tools/sub_program/tests/test_frame.py` | +80 | side_rail+table population tests; Open output folder tests |
| `tests/test_files.py` | NEW (+80) | 5 tests for the new shared helper |
| `tests/test_base_tool.py` | +100 | 8 new tests for RailItem, TableSpec, ToolResult defaults |
| `tests/test_primitives.py` | NEW or +many | 15 tests covering SelectableList, extended Table, _render_result branches |
| `CLAUDE.md` | +1 bullet | Cross-FS divergence gotcha extended with new symptoms + module-cache mtime workaround |

---

## ADR-0015 implementation status

| Step (per ADR §11) | Status | Owner |
|---|---|---|
| 1. Extend ToolResult + add RailItem/TableSpec | ✅ done | F |
| 2. Extract SelectableList from CommentaryDialog | ✅ done | F |
| 3. Extend Table primitive with row_style + on_row_click | ✅ done | F |
| 4. Extend `_render_result` with conditional 2-col branch | ✅ done | F |
| 5. Refactor Sub-Program to populate the new fields | ✅ done | G |
| 6. Add Open output folder to secondary_actions() | ✅ done | G |
| 7. Click-to-filter wiring inside Sub-Program's frame | ⏳ Agent I | — |
| (Bonus) Clear button — shell-level convention | ⏳ Agent H | — |

---

## Recovery work (sandbox-induced, NOT design issues)

Agent G's response was truncated mid-execution before it could run quality gates. Recovery
required four file restorations because the bash mount lost tail content on multiple files
(documented Cowork cross-FS sync issue, more aggressive this round than past encounters):

| File | Bash-mount damage | Recovery |
|---|---|---|
| `tools/sub_program/frame.py` | Missing lines 372-465; bash saw 370/371 lines, Windows had 464 | Wrote full content via `cat > /tmp/file.py <<'EOF' ... EOF; cp /tmp/file.py path/to/file` |
| `tools/sub_program/logic.py` | Missing lines 622-647; truncated mid-function body just after start of `# Per-f`-aculty comment | Append-mode patch via Python heredoc with the missing tail |
| `tools/master_budget/frame.py` | 1278 trailing null bytes after byte 12236 | `data.rstrip(b'\x00')` + write back |
| `tools/master_budget/tests/test_frame.py` | 499 trailing null bytes after byte 14616 | Same as above |

Plus a Python module-cache effect: even after the source on disk was correct,
`dataclasses.fields(ReportSummary)` returned only 6 of the 9 fields. Cause: stale mtime →
Python's import machinery used a cached parse of the dataclass decorator. Fix: `touch <file>`
to bump mtime, then re-import.

CLAUDE.md gotcha extended with both symptoms (truncation, null padding) and both workarounds
(write-from-/tmp + touch-to-invalidate-mtime).

---

## Final quality gates

```
$ python3 -m ruff format --check toolkit/ tools/sub_program/ tools/master_budget/ tests/
44 files already formatted

$ python3 -m ruff check toolkit/ tools/sub_program/ tools/master_budget/ tests/
All checks passed!

$ python3 -m mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/sub_program/ tools/master_budget/ tests/
Success: no issues found in 44 source files

$ python3 -m pytest tests/ tools/ --tb=line -q
396 passed, 30 skipped, 1 warning in 14.83s

$ python3 scripts/port_tokens.py --check
OK: toolkit/tokens.py is in sync with the CSS.
```

30 skips break down as:
- 14× `tests/test_primitives.py` — Tk-absent on Linux CI (expected)
- 4× `tests/test_shell_smoke.py` — tkinter absent (expected)
- 1× `tools/master_budget/tests/test_integration.py` — pywin32 COM Windows-only (expected)
- ~11 other Tk/pywin32 environmental skips across `tools/*/tests/`

---

## What the user will see when they restart School Tool

1. Open Sub-Program Budget Report tool from the left rail.
2. Tool now renders with the 220 px **faculty rail visible on the left** of the result table.
3. After Generate report:
   - Banner: "{N} sub-programs across {M} faculties. YTD spend {pct}% of annual..."
   - Rail: list of faculties sorted alphabetically with "Unknown" last, each row showing
     `{label} {used} %`, faculties containing any over-budget line marked with the
     light-pink `RAIL_HL_BG` background tint
   - Table: 7 columns matching the design exactly; over-budget rows get pink `#F4CCCC`
     bg + bold danger-red text on the `Used %` column
4. Action button row now shows: **Generate report** (primary) · **Edit commentary…** ·
   **Open output folder** (NEW)
5. Open output folder works for OneDrive paths with spaces (the OneDrive bug fix is now
   shared with Master Budget via `toolkit/files.py`).

What's NOT wired yet:
- Clicking a faculty in the rail does NOT filter the table — that's Agent I's job, next round.
- "Clear" button in the action row is NOT present — that's Agent H, the design-decision dispatch.

---

## Awaiting user direction

Phase 3 H (Clear button) and I (click-to-filter) are sequential next dispatches per the original
plan. Both are scope-locked to specific files. Recommend dispatching them in that order — H
introduces the shell convention (no behavioural change for tools that don't override `clear()`),
then I adds the live filtering UX inside Sub-Program.

Or — if the user wants to test the current state first (restart desktop, run a real CASES21 PDF
through the tool, verify the faculty rail looks right) — that's a sensible pause point before
dispatching H and I together as the final round.
