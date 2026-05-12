# What's new in School Tool

This page lists what changed in each version. The most recent release
is at the top.

---

## v2.4.21.0 — May 2026

* **Sub-Program Budget Report — title shows the actual print date.**
  The workbook header now reads ``Sub-Program Budget Report — 3 March
  2026`` instead of just ``March 2026``. The day of month is the YTD
  cut-off the CASES21 export was run for; council readers care which
  day the snapshot was taken since early-month vs end-of-month
  numbers can differ materially. The widened capture also flows into
  ``ReportSummary.period_label`` so any downstream consumer sees the
  fuller label.
* **Sub-Program Budget Report — Available Balance YTD formula
  matches the KMAR reference.** The formula is now
  ``=F-H-I`` (Annual Expenditure Budget − Expenditure YTD − Outstanding
  Orders), reflecting "how much expenditure budget is left to spend
  after committed orders settle". Pre-fix used ``=D+G-H-I`` (Funds +
  Revenue YTD − Expenditure YTD − Orders) which mixed cash-flow
  signals with budget-remaining signals and didn't match the
  council-facing KMAR template. For 7001 Administration:
  KMAR/v2.4.21: $581,700 − $192,126 − $1,732,527 = −$1,342,953;
  pre-fix would have shown −$1,898,217.
* **Sub-Program Budget Report — green data bar on Available Balance
  YTD column.** Excel renders an in-cell bar across J3:Jlast that
  auto-scales to the data range, giving the council reader an at-a-
  glance sense of how much budget remains across the page. Mirrors
  the data bar already on the Revenue detail sheet's % Budget
  received column for visual consistency.

---

## v2.4.20.0 — May 2026

* **Sub-Program Budget Report — XLSX restored to 4 sheets.** The
  exported workbook now ships with ``Sub Program Report`` (the
  combined Status/financials view, default active sheet),
  ``Watchlist`` (filtered subset for council attention), plus the
  legacy ``Revenue`` and ``Expenditure`` detail sheets. Round 38
  had collapsed both detail sheets into the combined view, but a
  user wanting to drill into "all Revenue lines for an auditor's
  read" or "every Expenditure account-row with its data bar" was
  left without that view. The detail sheets carry the same per-
  Account-row shape as the pre-Round-38 export (Last year actual /
  Last year budget / Annual budget / YTD / % Budget [received|
  Expended] / Uncommitted / Comments), with the green % data bar
  and pink-fill for over-budget rows.
* **Sub-Program Budget Report — new Preview tab in the in-app view.**
  A 4th tab "Preview" appears after Expense, showing the per-sub-
  program aggregated view that mirrors the XLSX Sub Program Report
  sheet's 13-column layout (CODE, Program name, Status, Funds prev.
  yrs, Budget Rev, Budget Exp, Rev YTD, Exp YTD, Orders, Avail Bal
  YTD, Avail %, Rev %, Comments). Users can see exactly what the
  export will look like without opening Excel. Pink-fill matches
  the XLSX exactly via the same is_over+is_material aggregation
  the Watchlist uses.

---

## v2.4.19.0 — May 2026

* **Sub-Program Budget Report — in-app + XLSX Watchlist sort orders
  aligned.** Pre-fix the in-app sorted per-line by
  ``-abs(variance_amount)`` while the XLSX Watchlist sheet sorted
  per-sub-program by signed available ascending — same items,
  different priority orders, so a council reader scanning either
  view saw a different row at the top. Both now use ``-abs(variance)``
  per flagged line: the XLSX picks each sub-program's max |variance|
  across its is_over+is_material lines and sorts descending, mirroring
  what an in-app user sees as the "top" item.
* **Sub-Program Budget Report — dead code removed.** Deleted
  ``compute_trend``, ``load_prior_period_ytd``, the ``_TREND_*`` pill
  constants, and ~16 related tests. Round 57 dropped the Trend
  column from the XLSX output; these helpers had no production
  callers afterwards (only their own tests kept them alive in
  grep). Net deletion ~600 lines of source + tests.

