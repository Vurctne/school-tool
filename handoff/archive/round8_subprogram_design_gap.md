# Round 8 handoff — Sub-Program tool: design vs implementation gap

**Date:** 2026-04-26
**Orchestrator:** Opus 4.7 (no sub-agent dispatched — analysis only)
**Round goal:** answer "does the Sub-Program Budget Report tool match the design pack?"

Source of truth referenced this round:
- `design_system/design_handoff_school_finance_toolkit/ui_kits/desktop_multitool/tk-tools.jsx` §3 (lines 95-165)
- `design_system/design_handoff_school_finance_toolkit/ui_kits/web_toolkit/tool-subprogram.jsx`
- `design_system/design_handoff_school_finance_toolkit/EXTENDING.md`

---

## Verdict

**~75% aligned.** The data shape and core surface (file pickers, primary button label, banner copy
pattern, table column schema, over-budget pink fill, Edit commentary action) all match the design
exactly. Two non-trivial gaps remain: the 220px faculty rail and the "Open output folder" /
"Clear" action buttons.

---

## What's already aligned

See the table in chat. Highlights:

- Table columns are a **1:1 match** with `tk-tools.jsx:97-105` — `Sub-program` (90, mono),
  `Account` (80, mono), `Description` (flex), `Budget` (90, right, mono), `YTD` (90, right, mono),
  `Remaining` (90, right, mono), `Used %` (70, right, mono).
- Banner pattern matches `tk-tools.jsx:128`: `"{N} sub-programs across {M} faculties. YTD spend
  {pct}% of annual. 1 line over budget: {sp}/{acc}."` (`frame.py:235-251`).
- Pink fill (`HL_MISMATCH = #F4CCCC`) on over-budget rows matches the `over = { _bg: "#F4CCCC" }`
  pattern in the jsx.
- Primary button label "Generate report" matches `tk-tools.jsx:122`.
- Secondary action "Edit commentary…" matches `tk-tools.jsx:123`.
- Numerics contract honoured (mono cols, tabular nums, dollar sign with no space, U+2212 minus).

## What's NOT aligned

### Gap 1 — Faculty rail (220px side panel) — **medium effort**

Design (`tk-tools.jsx:129-160`):

```jsx
<div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 10, ... }}>
  <div style={{ ...white panel... }}>
    {[
      ["English", "72", true],
      ["Mathematics", "58", false],
      // ... 12 faculties with used %, active flag, alternating bg
    ].map(...)}
  </div>
  <TkTable cols={cols} rows={rows} />
</div>
```

Current state: `BaseTool` / `ToolResult` / `shell._render_result()` have no concept of an in-tool
side rail. The shell currently grid-packs Banner → Progress → Metrics → Log → Table in a single
column.

To close: extend `ToolResult` with a `side_rail: list[FacultyRailEntry]` field (or an opaque
`SideRail` dataclass), extend `shell._render_result()` to detect side_rail and switch the table
container from `pack(fill="x")` to a 2-col grid. Add per-faculty used-% computation to
`tools/sub_program/logic.generate_report` (currently produces `faculty_counts: dict[str, int]` —
needs `faculty_used_pct: dict[str, Decimal]` too). Wire click-to-filter so clicking a faculty
filters the right-hand Treeview. Worth a tiny ADR (touches the BaseTool surface).

### Gap 2 — "Open output folder" secondary button — **trivial**

Design shows it as one of 5 action buttons (`tk-tools.jsx:124`). Master Budget already has it
(`tools/master_budget/frame.py:282`, returns `("Open output folder", self._open_output_folder)`).
Sub-Program tool's `secondary_actions()` returns only `[("Edit commentary...", self._edit_commentary)]`.

Watch out: per CLAUDE.md gotcha "OneDrive `Open output folder` doesn't open the right folder",
the fix is to pass `/select,"<path>"` as a **single shell string** to `subprocess.Popen`, not as a
list. Master Budget's current implementation needs that bug fix too — best to factor
`_open_output_folder` into a shared helper in `toolkit/shell.py` or `toolkit/files.py` so both
tools (and future Operating Statement) share one corrected implementation.

### Gap 3 — "Clear" secondary button — **small, design decision first**

Design shows `<TkButton>Clear</TkButton>` on every tool. Currently no tool exposes it.

Two paths:
1. **Shell-level** (recommended): bake "Clear" into the action row that the shell renders for every
   tool, alongside the primary button — clears file inputs, banner, log, table.
2. **Per-tool**: each tool returns `("Clear", self._clear)` from `secondary_actions()` and
   reimplements the reset.

Option 1 is cleaner — clearing is a shell-level concern, not a tool-level concern. Recommend
ADR-0015. **Don't auto-implement** before the user weighs in — locked-by-design surface per
EXTENDING.md "What stays locked".

### Gap 4 — PDF cover + body — **out of scope (M5+)**

`pdf_template = None` / `pdf_body = None`. EXTENDING.md "Adding a PDF report" describes
`reports/sub_program_cover.html` + `_body.html` + `report.css` via WeasyPrint, but ROADMAP places
the PDF report in M5+. Not a v2.0 launch blocker.

### Footer copy mismatch — **none, no action**

Design shows `Please send suggestions to ivan.wang@education.vic.gov.au`; current shell renders
`Please send feedback to ${SUPPORT_EMAIL}` where `SUPPORT_EMAIL = "Vurctne@gmail.com"`. The design
jsx is older than the v2.0 branding decision (Publisher: Vurctne); no change needed unless
branding flips again.

---

## Recommended next-round dispatch

If the user wants to close the gaps before testing the tool with a sample PDF, the order is:

1. **(orchestrator-direct, 10 lines)** Pull `_open_output_folder` from Master Budget into
   `toolkit/files.py` as `open_output_folder(path: Path) -> None`, fix the OneDrive bug. Have all
   3 paid-tool frames (`master_budget`, `sub_program`, `operating`) reference it from
   `secondary_actions()`. Update the 1 existing test for Master Budget.

2. **(ADR + sub-agent dispatch)** Faculty rail. Spec:
   - ADR-0015: "ToolResult.side_rail — opt-in 220px secondary navigation panel"
   - imp-12: extend ToolResult dataclass + shell._render_result + logic.generate_report.
     Acceptance: clicking a faculty filters the Treeview to that faculty's rows.
   - reviewer-4: independent code review.

3. **(design discussion, no code)** Decide on Clear button placement (shell-level vs per-tool).

Plan A Step 4 (run a real CASES21 PDF through the tool end-to-end) does NOT depend on closing
gaps 1–3 — the existing tool produces a correct workbook today; the gaps are pure UX polish.

---

## Status table updates

- Round 8 = analysis only. No commits, no sub-agent dispatch, no deploys.
- Tasks #10 / #11 / #12 created for the three gaps.
- Task #8 (verify paid tools unlock) still in_progress — pending user's confirmation that the
  licence pill flipped to Active after restart + Refresh.
