# Sub-Program Budget Report — OUTPUT redesign brief

**Date:** 2026-05-10
**Trigger:** User (Ivan): "你们配合重新设计一个全新的Sub program Budget
Report， …source file is GL21157_*.pdf, output is Monthly Sub Program
Report April 2026 KMAR.xls. Users are mostly without finance
background. Give me suggestions for redesigning the output."
**Lenses applied:** variance-analysis skill (decomposition, materiality,
narrative quality, waterfall) + non-finance-reader UX (plain English,
remove jargon, surface decisions).
**Disclaimer:** This is a UX/visualisation brief informed by
variance-analysis best practice — not financial advice. Heuristics
proposed here (materiality floors, "needs attention" classifications)
should be reviewed by qualified finance staff before publication.
**Scope:** **OUTPUT redesign** (the .xlsx workbook the school sends
to council). Distinct from the Round 44 brief which redesigned the
in-app screen.
**Status:** advice only — no code changed in this round.

---

## What we're working from

Source PDF (CASES21 GL21157 export — `Samples/Annual Subprogram Budget
Report/GL21157_Annual Subprogram budget report.pdf`):

- 8 pages, ~120 sub-program rows split by **Revenue Recurrent** and
  **Expenditure Recurrent** sections.
- Columns per row: `Sub Prog. | Title | Last year actual | Last year
  budget | Annual budget | YTD | % Budget received` (Revenue) plus
  `Outstanding Orders | Uncommitted Balance` (Expenditure).
- No comments, no period label visible (footer carries date), no
  faculty grouping.

Reference output (`Monthly Sub Program Report April 2026 KMAR.xls` —
the file Kate Marshall, the principal, actually receives):

- 11 sheets total — one of them, **`MGC - Combined Rev & Exp
  Report`**, is what schools call "the monthly report".
- 92 rows, 12 columns: `CODE | PROGRAM NAME | Funds from Previous
  Year | Budget Revenue 2026 | Total Budget Allocation Expenditure |
  Revenue YTD | Expenditure YTD | Less outstanding orders | Available
  Balance YTD | Available Balance % YTD | Revenue Budget % Received
  YTD | Comments`.
- One continuous list in code-numeric order. **No section breaks, no
  totals row, no priority ranking, no faculty grouping.**

The Phase D tool (Round 51, just shipped) produces something close to
this 12-column shape with structured commentary, materiality-aware
pink fills, and per-sub-program aggregation.

---

## What's broken about the current output for a non-finance reader

Quotes from real comment-column entries in the actual KMAR file —
each is a UX cliff that a non-finance principal hit:

| Sub-program | What the principal wrote | What broke |
|---|---|---|
| 6001 Building Serv & Utilities | "KMAR loog into this" | Typo — written under time pressure, no structure to invite a categorised note |
| 6502 Grounds | "KMAR loog into this" | Same |
| 6222 Maintenance Programs | "KMAR look into this" | Material variance flagged but no driver / outlook / action recorded |
| 7001 Administration | (no comment) | Available Balance YTD = **−$1,342,953** — almost 4× the annual budget over — and the principal didn't even write a note. The cell is just pink. |
| 8328 France Overseas Trip | "Budget needs to be amended fro…" (truncated) | Action is implied but not categorised |
| 8520 Aerobics Program | "Journal required from 8655 $99…" | Cross-reference between sub-programs invisible to anyone but the writer |

The structural problems behind these symptoms:

### 1. The signal-to-noise ratio is awful

