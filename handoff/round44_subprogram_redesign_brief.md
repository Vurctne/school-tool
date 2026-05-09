# Sub-Program Budget Report — Redesign Brief

**Date:** 2026-05-09
**Trigger:** User: "now evaluate Sub-Program Budget Report tool give
me advice to redesign whole visualization and layout."
**Lens used:** variance-analysis skill (decomposition, materiality
thresholds, narrative quality, waterfall methodology, budget-vs-
actual-vs-forecast).
**Disclaimer:** This is a UX/visualisation brief informed by
variance-analysis best practice — it is not financial advice. Any
classification of overspend or pacing is a heuristic; the user
remains the final arbiter. Quote from the skill: "All analyses
should be reviewed by qualified financial professionals before use
in reporting."
**Scope:** advice only — no code changed in this round.

---

## What the tool does today (grounded in `tools/sub_program/`)

Parses the CASES21 GL21157 PDF, shows three tabs (Revenue / Expense
/ Combined), pink-highlights rows where YTD exceeds the threshold
(default 101% — separate sliders for Revenue and Expense, range
100-120%), groups by faculty in a 220 px left rail with click-to-
filter, allows inline commentary edits, exports a 12-column XLSX
matching Kate Marshall's monthly template.

**Columns in the Revenue and Expense tabs** (`_TABLE_COLUMNS`):
Sub-program · Account · Description · Budget · YTD · Remaining ·
Used %.

**Columns in the Combined tab** (`_COMBINED_COLUMNS`): Sub-program
· Description · Revenue YTD · Expense YTD · Net YTD · Annual
budget net.

---

## What variance-analysis would say is missing

The variance-analysis skill prescribes five things every variance
report should be able to answer at a glance. The current tool
answers two of them well, two partially, one not at all.

| # | Question variance reports must answer | Current tool |
|---|---|---|
| 1 | "Which lines are off and by how much (in $)?" | **Partial** — pink highlight + Used %, but no signed dollar variance column |
| 2 | "Are these variances big enough to act on?" | **Yes** — threshold sliders |
| 3 | "Which lines should I look at first?" | **Partial** — pink rows are not sorted by impact; rail sorts alphabetically |
| 4 | "What's the trend? Is this getting worse?" | **No** — single-point snapshot, no period-over-period |
| 5 | "What's the explanation, and is action needed?" | **Partial** — freeform commentary, no structure or status |

The other variance-analysis principle worth highlighting: *colour
is never the only signal*. The current tool already follows this
(Used % > 100 accompanies the pink) — keep that posture in any
redesign.

---

## Six concrete redesign moves, in priority order

### 1 · Make variance the headline column, not "Used %"

**Why.** "Used %" is the current main signal but it's a weak one.
A line at $9,800 spent on a $10,000 budget reads as 98% — looks
fine — yet at month four of twelve it's six months ahead of
schedule and likely to blow out by year-end. Variance ($) and
Variance (%) — both signed, with direction (▲ over / ▼ under /
— flat) — are what the user actually needs to scan.

**How.** Replace the current six numeric columns:

```
Budget │ YTD │ Remaining │ Used %
```

with:

```
Budget │ YTD │ Variance $ │ Variance % │ Pacing
```

Where:

- `Variance $ = Budget − YTD` (signed). Format with U+2212 minus
  per the numerics contract; colour amount red when over, muted
  grey when under, but never as the sole signal.
- `Variance % = Variance $ / Budget` (signed).
- `Pacing = Used % ÷ Calendar %` (where Calendar % = months
  elapsed / 12, or finer if you have a period label). A Pacing
  value above 1.0 means "spending faster than the calendar
  predicts." This is the single most important early-warning
  signal in school budgeting and the current tool does not
  expose it.

**`Remaining`** falls out as derivable and can move to a tooltip.
**`Used %`** can be retained but demoted to the right-hand side or
tooltip; it duplicates `Variance %`.

### 2 · Add a Watchlist tab driven by investigation priority

**Why.** The skill ranks investigation by five signals: largest $
variance, largest % variance, unexpected direction, new variance
(was on track, now off), cumulative/trending. The current pink
highlight surfaces only "over threshold this period" — it doesn't
rank or explain.

**How.** Add a fourth tab at the top of `table_tabs` named
**Watchlist** that pre-filters to rows meeting any of these
criteria, sorted by `Variance $` descending:

- Variance $ ≥ materiality_dollar (default $5,000)
- Variance % ≥ materiality_pct (default 10%)
- Pacing ≥ 1.10 (10% ahead of calendar)
- (When prior-period file loaded:) status changed from on-track →
  off-track since prior period
