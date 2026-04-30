# ADR-0015 — Tool-result side rail and interactive table

**Status:** Proposed
**Date:** 2026-04-26

---

## Context

The Sub-Program Budget Report tool (M3-b), and its near-term successors Operating Statement and Camps
Reconciliation, need a secondary navigation panel left of the result table that lets the user filter rows
by a dimension (e.g. sub-program). Today `ToolResult` is a flat dataclass — banner, metrics, log lines,
a single `table_columns` / `table_rows` pair — and `_render_result` in `toolkit/shell.py` renders those
fields into a single-column layout. There is no provision for a side rail inside a tool's result area,
no row-click callback on the `Table` primitive, and no per-row style hook beyond the existing `_bg`/`_fg`
convention on row dicts.

We need to extend this surface additively so existing tools (HYIA Transfer Code Generator, Master Budget
Compass Autofill, and any future tool that does not need a rail) keep working without modification.
Simultaneously, the new fields must be expressive enough for Sub-Program's over-budget pink-fill rows,
its side-rail filtering UX, and any future tool with a comparable pattern.

**Terminology note.** This ADR introduces a 220 px *in-tool side rail* that appears inside the result
area of a specific tool. This is structurally and visually distinct from the 220 px *shell tool rail*
(the left-hand navigation panel that lists all registered tools, governed by ADR-0014 and locked by
`EXTENDING.md` "What stays locked"). Locking the shell rail means its width, styling, and selection
colour (`#3399FF`) cannot be changed per-tool. The in-tool rail proposed here is a new layout region
inside the tool's own frame; it does not touch the shell rail.

---

## Decision

### 1. New dataclasses in `toolkit/base_tool.py`

Add two new frozen dataclasses alongside the existing ones. No existing class is modified.

```python
from typing import Any, Callable

@dataclass(frozen=True)
class RailItem:
    label: str            # display name, e.g. "English"
    value: str            # pre-formatted summary, e.g. "72 %" — the rail does no arithmetic
    filter_key: str       # opaque token; the tool's frame interprets it for row filtering
    highlight: bool = False  # True → pink/over-budget marker on the rail row
```

```python
@dataclass(frozen=True)
class TableSpec:
    columns: list[dict[str, Any]]   # same shape as today's table_columns
    rows: list[dict[str, Any]]       # same shape as today's table_rows
    row_style: Callable[[dict[str, Any]], dict[str, str]] | None = None
    # row_style receives a row dict and returns a Tkinter option dict
    # e.g. lambda r: {"background": "#F4CCCC", "foreground": tokens.DANGER_FG}
    #      if float(r["used_pct"].rstrip("%")) > 100 else {}
    on_row_click: Callable[[dict[str, Any]], None] | None = None
    # on_row_click receives the full row dict when the user clicks a row
```

### 2. Additive extension of `ToolResult`

Append two optional fields to the existing `ToolResult` dataclass. Every existing field is preserved
at its current position and default.

```python
@dataclass
class ToolResult:
    status: Status
    banner_level: BannerLevel
    banner_text: str
    log_lines: list[LogLine] = field(default_factory=list)
    metrics: list[tuple[str, str, str | None]] = field(default_factory=list)
    table_columns: list[dict[str, Any]] | None = None   # legacy path — preserved
    table_rows: list[dict[str, Any]] | None = None       # legacy path — preserved
    output_path: Path | None = None
    # --- new fields (v2.0 phase 3 additions) ---
    side_rail: list[RailItem] | None = None
    table: TableSpec | None = None
```

**Backwards compatibility rule (critical):** `_render_result` uses the following fallback logic:

- If `result.table` is not None, it drives the table widget via `TableSpec`. Otherwise, `_render_result`
  falls back to the legacy `table_columns` + `table_rows` + per-row `_bg`/`_fg` path — exactly as
  today. Existing tools that populate only `table_columns`/`table_rows` receive no behavioural change.
- If `result.side_rail` is None, the result area is rendered in the current single-column layout. The
  two-column grid is created only when `side_rail` is not None.

Both fields are strictly opt-in. A tool must explicitly populate them to receive new behaviour.

### 3. Render layout for `_render_result`

The render order after this change (elements that already exist are unchanged):

```
section header  (label + short from BaseTool — already present)
banner
secondary action row  (primary button + tool.secondary_actions())
progress bar  (transient — already present)
metrics row  (if result.metrics — already present)

[
  if result.side_rail is not None:
    2-column grid frame:
      column 0  (220 px fixed, pack_propagate=False):
        SelectableList(result.side_rail, on_select=<filter callback>)
      column 1  (fill + expand):
        Table (from result.table or legacy fallback) + LogView

  else:                              ← current single-column behaviour, unchanged
    Table (from result.table or legacy fallback) + LogView
]

footer  (already present)
```