92 rows, ~50% with substantive numbers and ~50% nearly empty (placeholder rows for sub-programs that exist on the chart of accounts but didn't transact this period). The principal scans for trouble in a forest of zeros.

### 2. "Available Balance % YTD" is a number, not a meaning

A column showing `−2.21` or `0.40` requires the reader to do mental arithmetic: "what does negative 221% even mean? Are we ruined?" Worse, the literal value `7` appears (e.g. r15, r23 — likely a `=#DIV/0!` evaluated as `7` somewhere in the original Excel template). A non-finance reader cannot tell "broken cell" from "real number".

### 3. There is no story arc

The report leads with sub-program 1251 (Design, Creativity & Tech) — a tiny program nobody on council will ask about — and ends with sub-program 9499 (Revenue Control — a $3.7M aggregator). The biggest variance in the school ($1.3M overdraw on Administration) is buried at row 55 of 92.

### 4. The faculty dimension is invisible

Sub-program codes encode faculty in the leading digit (1 = Design & Tech, 4 = Curriculum, 5 = Wellbeing, 6 = Facilities, 7 = Admin, 8 = Programs/Camps, 9 = IT). The tool already infers this for the in-app rail, but the **output** loses it — the principal can't ask "how is Wellbeing tracking overall?" without manually filtering.

### 5. The Comments column carries 4 different things

Looking at real comments in the KMAR file, principals use this single column for:

- **Action prompts** (e.g. "KMAR look into this") — *Action: Investigate*
- **Variance drivers** (e.g. "Revenue amount related to…") — *Driver: One-time / Ongoing*
- **Cross-references** (e.g. "Journal required from 8655 $99…") — *Internal note, not for council*
- **Forecast updates** (e.g. "Budget needs to be amended from…") — *Action: Update forecast*

Round 51 Phase D added structured Driver / Outlook / Action dropdowns
in the in-app editor that map exactly to these four uses — but the
**output** still presents the structured prefix as inline text in the
same Comments column. Non-finance readers parse `[Driver: Ongoing |
Action: Monitor] notes` as software output, not as decision support.

### 6. There is no "what changed since last month" signal

The PDF carries `Last year actual` and `Last year budget`; the KMAR
output drops these entirely (probably because the principal doesn't
care about last year on a monthly basis). But the tool has no
period-over-period story either — no "this is a new variance",
"this got worse since March", "this came back to plan". The
principal can't tell whether their attention is correctly placed.

---

## Six concrete redesign moves, ordered by user impact

### Move A — ~~Summary sheet~~ **DROPPED — keep main view as the line-by-line table**

**User decision (2026-05-10):** No Summary sheet. The principal opens
to the same line-by-line shape they're used to (Kate Marshall's
existing template), with the renderer improvements (Move B Status
pills, Move D Trend column, Move E prose commentary, Move F edge-case
caps) applied to the existing layout.

**What this means for the rest of the brief:**

- No new sheet 1. The existing 12-column sub-program sheet stays as
  the primary view and the file's first sheet.
- "Top 10 sub-programs to look at" / "What's new since last period" /
  "Notes from the team" sections are dropped. The signal that would
  have populated them lives at the row level via Status + Trend
  columns (Move B + D) — readers scan the Status column for "Investigate
  urgently" rather than reading a prepared executive summary.
- Move E (prose commentary) still applies — same rendering
  improvement, just on the existing sheet only, not on a new one.
- The Watchlist sheet (Sheet 3 below) survives as a filtered view
  of the same data — the council-targeted artefact that the dropped
  Summary would have served.

**Original rationale, retained for context:**

The variance-analysis skill is explicit that good reports answer
five questions at a glance. The current 92-row table answers none
of them. A non-finance principal opens the file, sees rows, closes
the file, asks the bursar "anything I should look at?". The Status
pill column (Move B) and Trend column (Move D) are now the answer
to "what should I look at" at the row level, in lieu of an executive
summary.

---

### Move B — Replace numeric percent columns with **plain-English status pills**

**Why.** Two columns in the current KMAR output cause the most
non-finance confusion:

- "Available Balance % YTD" — values from `−2.21` to `1.00`
- "Revenue Budget % Received YTD" — values from `0.00` to `21.36`

A non-finance principal cannot read these as percent of budget.
`−2.21` is interpreted as "minus two something" not "we have
overspent by 221% of annual budget". The literal `7` (= a stale
`=N/A` cell coerced to int) is read as "seven what?".

