# What's new in School Tool

This page lists what changed in each version. The most recent release
is at the top.

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