Layout constants:

- Gap between rail column and table column: `tokens.SP_GAP_SECTION` (10 px). This value is intentionally
  off the 4 px grid; the comment in `colors_and_type.css` notes it as a section-level gap token, not a
  component-level spacing unit. Using it here is consistent with its documented intent.
- Rail panel active row: `tokens.RAIL_SELECTED` (`#3399FF`) background, `tokens.FG_INVERSE` (`#FFFFFF`)
  foreground. This matches the `CommentaryDialog` left-pane selection style already present in
  `primitives.py:1087-1089`.
- Rail panel odd-index rows: `tokens.BG_ROW_ALT` (`#FAFBFC`) — same alternating-row convention as the
  Table primitive's `alt` tag.

When `side_rail` is populated and the user clicks a rail item, the shell passes the `filter_key` to the
`on_select` callback provided by the tool frame. The tool frame is responsible for re-emitting a new
`ToolResult` (with a filtered `table`) rather than mutating the rendered table in place — see §8 below.

### 4. New `SelectableList` primitive in `toolkit/primitives.py`

Extract the scrollable left-pane list pattern currently embedded in `CommentaryDialog`
(`primitives.py` lines 977–1139) into a standalone reusable primitive:

```python
def SelectableList(
    parent: tk.Widget,
    items: list[RailItem],
    on_select: Callable[[str], None],   # called with filter_key on click or keyboard nav
    width: int = 220,
) -> tk.Frame:
    """Scrollable, keyboard-navigable selection list backed by a list[RailItem].

    Returns the outer tk.Frame. The caller is responsible for placing it.
    Rows with highlight=True receive a pink left-border marker consistent with
    HL_MISMATCH semantics (over-budget / mismatch indicator).
    """
    ...
```

`CommentaryDialog` is then refactored to call `SelectableList` for its own left pane. The dialog's
external interface (`sub_programs`, `initial`, return type) is unchanged; only the internal construction
changes. All existing tests for `CommentaryDialog` pass without modification.

The `SelectableList` primitive is placed in `primitives.py` alongside the other primitives (after
`Table`, before `Metric`), and exported from `toolkit/__init__.py` in the same style as the existing
exports.

### 5. Extend the existing `Table` primitive — not a new class

The existing `Table` class in `toolkit/primitives.py` is extended by adding two optional keyword
arguments. Existing call sites pass neither; they receive no behavioural change.

```python
class Table(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        columns: list[dict[str, Any]],
        min_height: int = 200,
        row_style: Callable[[dict[str, Any]], dict[str, str]] | None = None,
        on_row_click: Callable[[dict[str, Any]], None] | None = None,
        **kwargs: Any,
    ) -> None: ...
```

- When `row_style` is provided, `set_rows` calls it for each row and applies the returned dict as
  Tkinter tag options (typically `background` and `foreground`). If the row also has `_bg`/`_fg` keys,
  `row_style` takes precedence; the legacy keys remain as a fallback.
- When `on_row_click` is provided, `Table.__init__` binds `<<TreeviewSelect>>` on the internal
  `ttk.Treeview` to reconstruct the row dict and invoke `on_row_click(row_dict)`.
- Both default to `None`. The existing `_bg`/`_fg` per-row tag path (`set_rows` lines 832–846 today)
  is preserved unmodified for rows that do not trigger `row_style`.

`TableSpec.row_style` and `TableSpec.on_row_click` are forwarded to the `Table` constructor by
`_render_result` when it builds the table widget from a `TableSpec`.

### 6. Over-budget cell signal: row bg + numeric value + explicit minus (Option B)

Phase 1 (Agent D) identified that the web mock additionally paints the `rem` (Remaining) and `Used %`
cell text in `--danger-fg` on over-budget rows, beyond the row-level pink background fill. The desktop
mock does not include this per-cell text colour. ADR-0014 / README §4 requires that colour is never
the sole signal; a second signal must exist.

**Decision: Option B.** Tools using `TableSpec.row_style` for over-budget rows return both `background`
and `foreground` at the row level:

```python
lambda r: (
    {"background": "#" + HL_MISMATCH, "foreground": tokens.DANGER_FG}
    if float(r["used_pct"].rstrip("%")) > 100
    else {}
)
```

This satisfies the README rule via three independent signals on an over-budget row:

1. Row background fill (pink, `#F4CCCC`).
2. Explicit numeric `Used %` value greater than 100 — a data-level signal.
3. Explicit `−` (U+2212) prefix in the `Remaining` column — a data-level signal distinct from colour.

A per-cell style hook (`column_style`) is not introduced in this ADR. The row-level `foreground` from
`row_style` changes all cell text in the row to `DANGER_FG`, which is acceptable: the over-budget row
is red text on pink background, and every column in that row is part of the over-budget condition.
If a future tool needs to colour only specific columns (e.g. leave label columns in `FG_1`), a
`column_style` hook can be added as a follow-up ADR. Phase 3 builders should not invent an ad-hoc
`column_style` parameter; raise a follow-up ADR if the need materialises.

### 7. Extend vs new Table primitive

**Decision: extend the existing `Table`.** Reasons:

- A single `Table` primitive keeps the toolkit surface small and predictable. Every tool that needs a
  table — simple or interactive — uses the same class.
- The existing `_bg`/`_fg` per-row tag mechanism already demonstrates that `Table` can carry display
  metadata alongside data. Adding `row_style` and `on_row_click` is a natural continuation of that
  pattern.
- Extending via optional kwargs preserves all existing call sites with zero changes (Python default
  arguments).
- Tests for `Table` grow incrementally in the same test file; there is no parallel test suite to keep
  in sync.

**Trade-off acknowledged:** a separate `InteractiveTable` class would provide hard isolation and allow
the click-and-filter path to evolve independently without any risk of regressions in HYIA, Master Budget,
or SRP rendering. The cost is maintaining two parallel codebases and two test suites for what is
essentially the same widget with two optional features. For the click feature alone, that cost is not
justified. If the `Table` surface grows significantly more complex (e.g. inline editing, drag-to-reorder,
virtual scrolling), a split should be reconsidered in a future ADR.

---

## Consequences

### Positive

- Provides a first-class surface for rich result views (side rail + filtered table) without touching
  any existing tool or breaking any existing test.
- `SelectableList` becomes a reusable toolkit primitive. Future tools with a left-pane navigation
  pattern — Operating Statement period selector, Camps Reconciliation activity picker — can use it
  without duplicating the scroll/keyboard/selection logic that is currently copy-locked inside
  `CommentaryDialog`.
- The two-column layout is entirely opt-in: tools that do not populate `side_rail` see no change in
  their render path, binary size, or test coverage.

### Negative / risks

- `ToolResult` grows two more fields (`side_rail`, `table`). The existing `table_columns`/`table_rows`
  fields are now a legacy path. A future ADR may deprecate and remove the legacy fields once all tools
  have migrated to `TableSpec`; that migration is out of scope here and should not be attempted
  opportunistically during Phase 3.