**How.** Drop both columns from the headline output. Replace with a
single `Status` column whose value is one of:

| Status | Meaning | When |
|---|---|---|
| `On track` | Within materiality threshold | Variance < $5K AND < 10% |
| `Slightly over` | Material but small | $5K–$25K over OR 10–25% over |
| `Material concern` | Worth a council mention | $25K–$100K over OR 25–50% over |
| `Investigate urgently` | Big enough to act on | > $100K over OR > 50% over |
| `No spend yet` | $0 YTD on a non-zero budget | Used = 0 |
| `New since last period` | Variance is new | Previous month status was `On track` |
| `Worsening` | Growing each month | Variance trend up over 3 months |

Each status maps to a colour token (already in the design system —
green for OK, amber for slight, red for material/urgent, grey for
no-spend). The numeric percent stays available in the Detail sheet
for anyone who wants it, but it doesn't crowd the headline view.

**Bonus:** The status column is what the **Summary sheet** filters on
to build the "Top three things to look at" list automatically.

---

### Move C — ~~Faculty grouping~~ **DROPPED — per-sub-program analytics only**

**User decision (2026-05-10):** Faculty grouping in the output is
not wanted. Sub-program is the actual decision unit — programs have
specific stakeholders (the rowing co-ordinator, the music director,
the camp organisers), and the faculty inference from leading-digit
code is a model that adds cognitive overhead without changing what
gets investigated. The in-app faculty rail is unaffected (it's a
navigation aid for the operator, not output the principal sees).

**What this means for the rest of the brief:**

- Detail sheet stays as one continuous list ordered by sub-program
  code (matches Kate Marshall's existing template behaviour).
- No faculty subtotals. Sub-program totals (Total Annual Budget,
  Total YTD, Total Net) aggregate at the **school** level only.
- Summary sheet's faculty bar chart (originally Move A) is replaced
  with a per-sub-program **Top 10 concerns** list — see Move A,
  revised below.
- Sheet 4 "Faculty health" is dropped from the workbook.

---

### Move D — Resurrect a **trend column**: "Vs March 2026"

**Why.** Variance-analysis best practice is that a single-period
snapshot answers four of the five investigation questions but
misses "what's the trend, is this getting worse?". The KMAR output
has no period-over-period dimension at all. The principal cannot
tell whether last month's $1.3M Admin overrun grew or shrank this
month.

**How.** When the user supplies a prior-period file (which the tool
already accepts for commentary join), also extract YTD figures from
it and compute:

| Trend label | Glyph | When |
|---|---|---|
| `New issue` | ⚠ | Was on-track last month, now off |
| `Worsening` | ↑ | Variance grew by > $5K |
| `Stable` | → | Variance changed by ≤ $5K |
| `Improving` | ↓ | Variance shrank by > $5K |
| `Resolved` | ✓ | Was off-track, now on-track |

Render in a single column on the Detail sheet, between Status and
Comments. The Summary sheet can pull a "What's new" list filtered to
`New issue` and `Worsening` items.

This requires extending `load_prior_period_comments` to also grab
the prior YTD numbers (currently only Comments are read). The tool
already has the join keys (sub_program + account / description) —
this is a small extension.

---

### Move E — Surface structured commentary **as plain English**, not as a prefix

**Why.** Round 51 Phase D's `[Driver: Ongoing | Action: Monitor]`
prefix in the Comments cell is great in-app (the editor structures
the input) but reads as software output in the printed report. A
non-finance principal flipping through the file thinks "what does
that bracket-thing mean?".

**How.** In the OUTPUT writer, expand the structured tuple into one
or two human sentences per row:

| Structured input | Output cell text |
|---|---|
| `Driver: Ongoing, Action: Monitor`, notes "Reviewed by council" | "Ongoing variance — being monitored. Reviewed by council." |
| `Action: Investigate`, notes "Cross-check with HOD next week" | "Needs investigation: cross-check with HOD next week." |
| `Driver: Timing-late, Outlook: Expected to continue`, no notes | "Spend later than planned; expected to continue." |
| `Action: Update forecast`, notes "Budget needs amending" | "Forecast update needed: budget needs amending." |
| All blank | (cell empty) |

A small `_render_commentary_for_xlsx(line) -> str` function with a
copy-table from the dropdown values. The structured tuple is still
encoded **on the in-app side and in any cell the prior-period
reader will round-trip back** (so re-reading next month's file
preserves the categorisation), but the published Detail sheet uses
the prose form for human readers.

**Decision needed.** Do we duplicate (one column with structured
prefix for round-trip, one with prose for humans), or do we keep
just prose and lose the round-trip? The cleanest answer is to
keep the structured prefix on a HIDDEN second comments column
(used only when this file is read back as a prior-period source),
and the visible cell is the prose. Excel hides columns trivially;
schools won't notice.

---

### Move F — Cap and rebrand the percent-format edge cases

**Why.** Real KMAR rows we observed:

- r27 Mathematics: `Available Balance % YTD = -0.45`, `Revenue Budget
  % Received YTD = 21.36` — the latter literally means "we collected
  21× our annual revenue budget already". An accident: the parser
  divided by an annual budget of $1,000 when the YTD is $21,365.
- r15, r23, r69, r75, r81 — `7` literal in the percent column. From a
  legacy `=N/A` cell or `IFERROR(0,7)` boolean coercion. Means
  nothing to a reader.
- r54 School Funded Capital Building: blank Annual Budget but $454K
  YTD spend. Available Balance and percent columns are blank. A
  council member sees "$454K spent on what?" with no context.

**How.** Three small fixes the writer can apply:

1. **Cap displayed percents at ±999%** with a footer note "(uncapped
   value: 2,136%)". Anyone scanning the column sees a finite number,
   anyone investigating sees the truth.