---

## v2.4.18.0 — May 2026

* **Sub-Program Budget Report — Status pill now flags Revenue-over-
  budget rows.** Pre-fix the Status pill only inspected the
  Expenditure side, so sub-programs whose Revenue YTD materially
  exceeded the Revenue budget (parent payments collected ahead of
  schedule, fundraisers that beat target, unbudgeted donations)
  printed pink-shaded on the Watchlist sheet but with Status = "On
  track" — a council-facing contradiction. 4 of the 6 Watchlist
  rows in the sample PDF exhibited this. The new "Revenue over
  budget" pill sits at the bottom of the urgency stack — over-
  collection is generally benign, but council needs to acknowledge
  it (refund parents, roll forward, adjust the budget). Expense-side
  buckets (Slightly over / Significant overspend / Investigate
  urgently) always win when both fire on the same row.
* **Sub-Program Budget Report — "Ignore amounts under" slider now
  propagates to the Excel export.** Pre-fix the `_export_xlsx` call
  dropped the user's materiality_dollar value and the writer fell
  back to its $100 default. Users who tuned the slider up (e.g. to
  $5,000 to suppress mid-range overruns) saw the in-app Watchlist
  narrow correctly but the exported XLSX kept flagging every $100+
  variance.
* **Sub-Program Budget Report — banner count reconciled with
  Watchlist count.** Pre-fix the banner read "7 lines over budget"
  while the Watchlist tab label read "Watchlist (6)" because the
  banner included immaterial is_over lines (below the $ floor) and
  the Watchlist filtered them out. Both now use the same filter.
* **Sub-Program Budget Report — auto-filled comment now matches
  pink-fill exactly.** Pre-fix the "Action needed: add commentary."
  prompt only fired on Status ∈ (Urgent / Material / Spent without
  budget). After Round 60 wired pink-fill to the per-line
  is_over+is_material signal, rows could be pink without any of
  those three statuses (notably revenue-over rows) and so printed
  with blank Comments — looking like the business manager had
  ignored the alert. Now any pink row gets the prompt.
* **Sub-Program Budget Report — help text rewritten.** Removed
  stale references to the dropped Faculty rail (Round 55) and to a
  single Over-budget threshold field (split into Revenue + Expense
  thresholds in Round 21).
* **Various code cleanups** from two parallel Opus 4.7 audits:
  inverted `_OVER_BG` comment fixed; section-banner detection uses
  `elif` so a future page with both banner texts can't accidentally
  co-fire; pre-R57 stale references to "Trend column" left in
  comments tagged for follow-up cleanup.

---

## v2.4.17.0 — May 2026

* **Sub-Program Budget Report — parser rewritten to use positional
  column extraction.** The CASES21 GL21157 PDF right-aligns every
  numeric column to a fixed x position derived from the column
  header. Previous rounds (R59/R60) tried to disambiguate columns by
  the percent value (`pct == 0` triggered "YTD column omitted"),
  which worked for many cases but was fundamentally a guess. The
  new parser reads the page's column header positions via
  pdfplumber's `extract_words()` and bins each numeric token to the
  column whose right edge x1 is closest. Blank columns simply
  produce no token at that position — which the binning correctly
  reads as "field absent → defaults to zero". 20 spot-check rows
  from the sample PDF (Revenue + Expenditure, with combinations of
  blank YTD, blank orders, blank annual budget, last-year-only)
  pinned in a parametrized regression test. The pre-R61 heuristic
  helpers (`_parse_text_lines`, `_build_line`,
  `_parse_numeric_tokens_from_parts`) deleted.

---

## v2.4.16.0 — May 2026