- (When prior-period file loaded:) Variance $ growing
  monotonically over the last 3 periods

The Watchlist columns can be the same as #1 plus a "Why flagged"
column showing which trigger fired ("over $", "over %", "ahead of
pace", "newly off-track", "deteriorating"). Use the variance-
analysis skill's investigation-priority rule of thumb as the sort
order.

### 3 · Replace the Combined tab with a YTD-vs-Budget waterfall

**Why.** The current Combined tab is a six-column listing of net
positions per sub-program. It's a table of values, not a story.
The variance-analysis skill is explicit that this is a
prime use case for a bridge / waterfall.

**How.** Render an inline waterfall (text or canvas) that decom-
poses Annual Budget Net Position → YTD Net Position by faculty
contribution:

```
Annual budget net (planned full-year)             $185,000
  │
  │ ── Performing Arts: surplus YTD               +$12,400
  │ ── Sport: surplus YTD                          +$3,800
  │ ── Mathematics: subsidy YTD                    −$2,100
  │ ── Welfare: subsidy YTD                       −$18,600
  │ ── Library: subsidy YTD                        −$4,200
  │
YTD net (current actual position)                  $176,300
```

Below it, keep the existing per-sub-program detail table but as
a secondary "Detail" expander, not the headline. The waterfall
follows the skill's "5-8 drivers maximum, aggregate the rest into
Other" rule — if you have more than 8 faculties, fold the smallest
into "Other faculties (n)".

The skill also requires verification that the waterfall reconciles
(`Start + Σ drivers = End`) — show that as a small ✓ next to the
End value to build user trust.

### 4 · Materiality thresholds in dollars, not just percent

**Why.** Today the only threshold is `%`. A 105% line is flagged
whether it's $50 or $50,000 over. The skill prescribes dollar AND
percent thresholds with an "either exceeded" trigger.

**How.** Add two new inputs:

```python
NumberInput(
    key="materiality_dollar",
    label="Materiality threshold ($)",
    default=5000,
    inline_with_previous=True,
),
NumberInput(
    key="materiality_dollar_pct",
    label="Materiality (% of total budget)",
    default=1.0,
),
```

Compute `effective_materiality = max(materiality_dollar, total_budget × materiality_dollar_pct / 100)` — the user can set either an absolute floor or a relative one and the tool picks the larger. Lines below the materiality floor are still in the table but render in muted grey, not danger red, even if they exceed the percentage threshold. This stops the "$50 over a $30 stationery budget" noise that currently competes for attention with the "$18,000 over the IT budget" row.

### 5 · Structure the Commentary column

**Why.** The current commentary is one freeform Text widget. The
skill's "Narrative quality checklist" is six items: specific,
quantified, causal, forward-looking, actionable, concise. The skill
also lists six anti-patterns ("Various small items", "Timing"
without specifics, etc.). A freeform field cannot enforce any of
this; a structured one can prompt for it.

**How.** Replace the current single-text commentary editor with
three short fields:

| Field | Pills / values |
|---|---|
| **Driver** | One-time · Ongoing · Structural · Timing (early) · Timing (late) · Investigating |
| **Outlook** | One-time · Expected to continue · Improving · Deteriorating |
| **Action** | None · Monitor · Investigate · Update forecast |

Plus one short free-text field: "Notes (1-2 sentences)".

The XLSX output then has four cleaner columns instead of one
unstructured one, and the header rail can show counts ("3 lines:
Action = Investigate"). Existing freeform commentary should
migrate as Notes; old XLSXes still parse. The variance-analysis
skill's narrative anti-pattern list is the rationale you can cite
to school business managers — "we're moving away from 'various
small items' as a comment because it doesn't survive an audit."

### 6 · Faculty rail: contribution to variance, not used %

**Why.** The rail currently shows used %. That's a function of the
faculty's spend pattern, not its impact on the school's bottom
line. A faculty at 95% used and a faculty at 110% used look
roughly the same in the rail (both somewhere on the bar) — but if
one is a $200,000 program and the other is a $5,000 program, the
former dwarfs the latter.

**How.** Change the rail's value display from `Used %` to either:

- `Contribution to variance` — i.e., `(YTD - Budget) / Σ all faculty (YTD - Budget)` — what share of the school's total variance is this faculty driving?
- Or a mini sparkline of pacing history (when prior-period data is
  loaded).

The existing data-bar tint (green/amber/red) can stay, just
re-keyed to contribution magnitude. Faculties contributing the
most variance bubble to the top automatically.

---

## Layout sketch — ASCII version

```
┌─[ Sub-Program Budget Report ─ April 2026 ]────────────────────────────────────┐
│ INPUTS  [collapsed after first run]                                           │
│                                                                               │
│ ┌──[ FACULTY RAIL ]──┐   ┌──[ HEADER METRICS ]──────────────────────────────┐ │
│ │ Welfare ▔▔▔ 38% ↑  │   │ 47 sub-programs · 9 faculties                    │ │
│ │ Library ▔▔  18%    │   │ YTD spend 32% of annual · pacing 1.04 (slight   │ │
│ │ Sport   ▔   12%    │   │ ahead) · 5 lines on Watchlist · materiality $5k │ │
│ │ Maths   ▔   8%     │   └──────────────────────────────────────────────────┘ │
│ │ Music   ·    3%    │                                                        │
│ │ ...                │   ┌──[ TABS ]──────────────────────────────────────┐ │
│ └────────────────────┘   │  Watchlist (5)  Revenue  Expense  Bridge       │ │
│                          ├────────────────────────────────────────────────┤ │
│                          │ Sub-pgm  Description    Budget   YTD   Var $   │ │
│                          │   1100   IT general    $40,000  $58k  +$18,000│ │
│                          │   1300   Welfare        $5,000  $9.6k +$4,600 │ │
│                          │   ...                                           │ │
│                          └────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────┘
```

Where Bridge tab replaces today's Combined, Watchlist is the new
priority view, and the rail re-sorts by contribution-to-variance.

---

## Things that should NOT change

The variance-analysis lens does not argue with these — they're
already aligned with best practice or with the project's locked
design contract:

- **Numerics contract:** tabular figures, comma thousands, U+2212
  minus, `$` prefix, banker's rounding — keep everything as-is.
- **Colour-not-the-only-signal:** keep the pink highlight paired
  with a non-colour signal (today: Used %; redesign: signed
  Variance $).
- **Faculty rail width 220 px** and "Unknown" sorted last —
  unchanged.
- **Inline commentary editor on row click** — keep the entry
  point, restructure the form (move 5 above).
- **Per-section thresholds (Revenue / Expense)** — keep; useful.
  The new dollar materiality floor stacks on top.
- **Pink for over-budget, blue for subsidy, green for surplus** —
  semantics unchanged; what changes is what populates each.
- **`HL_MISMATCH` / `HL_SOURCE_ONLY` / `INFO_BG` token use** —
  unchanged. The drift guard `test_no_rogue_hex_in_tool_strings`
  stays happy.

---

## Phasing suggestion (if Ivan wants to ship incrementally)

If a single big redesign is too much for one round, the moves
above slot cleanly into three independent rounds:

| Phase | Moves | Risk | Effort |
|---|---|---|---|
| **A** | #1 (Variance + Pacing columns) + #4 (dollar materiality) | Low — column rename + formula | ~1 round |
| **B** | #2 (Watchlist tab) + #6 (rail re-key) | Medium — new sort logic, new rail computation | ~1 round |
| **C** | #3 (Bridge waterfall) + #5 (structured commentary) | High — new render path, schema migration for existing XLSXes | ~2 rounds |

Phase A delivers the biggest perceptual win (the user sees signed
$ variance and pacing immediately) for the smallest engineering
hit. Phase C is the largest but also the one that most aligns the
tool with how variance is taught in finance practice.

---

## Open questions for Ivan

1. **Do schools use period labels** (e.g. "as of April 2026") that
   the parser can extract? The Pacing calculation in #1 needs a
   `calendar_pct` value — if the source PDF carries a period
   label we read it; otherwise the user types it once per run.
2. **Is multi-period comparison in scope?** Most of the
   variance-analysis frameworks (trending, forecast accuracy,
   "newly off-track") need at least two periods of data. The
   current "Prior-period comments" file is comments-only; a
   prior-period **report** file would let us compute trends.
3. **Does Ivan want the freeform commentary preserved as a
   migration path** (move 5)? If existing XLSXes carry freeform
   text, we map it to Notes and leave Driver/Outlook/Action
   blank. Confirm before we start.
4. **Materiality default of $5,000 / 1%** — is that the right
   heuristic for Victorian government schools, or do you want it
   set lower (e.g. $1,000) to match a typical sub-program size?

---

## Status

- No code changed.
- Brief saved here.
- Next step on Ivan's word: confirm phasing (A → B → C, or one
  big round), answer the four open questions, and we kick off
  Phase A.