2. **Strip literal `7` and other coerced placeholders.** Detect
   non-percent values in percent columns; render `—`. Add a footer
   note for the count of stripped placeholders if non-zero.
3. **Surface "Spent without budget" rows** in their own Summary
   section. They're a real category of finance concern (capital spend
   without a council-approved annual budget) and currently invisible.

---

## Layout sketch — what the new workbook contains

```
Workbook: Sub Program Report - April 2026.xlsx
│
├─ Sheet 1: Sub Program Report            ★ KMAR's existing layout, enhanced
│   ├─ One continuous list, per-sub-program  (unchanged from current)
│   ├─ Status column                      (plain-English pills, Move B)
│   ├─ Trend column                       (vs prior period, Move D)
│   └─ Commentary                         (prose form, Move E)
│
├─ Sheet 2: Watchlist                     ★ Spinout for council
│   └─ Just the rows where Status ≠ "On track"
│       Pre-filtered, pre-sorted by $ impact
│
└─ Sheet 3: Audit trail                   ★ NEW (hidden by default)
    └─ Sub-program | structured-prefix-encoded comment
       Read by the next month's prior-period join.
       Hidden by default — council never sees it.
```

The current single sheet → 3 sheets, each with a clear single
purpose. **No Summary sheet** (per user direction). **No Faculty
roll-up sheet** (per user direction). Sub-program is the unit
throughout. The principal opens to Sheet 1 (the layout they're
already used to, with better signals), council reads Watchlist,
the round-trip joiner reads Audit trail.

---

## Print and distribution considerations

The current output is printed and bound for monthly council
meetings. Move A's Summary sheet must fit on **one A4 page**
landscape; that's the design constraint that keeps it focused.

- Print headers / page setup already configured by Round 47.
- Per-sheet page setup: Summary = portrait A4 fit-to-1, Detail =
  landscape A4 fit-to-width with title row repeat, Watchlist =
  landscape A4 fit-to-1, Faculty health = portrait A4 fit-to-1,
  Audit trail = "do not print" (hidden).
- A small "Confidential — for council use" footer on every sheet
  except Audit trail.

---

## What stays the same