* **Sub-Program Budget Report — XLSX Watchlist now matches in-app
  Watchlist exactly.** Pre-fix the in-app Watchlist tab filtered on
  per-line `is_over and is_material` (so a Revenue line over-budget
  flagged the sub-program), but the exported XLSX used the
  per-sub-program Status pill which only looks at the Expenditure
  side. Sub-programs with Revenue over budget appeared on the in-app
  Watchlist but were missing from the XLSX Watchlist sheet AND not
  pink-highlighted on the main sheet. Now the writer aggregates the
  same per-line signal the in-app uses, so the two views are
  identical row-for-row. Tested against the sample PDF: 9 sub-
  programs flagged in-app, 9 sub-programs flagged in XLSX, set
  difference empty.
* **Sub-Program Budget Report — parser fix for last-year-only rows.**
  The Round-59 fix correctly handled "unbudgeted spend" rows
  (single pre token + a negative Available Balance post token, e.g.
  8650 Rowing Program "(See 8599)") but mis-classified the OTHER
  single-pre shape: rows with NO post token at all. Per the KMAR
  reference workbook, those rows have no current-year activity —
  the single token is Last-year actual, and budget / YTD / orders /
  available are all blank. Affected: 8505 School Saving Bonus
  ($255,751 misread as YTD; correct is LY_actual=$255,751,
  YTD=$0), 8655 Aerobics SLP ($1,644 same pattern), and 8505 on the
  Revenue side ($166,286 same pattern). The unbudgeted-spend case
  (1 pre + ≥1 post) still parses correctly.

---

## v2.4.15.0 — May 2026

* **Sub-Program Budget Report — parser fix for zero-spend rows.**
  The GL21157 PDF omits the YTD column entirely when a sub-program
  has had no spend this year (the percent shows as `0.00` instead).
  Pre-fix the parser silently shifted everything one column to the
  left — Annual budget read as YTD, Last-year budget read as Annual
  budget. ~20% of the rows in a typical school budget had wrong
  numbers as a result. Now disambiguates by the percent value: when
  `pct == 0`, the YTD column is treated as omitted and the Annual
  budget shifts back to its correct slot. Affected rows include
  Photography (4010), Instrumental Music (4016), Magazine (8851)
  and many others. The unbudgeted-spend pattern (e.g. School Saving
  Bonus) and the no-budget-no-spend pattern (e.g. discontinued
  programs like 4051, 4290) are also now handled correctly.
* **Sub-Program Budget Report — negative numbers print red.** Every
  dollar column in the exported XLSX now renders negatives in red
  via the Excel `[Red]` accounting format. A council reader can spot
  deficits / over-spends at a glance without having to scan for the
  leading minus sign. Also applied to the Available Balance % YTD
  and Revenue Budget % Received YTD columns.
* **Sub-Program Budget Report — pink fill follows Status, not
  Available Balance.** Pre-fix the pink "needs attention" highlight
  fired on rows where Available Balance YTD was below the dollar
  materiality floor. After Round 56 the Status pill switched to a
  pure threshold compare (`exp_ytd > expense_threshold% × annual_exp_budget`)
  but the pink fill kept the old Available Balance signal — programs
  that spend at the expected rate but whose revenue arrives in lumps
  (parent payments at start of term) sat at `available < 0` for
  half the year while Status correctly read "On track", causing
  many On-track rows to print pink. Now the pink fill fires only
  when Status itself is non-OK; the two signals can no longer
  contradict.
* **Sub-Program Budget Report — `compute_status_pill` and other
  logic.py defaults lowered to $100 too.** Round 58 (v2.4.14.0)
  lowered the user-facing NumberInput default from $5,000 to $100;
  this round propagates the same default through the function
  signatures so callers that don't pass `materiality_dollar`
  explicitly see the same behaviour as the UI.

---

## v2.4.14.0 — May 2026