- `row_style` and `on_row_click` introduce closures that can capture mutable state from the tool
  frame (e.g. the frame's `active_filter` variable). The tool frame is responsible for guarding against
  stale captures: **when the active filter changes, the frame must re-call `tool.run()` or emit a new
  `ToolResult` with a freshly-built `TableSpec`**, not attempt to mutate the already-rendered table
  widget. Mutating the rendered widget from a closure is not safe on the threading model (ADR-0005).
- Refactoring `CommentaryDialog` to use `SelectableList` introduces a small internal change to a
  tested path. The refactor must be behaviour-preserving; its correctness is verified by the existing
  `CommentaryDialog` tests without modification.

---

## Alternatives considered

### (a) New `InteractiveTable` primitive

Rejected — see §7. The isolation benefit does not outweigh the cost of two parallel primitives.

### (b) Inline custom rendering inside `tools/sub_program/frame.py`

Rejected. Implementing the side rail and row-click filtering directly inside the Sub-Program frame
would place shell-level layout decisions (two-column grid, column widths, scroll region) inside the
tool. This violates the BaseTool contract (ADR-0004: "Never put shell-aware code inside a tool") and
`EXTENDING.md` "What stays locked" ("a tool module may import from `toolkit.*`; `toolkit` must never
import from `tools.*`"). It also means every future tool with a rail would re-implement the same
layout, diverging over time.

### (c) Wait for a second customer before generalising

Rejected. The YAGNI argument does not apply here: Operating Statement and Camps Reconciliation are both
on the immediate roadmap (M7/M8) and both likely candidates for a similar left-pane + filtered-table
pattern. The marginal cost of designing the abstraction correctly now, with Sub-Program as the first
customer, is small. Deferring and then refactoring the Sub-Program implementation after the fact would
be more disruptive than designing it once.

---

## Backwards compatibility matrix

Every tool currently in the registry is listed below with its behaviour under the new surface. The key
invariant: **no tool's existing `ToolResult` construction, existing test suite, or rendered output
changes as a result of this ADR.** New fields default to `None`; `_render_result` treats `None` as
"use the legacy path".

| Tool | `side_rail` | `table` | `row_style` | `on_row_click` | Behaviour change |
|---|---|---|---|---|---|
| HYIA Transfer Code Generator | `None` | `None` (uses legacy `table_columns`+`table_rows`) | n/a | n/a | None |
| Master Budget Compass Autofill | `None` | `None` (uses legacy `table_columns`+`table_rows`) | n/a | n/a | None |
| SRP Comparison | `None` | `None` (uses legacy `table_columns`+`table_rows`) | n/a | n/a | None |
| Sub-Program Budget Report | populated | populated | over-budget: pink bg + danger fg | filter table by sub-program | **NEW** (Phase 3) |
| Operating Statement | `None` | `None` | n/a | n/a | None (until M5+ polish, per roadmap) |
| Camps Reconciliation | `None` | `None` | n/a | n/a | None (tool scaffolded; parser pending sample data) |

Every existing test file under `tools/*/tests/` continues to pass without modification. New tests for
`RailItem`, `TableSpec`, `SelectableList`, extended `Table`, and the two-column `_render_result` branch
are written alongside the Phase 3 implementation.

---

## Implementation order

Phase 3 owns the implementation detail. The headline sequence is:

1. Add `RailItem` and `TableSpec` dataclasses; extend `ToolResult` with `side_rail` and `table` in
   `toolkit/base_tool.py`.
2. Extract `SelectableList` from `CommentaryDialog`; refactor the dialog to use it (behaviour
   unchanged).
3. Extend `Table.__init__` with `row_style` and `on_row_click` optional kwargs.
4. Extend `_render_result` in `toolkit/shell.py` with the conditional two-column branch.
5. Refactor Sub-Program's `frame.py` to populate `side_rail` and `table` in its `ToolResult`.
6. Add `Open output folder` to Sub-Program's `secondary_actions()` (low-risk port from Master Budget —
   covered by the bug-report queue separately).
7. Wire click-to-filter inside Sub-Program's frame (re-emit a filtered `ToolResult` on rail selection).

Each step is a separate Phase-3 dispatch and can be code-reviewed independently.

---

## Numbering note

Existing ADRs in `docs/02_ARCHITECTURE.md` use 4-digit zero-padded numbering (ADR-0001 through
ADR-0014). This file is therefore numbered **ADR-0015**. The original brief used `ADR-001-…`; that
form was not used here because it does not match the codebase convention.

---

## Open questions

1. **`SP_GAP_SECTION` = 10 px is not on the 4 px grid.** `colors_and_type.css` documents it as a
   deliberate exception ("section-level gap, not component-level spacing"). Using it for the gap
   between the in-tool rail and the table is consistent with its intent. If a future design review
   moves it onto the grid (e.g. to 8 px = SP_2 or 12 px = SP_3), the token change propagates
   automatically via `port_tokens.py`.

2. **`RailItem.highlight` visual treatment is underspecified.** This ADR says "pink/over-budget
   marker" but does not pin the exact widget-level implementation (border, dot, background tint).
   Phase 3 should establish the visual and document it; if it requires a new token, that token must
   be added to `colors_and_type.css` first (per ADR-0009 and `EXTENDING.md`).

3. **`SelectableList` keyboard navigation contract.** The `CommentaryDialog` implementation supports
   Up/Down arrow keys on `list_canvas` and `list_inner`. The new primitive should preserve this.
   The exact focus-management detail (which widget receives initial focus when the rail is first
   rendered inline vs. inside a modal) will differ between the two use-sites and must be resolved
   during Phase 3 implementation.

4. **`ToolResult` mutability.** `ToolResult` is currently a regular (non-frozen) `@dataclass`.
   `RailItem` and `TableSpec` are `frozen=True`. This asymmetry is intentional: `ToolResult` may be
   re-emitted by the tool frame on filter change, and the new frozen dataclasses are value objects
   that should not be mutated. No change is needed, but reviewers should note the distinction.

5. **`Table.set_rows` vs `Table.__init__` for new kwargs.** This ADR specifies the new kwargs on
   `__init__`. An alternative is to put `row_style` on `set_rows` (called once per result render).
   The `__init__` approach is slightly cleaner because the click binding is set up once; if `set_rows`
   is called again (e.g. on filter change), the binding is already in place. Phase 3 implementors
   should confirm this is correct before coding and flag any issue here.