The variance-analysis lens does NOT argue with these — they're
already aligned with best practice or with locked design contracts
(ADRs / EXTENDING.md / Phase D contract):

- **Numerics contract** (REQ §6, design handoff §4): tabular figures,
  comma thousands, U+2212 minus, `$` prefix, banker's rounding —
  unchanged.
- **Pink for over-drawn** + materiality-aware fill (Round 47) —
  unchanged. The new Status column reinforces, doesn't replace.
- **Phase D structured commentary** (Round 51) — unchanged on the
  input side. Move E only changes how it's rendered for human
  readers.
- **Kate Marshall's locked 12-column shape** — preserved on Sheet 2
  (Detail). New views are additive, not breaking.
- **Per-section thresholds** (Revenue / Expense, Round 21) —
  unchanged; carries through Sheet 2 + 3.
- **Faculty inference from leading digit** — unchanged; Move C
  surfaces the existing `_FACULTY_MAP` in the output.

---

## Phasing suggestion (revised — Moves A and C dropped)

Four remaining moves (B, D, E, F — A and C dropped) slot into two
rounds:

| Phase | Moves | Risk | Effort |
|---|---|---|---|
| **F1** | Move B (Status pills) + Move E (prose commentary) + Move F (cap edge cases) | Low — pure renderer changes on existing sheet | ~1 round |
| **F2** | Move D (Trend column) + Watchlist sheet | Medium — needs prior-period YTD extraction + period-over-period diff logic | ~1 round |

**Total: 2 rounds to fully shipped output redesign** (down from 4–6
in the original brief). F1 delivers the highest per-row signal lift
on day one — Status pills replace the unreadable `−2.21` percent
column, and prose commentary stops looking like JSON output. F2
adds the period-over-period dimension via a Trend column on the
main sheet plus a council-ready filtered Watchlist sheet.

The dropped Moves A (Summary sheet) and C (Faculty grouping) shaved
~3 rounds of effort off the original plan. The Move B Status pill
and Move D Trend column now carry all the "what should I look at"
signal at the row level, in lieu of an executive summary section.

---

## Open questions for Ivan

1. **Is v2.3.1.0 the right ship vehicle for F1?** ~~F1 is small
   enough to land as a patch~~. F1 is now bigger than originally
   scoped (it absorbed Move E from the dropped F2) but still
   renderer-only — safe to ship as 2.3.1.0 patch immediately after
   the next round.
2. **Do we have written confirmation from any school user that
   "Available Balance % YTD = −2.21" is confusing?** Decision: the
   actual KMAR file ("KMAR loog into this", literal `7` cells,
   `21.36` percent value) is sufficient evidence to ship F1 on. If
   Kate gives feedback later, F2 is the next intervention point.
3. ~~**Kate Marshall reaction to Summary-first sheet order?**~~
   **Resolved by dropping Move A.** The principal opens to the same
   layout they always have — no behaviour change for the recipient.
4. **Is "no spend yet" a useful Status, or noise?** Recommendation:
   only flag `No spend yet` when budget > $5K (materiality floor)
   AND calendar > 25%. Otherwise leave the row's Status blank —
   chart-of-accounts placeholders that haven't transacted aren't
   decisions. ~50% of the rows in the KMAR file are placeholders;
   without this rule the Status column is noisy.
5. **Materiality dollar floor — keep at $5,000?** Recommendation:
   yes. Without a Summary sheet's top-N ranking, the materiality
   floor only drives cell-level pink fills + the Watchlist filter
   threshold. $5K is the right level for "this row should stand out
   from the noise" at MGC's scale. The variance-analysis skill's
   $33K-$67K heuristic was for council-level reporting — moot now
   that there's no Summary "Top 3" to populate.

---

## Status

- No code changed.
- This brief saved at `handoff/round52_output_redesign_brief.md`.
- Next step on Ivan's word: confirm phasing (F1 → F2 → F3), answer
  the five open questions, and we kick off F1 in the next round.