* **Sub-Program Budget Report — "Ignore amounts under" default
  lowered $5,000 → $100.** The earlier $5K default suppressed too
  many mid-range overruns that a business manager would want flagged
  (e.g. a $3K stationery overspend reading as on-track). $100 is
  closer to the $500 hard noise floor compute_status_pill enforces
  internally so the slider's effect is more predictable.

---

## v2.4.13.0 — May 2026

* **Mouse wheel scrolling.** Scrollable areas in the tool view now
  respond to the mouse wheel — previously the only way to scroll was
  via the scrollbar. Wheel events are scoped to the canvas the cursor
  is over, so the binding doesn't steal scroll from sibling widgets
  (log panel, table, etc.). Same scoped pattern applied to the
  `SelectableList` primitive so any tool that uses one (User tab
  service list, future feature lists) gets wheel-scroll automatically.
* **Sub-Program Budget Report — Trend column dropped from XLSX.** The
  exported workbook is now 13 columns wide (was 14 in F2). The Trend
  column was rarely populated in practice (required a prior-period
  XLSX, which the export path didn't actually plumb through) and the
  Status pill alone carries the call-to-attention. Funds from
  Previous Years moves up to col 4 (was col 5); Comments to col 13
  (was col 14); the print area shrinks from `A1:N` to `A1:M`.
* **Sub-Program Budget Report — Funds from Previous Years now rolls
  forward.** When the user supplies a prior-period XLSX via the
  Prior-period comments picker, the writer reads the
  "Funds from Previous Years (Funds)" column from that file and
  populates the same column in the new period's output. Sub-programs
  not present in the prior file leave the cell blank (no fabricated
  zeros). Previously the column was always blank — schools had to
  re-enter their carry-forward by hand every period.
* **Sub-Program Budget Report — derived columns now use Excel
  formulas.** Three computed columns now write Excel formulas instead
  of pre-computed numeric values, so a school auditor can see how
  each number is derived:
  * Available Balance YTD: `=D{r}+G{r}-H{r}-I{r}` (Funds + Revenue
    YTD − Expenditure YTD − Outstanding orders)
  * Available Balance % YTD: `=J{r}/F{r}` (Available Balance YTD ÷
    Annual Expenditure Budget)
  * Revenue Budget % Received YTD: `=G{r}/E{r}` (Revenue YTD ÷ Annual
    Revenue Budget)

  Capped percentages (>999% / <-999%) keep the existing text marker
  fallback for display so the cap is visible on print; the cell
  comment continues to carry the uncapped value for screen readers.

---

## v2.4.12.0 — May 2026

* **Sub-Program Budget Report — pacing logic dropped.** All calendar-
  awareness has been removed from the Status pill. Previously the pill
  compared YTD spend against the calendar fraction of the year (e.g.
  "33% spent at end of April"); a sub-program flagged `No spend yet`
  if the calendar was past 25% but the budget hadn't moved. The new
  rule is a straight threshold compare: `exp_ytd > expense_threshold%
  × annual_exp_budget`. Sub-programs whose Expense YTD exceeds the
  threshold (default 101%) are flagged via the same dollar/percent
  bucketing as before — Slightly over / Significant overspend /
  Investigate urgently — but no longer get a calendar-aware free pass
  early in the year, and budgeted-but-unspent rows no longer light up
  late in the year.
* **`No spend yet` pill removed.** The pill depended on calendar
  awareness, which is gone. Budgeted programs with $0 YTD now read as
  `On track`; the YTD column itself conveys the absence of spend.
* **Watchlist narrowed to over-budget only.** The in-app Watchlist tab
  previously also included rows whose pacing exceeded 110% of calendar.
  With pacing gone, the Watchlist is strictly an over-budget list —
  rows whose Status is non-OK (Slightly over / Significant overspend /
  Investigate urgently / Spent without budget).
* **Pacing column + Pacing card + Watchlist card removed.** The
  in-app table loses the Pacing column. The metric-card strip drops
  the Pacing and Watchlist cards, leaving Sub-programs and YTD spend.
  The faculty count is also dropped from the Sub-programs card (the
  Faculty rail itself was removed in v2.4.11.0; the count was
  redundant after that).
* **Cleanups.** Removed `calendar_pct_from_period_label`,
  `_PACING_WATCH_THRESHOLD`, `_fmt_pacing`, and the `pacing` field on
  `SubProgramLine`. `compute_status_pill` lost its `available` and
  `calendar_pct` parameters in the redesign.

---

## v2.4.11.0 — May 2026

* **Sub-Program Budget Report — UI simplification.** The in-app
  view tabs go from 5 → 3: dropped the Summary tab (Round 49) and
  Bridge tab (Round 50). Watchlist is now the default landing tab,
  followed by Revenue and Expense detail tabs. The Status pill +
  Trend column on each row carry the "what should I look at"
  signal at the row level, replacing the Summary card.
* **Faculty rail removed.** The 220px left rail showing per-faculty
  contribution-to-variance is gone. The Status pill + Trend column
  surface high-impact lines without needing a separate left
  rail; saves screen real-estate and one cognitive layer for the
  non-finance reader.
* **Log panel default-collapsed.** The bottom log panel now starts
  hidden — click "Show log ▾" to expand. Reduces the perceived
  visual noise on first-run for users who don't need to debug.
  Per-tool opt-in via the new ``BaseTool.log_default_collapsed``
  attribute (defaults to False for other tools).

---

## v2.4.10.0 — May 2026

* **Sub-Program Budget Report — Trend column + Watchlist sheet.**
  The XLSX output's main sheet now leads with Status (col 3) and
  Trend (col 4) before the financials, so a non-finance reader's eye
  lands on the call-to-action before scanning dollars. The financial
  columns shift right by 2 (so Comments lands at col 14). When the
  user supplies last month's exported XLSX as the prior-period file,
  the Trend column populates with one of `New issue`, `Worsening`,
  `Stable`, `Improving`, or `Resolved` — period-over-period direction
  computed from the change in Available Balance YTD against the same
  $5K materiality floor that the Status pill uses. `Worsening` and
  `New issue` are bold-faced for print scan-ability. When no prior-
  period file is supplied, the Trend column stays blank and the
  page footer carries an explanatory note.
* **New Watchlist sheet** holds the same 14 columns but filtered to
  rows whose Status is not `On track`, sorted by absolute variance
  descending (variance-analysis skill rule: largest concerns first).
  Council members read this sheet to find what needs attention
  without scanning past every healthy row in the main report.

---

## v2.3.1.0 — May 2026

* **Sub-Program Budget Report — plain-English Status column + prose
  commentary.** The XLSX output gains a Status column (col 13) whose
  value is one of `On track`, `Slightly over`, `Material concern`,
  `Investigate urgently`, `No spend yet`, or `Spent without budget`
  — a non-finance reader can scan the column and instantly see which
  sub-programs need attention without parsing the `Available Balance
  % YTD` value (which can read `−2.21` for a 221% overdraw and which
  the actual KMAR file shows as a literal `7` for stale `=N/A`
  cells). The Status pill is sub-program-level and computed from the
  same Available Balance value the dollar column carries, so the two
  columns always tell the same story. Pills for `Material concern`,
  `Investigate urgently`, and `Spent without budget` are bold-faced
  for print scan-ability.
* **Plain-English commentary in the Comments cell.** The Round 51
  structured triplet (Driver / Outlook / Action) is now rendered as
  one or two human sentences in the visible cell — e.g. `[Driver:
  Ongoing | Action: Monitor] Reviewed by council` becomes `Ongoing
  variance — being monitored. Reviewed by council.`. Round-trip via
  prior-period files is unaffected for cells written by Round 51
  (the reader handles both forms).
* **Percent cap on Available Balance % and Revenue % Received.**
  Unbounded percents (e.g. Mathematics row's revenue ratio of 21.36
  = `2,136%`) cap at ±999% for display, with an Excel cell comment
  carrying the uncapped value for any reader who needs the truth.

---

## v2.3.0.0 — May 2026

* **Sub-Program Budget Report — structured commentary.** The single
  freeform Comments box on each sub-program is replaced with three
  short dropdowns (Driver / Outlook / Action) plus a free-text Notes
  paragraph. The dropdowns prompt for the things variance-analysis
  best practice asks every comment to answer: *what kind of variance
  is this* (Driver: One-time / Ongoing / Structural / Timing-early /
  Timing-late / Investigating), *what do we expect next* (Outlook:
  One-time / Expected to continue / Improving / Deteriorating), and
  *what are we doing about it* (Action: None / Monitor / Investigate
  / Update forecast). The XLSX output stays in Kate Marshall's
  12-column shape — the dropdowns are encoded as a short prefix on
  the Comments cell (e.g. `[Driver: Ongoing | Action: Monitor]
  Reviewed by council`). The in-app sub-row beside each line shows
  the Action tag inline (`💬  [Action: Investigate] notes`) when
  set, suppressing the prefix when the user has only written Notes.
  Pre-Phase-D files round-trip cleanly: their freeform commentary
  lands in Notes with the three dropdowns blank.

---

## v2.2.9.0 — May 2026

* **Sub-Program Budget Report — Bridge waterfall.** The Combined
  tab is replaced by a new Bridge tab. It reads top-to-bottom:
  Annual budget net → faculty drivers (each one signed, +/−,
  showing how much that faculty improved or weakened the bottom
  line) → YTD net. A **Magnitude** column on the right paints a
  text-art bar (`█████░░░░`) so the relative size of each driver
  is visible at a glance. When a school has more than 6
  contributing faculties, the smallest are folded into "Other
  faculties (n)" so the table stays readable. The tab label
  carries the headline change (`Bridge · +$8,400` or `Bridge · on
  plan`).

---

## v2.2.8.0 — May 2026

* **Sub-Program Budget Report — new Summary tab.** A plain-English
  read-down view, now the first tab. Shows period, scope (e.g.
  "47 across 9 faculties"), spend percent, spending pace ("+4%
  slightly ahead"), and the top 5 sub-programs that need attention
  named with the dollar amount they're over by. Designed for users
  with no finance background — readable in 10 seconds. Watchlist /
  Revenue / Expense / Combined remain available as drill-down tabs.
* **Smoother window dragging — even less mid-drag work.** During
  a window-edge drag, the inner-frame's scrollregion update is now
  also deferred to the same drag-settle hook the canvas-configure
  path uses (Round 43). One settle-time update at the end of the
  drag instead of a debounced one mid-drag. Stacks on top of every
  prior resize-lag round.

---

## v2.2.7.0 — May 2026

* **Plain-English labels.** Sub-Program Budget Report now uses
  everyday language instead of finance jargon:
  - The **Spending pace** column (was "Pacing") shows values like
    `+4%`, `−10%`, `On track`, or `Unknown` — no more `1.04`
    multiplier that needed a finance background to read.
  - The **Issue** column on the Watchlist (was "Why") now spells
    out the trigger: `Over budget; spending too fast`,
    `Over budget`, or `Spending too fast` — instead of the cryptic
    `Over $ + pace`, `Over $`, `Pace`.
  - The materiality input now reads **Ignore amounts under ($)**
    (was "Materiality threshold ($)") — describes what the input
    actually does.
  - The **Pacing** metric card on the result panel uses the same
    new plain-English values as the column.
* The columns **Variance $** and **Var %** keep their headers (the
  signed `+$18,000` / `−$5,000` values are already readable), and
  **Watchlist** stays as a header — both already pass the "would a
  non-finance reader understand this?" test.

---

## v2.2.6.0 — May 2026

* **Excel report — printable, percentages render correctly.** The
  exported workbook now sets up Excel's print page (landscape A4,
  fit-to-width, header rows repeat at every page break, page-number
  footer, period in the header) so a printed copy reads cleanly on
  the council table. The two percentage columns ("Available
  Balance % YTD" and "Revenue Budget % Received YTD") now use Excel's
  proper percent format — they render as e.g. `39.8%` instead of
  `0.398`. Comments wrap rather than overflowing horizontally.
* **Excel pink fill respects materiality.** A row whose Available
  Balance is over-drawn but the dollar amount is below your
  Materiality threshold no longer paints pink in the Excel — same
  rule the in-app table already uses. Stops the `$50 over a $30
  budget` rows from competing for attention with the genuinely
  large variances.
* **Zero-budget rows flagged correctly.** A sub-program with `$0`
  budget but `$X` of YTD spend is now flagged as over budget and
  appears on the Watchlist. Previously the percentage gate skipped
  these rows because Used % was reported as 0.
* **UX polish.** Watchlist trigger labels reworded for scannability
  (`Over $ + pace` → `Over budget + pace`, etc.). Faculty rail value
  drops a stray space (`38 %` → `38%`). Help text updated to match
  the current column shape; stale internal hex code removed. Empty
  Watchlist tab reads `Watchlist · all clear` rather than just
  `Watchlist (0)`.

---

## v2.2.5.0 — May 2026

* **Sub-Program Budget Report — Watchlist tab.** A new first tab
  shows just the lines that need attention right now: those that
  are over budget AND over the materiality dollar floor, OR those
  pacing 10%+ ahead of calendar (early warning before they go
  over). Sorted by absolute dollar variance — the biggest concerns
  bubble to the top. A new **Why** column on the right names which
  trigger fired: "Over $ + pace", "Over $", or "Pace".
* **Faculty rail by share of variance.** The left rail used to
  show "used %" per faculty — same for a $200,000 program at 95%
  used and a $5,000 program at 110% used, even though the impact
  is wildly different. The rail now shows each faculty's share of
  the school's total dollar variance, and faculties sort with the
  biggest impact at the top. The bar tint stays green / amber /
  red, just re-keyed to magnitude.

---

## v2.2.4.0 — May 2026

* **Sub-Program Budget Report — variance + pacing columns.** The
  result table now leads with **Variance $** (signed, with `+` for
  over-budget and `−` for under-budget), **Var %**, and **Pacing**
  (a multiplier — 1.00 means spending is exactly on calendar pace,
  1.50 means 50% ahead of calendar). The previous **Used %** and
  **Remaining** columns drop off the headline view. Pacing is the
  big new signal: a sub-program at 80% used in month 4 of 12 looks
  fine on Used %, but its pacing of 2.4× is the early warning that
  it will blow out long before December.
* **Materiality threshold ($).** A new input under the over-budget
  thresholds. Lines whose dollar variance is below this floor still
  flag in pink, but render with muted text — so the `$50 over a $30
  stationery budget` rows don't compete for attention with the
  genuinely large variances. Default $5,000.
* **Run summary metric strip.** The four cards above the result
  table now show **Sub-programs · Faculties**, **YTD spend %**,
  **Pacing** (school-wide), and **Watchlist** (count of lines that
  are both over-budget and over the materiality floor). Pacing is
  green / amber / red at 1.00 / 1.10 thresholds.

---

## v2.2.3.0 — May 2026

* **Sub-Program Budget Report — new monthly layout.** The exported
  Excel now matches the standard Monthly Sub-Program Report layout
  used in the field — 12 columns including Funds from Previous
  Years, Budget Revenue, Total Budget Allocation Expenditure,
  Revenue YTD, Expenditure YTD, Less Outstanding Orders, Available
  Balance YTD, Available Balance % YTD, Revenue Budget % Received
  YTD, and Comments. Layout contributed by **Kate Marshall**.
* **Cleaner tool frames** — removed the right-side shadow that
  appeared on every tool's input panel. The frames now sit flush
  against the rail and feel less boxed-in.
* **Smoother window resizing** — dragging the window edge no longer
  stutters while School Tool relays out the result panel. Resize
  redraws are now coalesced and only the latest size triggers the
  expensive table-rebuild step.
* **Status bar tidy-up** — the bottom-right corner now shows the
  app version only. The support email used to live there too; with
  the new Contact dialog (Privacy Policy / Contact rail link), the
  duplicate is no longer needed.
* **In-development list refresh** — "Operating Statement" was
  swapped out for "Fortnightly Salary Comparison" in the rail's
  In-development section, reflecting the next planned tool.

---

## v2.2.2.0 — May 2026

* **Sub-Program Budget Report** — fixed a bug where the report would
  run successfully but the result panel stayed empty. Reports now
  render with the full faculty rail, view tabs (Revenue / Expense /
  Combined), and over-budget highlighting as designed.
* **New support address** — please send feedback, bug reports, and
  feature requests to **feedback@schooltool.com.au**. This is the
  address shown across the app, in error messages, and in the
  Microsoft Store listing.
* **Privacy Policy** — wording trimmed and clarified.

---

## v2.2.1.0 — May 2026

This was a feature release covering several rounds of work since the
initial Store launch. The previous version had a critical rendering
bug; v2.2.2.0 above is the first version where these features
actually display correctly.

### New features

* **Master Budget Compass Autofill — Compare two budgets.** A new
  primary-style button ("Compare two budgets") next to "Generate
  budget workbook". Pick two Master Budget XLSM files; the tool reads
  three target metrics per sub-program (Total Estimated Revenue,
  Total Proposed Expenditure Current Year, Total Estimated Funds Held
  future years) and shows only the sub-programs whose values differ.
  Click "Export comparison Excel" afterwards to save the diff as
  XLSX.
* **Sub-Program Budget Report — Combined view.** Year-to-date revenue
  / expense / net per sub-program, with a side rail you can click to
  filter all three view tabs at once. Excel export now includes a
  Combined sheet via a yes/no dialog.
* **Update notifications.** When you launch School Tool, it asks the
  Microsoft Store whether any updates are pending. If yes, a small
  dialog offers to open the Store so you can install the update.
  No data is sent to our servers — the check goes via the OS-level
  Store client only.

### Polish

* **Plain-English error messages.** When something unexpected goes
  wrong, you now see what happened, how to fix it, and the technical
  detail to send support — instead of a Python traceback.
* **Press-and-hold reveal** for the HYIA calculation formula — hold
  the "Show formula" button to see the calculation, release to hide.
* **Output pill** with one-click "Open folder" link after a
  successful run, so you can find the saved file without scrolling
  through the log.
* **Auto-collapse inputs** after the first successful run, so the
  result panel gets the vertical real estate. Click "Edit ▾" on the
  summary chip to make changes.
* **Side-by-side Revenue / Expense thresholds** in Sub-Program with
  paired number boxes — type any value, the slider clamps to its
  range automatically.
* **Click-to-filter faculty rail** with a persistent chip showing
  "Showing N of M — clear filter" so you always know the current
  filter state.
* **Larger PAL Search button**, **draggable left rail divider**, and
  the **About panel** replaced with a **Privacy Policy** entry that
  shows the full policy text inline.

### Other

* **Refined PAL Search** — the redundant "Clear" button is gone;
  the action row is just the big "Open Refined PAL Search" button.
* **No new accounts, no new charges, no new data sent to our
  servers** from any of the tools. Everything continues to run
  offline on your machine.

---

## Earlier versions

Earlier versions are not listed here — they pre-date the Microsoft
Store launch and were only used during internal testing.

---

Questions, bug reports, or feature requests:
**feedback@schooltool.com.au**
