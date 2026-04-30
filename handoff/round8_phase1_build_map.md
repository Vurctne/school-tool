# Round 8 Phase 1 — Build Map (Sub-Program design fidelity)

**Date:** 2026-04-26
**Orchestrator:** Opus 4.7
**Sub-agents:** A · B · C · D (Sonnet 4.6, Explore tier, read-only) — all returned green.

---

## Discovery output (per-agent, condensed)

### Agent A — Shell-surface audit
- `ToolResult` (`base_tool.py:91-110`) — 8 fields; `output_path` is dead (never read by shell).
- `_render_result` (`shell.py:1088-1140`) renders single-column: banner → metrics → log → table.
- `Table` primitive (`primitives.py:770`) supports columns/rows + per-row `_bg`/`_fg` tags — but **has no click-callback API**.
- No two-column layout primitive exists in the shell content area.
- `CommentaryDialog` (`primitives.py:977-1139`) embeds the exact rail pattern needed (220 px, scrollable, click-select, active highlight) — but it's tangled inside the dialog, not a reusable primitive.
- **Recommend new `SelectableList` primitive** + new `side_rail` field on `ToolResult`. `_render_result` adds an opt-in 2-col branch.

### Agent B — Sub-Program logic audit
- `SubProgramLine` (`logic.py:87-98`) has `faculty` and `commentary` already — neither is currently emitted to `table_rows`.
- `ReportSummary` has `faculty_counts` (per-faculty line counts) but **no per-faculty financial totals**.
- `is_over` rule: `ytd > budget` (logic.py:216) — **not** `used_pct > 100`. Agreement with the design rule is incidental; for the rail's per-faculty used %, compute from totals (`faculty_ytd / faculty_budget * 100`), don't reuse PDF-sourced row %s (they may not sum correctly).
- Insertion point for per-faculty stats: extend the existing loop at `logic.py:611-614` (Option A — single-pass, +4 lines).
- `secondary_actions()` returns `[("Edit commentary...", …)]`. No "Open output folder" anywhere — and no draft of one.

### Agent C — Master Budget reference audit
- `_open_output_folder` (`master_budget/frame.py:284-333`) **already has the OneDrive-safe form** (`subprocess.Popen(f'explorer /select,"{path}"')`, single string, line 317). Pinned by `test_open_output_folder_uses_string_form_for_win32` (`test_frame.py:345-377`).
- Sub-Program is missing: `_last_output_path` instance field, `_open_output_folder` method, the corresponding 3 tests.
- Recommend: lift the function into `toolkit/files.py` so SP + Operating + future tools share one corrected impl.

### Agent D — Design spec
- All 12 faculties + table columns + over-budget styling extracted as structured tables (see Phase 1 chat output for full breakdown).
- Token mapping verified — every constant we need (`HL_MISMATCH`, `BG_MUTED`, `FG_1`, `FG_INVERSE`, `RAIL_SELECTED`, `BG_ROW_ALT`, `BORDER_SUBTLE`, `DANGER_FG`, `WARN_FG`, `INFO_FG`, `INFO_BG`) already exists in `toolkit/tokens.py`. No CSS-port required.
- **`HL_MISMATCH = "F4CCCC"` (no `#` prefix)** — Phase 3 must prepend `#` for Tkinter, openpyxl gets the bare hex via `toolkit.fills.argb()`.
- `SP_GAP_SECTION = 10` (off the 4 px grid by design — used for the table+rail gap).

---

## Desktop vs web deltas (resolved)

Per user direction `tk-tools.jsx` wins by default. 13 deltas inspected; 12 resolved in favour of desktop, 1 web enrichment adopted (with rationale).

**Web-enrichment exception (row 7 in chat):** per-cell fg colouring on over-budget rows. The desktop mock paints only the row bg pink; the web mock additionally paints `rem` and `used %` cell text in `--danger-fg` (and `used %` bold). README §4 ("colour is never the only signal") requires a second signal — the bold red text on `Used %` and `Remaining` provides it. Adopting from web here is consistent with the README's explicit rule. Architect (Agent E) to formalise in ADR-001.

All other deltas: desktop wins. Full delta table in chat output.

---

## Phase 2 readiness checklist

- [x] Shell surface mapped — what `ToolResult` fields the shell reads, where the schema can extend.
- [x] Logic gaps identified with concrete insertion points.
- [x] Reference port plan (Master Budget → Sub-Program) drafted with file/line specifics.
- [x] Design spec extracted as structured spec, no JSX paste-ins.
- [x] Desktop vs web deltas surfaced explicitly with default resolution.
- [ ] **Awaiting user approval** to dispatch Agent E (ADR-001 author).

## Open question for the ADR

When Agent E writes ADR-001, one decision is worth a one-paragraph trade-off:

> Do we **extend the existing `Table` primitive** (`primitives.py:770`) to add a row-click callback,
> or **add a new primitive** (e.g. `InteractiveTable`) and leave `Table` as-is for non-clickable
> tables?

Recommendation in the ADR draft: extend, with default `on_row_click=None` so existing call sites (HYIA, Master Budget, SRP) get no behavioural change. Same `Table` for everyone keeps the surface small. But Agent E should evaluate.

---

## Files created this round

- `handoff/round8_subprogram_design_gap.md` (Round 8 init — gap analysis, no code)
- `handoff/round8_phase1_build_map.md` (this file — Phase 1 synthesis)

No code changed. No deploys. No commits.

## Phase 2 dispatch on user "go"

Agent E prompt template ready — will produce `docs/ADR-001-tool-result-side-rail-and-table.md`,
covering: schema additions (RailItem, TableSpec, side_rail field, table field), backwards compat
guarantees for tools that pass neither, layout grid spec for `_render_result`, primitive additions
(`SelectableList`), trade-off on extend-vs-new-Table-primitive, and the over-budget cell-fg rule.
