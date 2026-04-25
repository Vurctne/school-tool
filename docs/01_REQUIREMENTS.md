# Vic School Tool v2 — Requirements & Pages

> Source of truth: `design_system/design_handoff_school_finance_toolkit/` (README, EXTENDING, `colors_and_type.css`, and `ui_kits/desktop_multitool/`). Where the handoff is silent, defaults are called out explicitly below.

## 1. Product summary

A Windows desktop application shell that will eventually house multiple finance automation tools used by Victorian Government school business managers. Ships as an MSIX through the Microsoft Store on DoE-managed Windows 11 laptops.

**Release strategy (revised)**
- **v2.0.0** — shell + **HYIA Transfer Code** (free) + **Master Budget Compass Autofill** (free) + **Sub-Program Budget Report** (paid) + **User tab** (sign-in, licence, invoice, support). Ships as a **new Microsoft Store listing**, separate from v1.0.2.
- **v2.1.0** — SRP Comparison + Operating Statement added.
- **v2.2.0** — Camps Reconciliation added.
- **Master Budget Automation Tool v1.0.2** (existing Store listing) stays frozen — no updates, no migration path. v2.0.0 users install the new Store product alongside; v1 eventually deprecated once adoption warrants.

Seller: **ZXW Investment Pty Ltd** (ABN <ABN TBD>, GST status TBD). Licence price: **$550 + GST per school per year**. Support: Vurctne@gmail.com. Single-user per install; data stays on the device for tool runs; only registration/invoice/PO metadata touches the backend.

## 2. Shell (global UI)

### 2.1 Window chrome
- Windows 11 native title bar. Title string: `School Tool v2.0.0 — <Active Tool Name>`.
- SF monogram chip in the title area (16×16, navy `#185787`, white `MB`-style short mark taken from the active tool).
- Standard min / max / close buttons.
- Default window size: 1200×820. Resizable; minimum 960×640.

### 2.2 Left rail (tool picker)
- Fixed width **220 px**. White background. 1 px right border `#D6D6D6`.
- Two groups by default: **Budget** and **Reconciliation**. Groups rendered as collapsible tree items with `▾` carets. Group header bold, 12 px.
- Tool rows: 13 px, `4px 12px 4px 30px` padding. Hover: `#F0F0F0`. Selected: background `#3399FF`, text white. No icons.
- Below the tool list: a divider, then `Instructions` and `About` entries.
- Order: tools sorted by `(group, order, label)`. New tools pick their group and order.

Group → tool mapping (across all planned versions):
| Group | Tool | Short | Tier | Ships in |
|---|---|---|---|---|
| Banking | HYIA Transfer Code | HY | Free | **v2.0.0** |
| Budget | Master Budget Compass Autofill | MB | Free | **v2.0.0** |
| Budget | Sub-Program Budget Report | SP | Paid | **v2.0.0** |
| Budget | SRP Comparison | SR | Free | v2.1.0 |
| Reconciliation | Operating Statement | OS | Paid | v2.1.0 |
| Reconciliation | Camps / Activities | CA | Paid | v2.2.0 |

v2.0.0 rail order: Banking → HYIA Transfer Code · Budget → Master Budget Compass Autofill, Sub-Program Budget Report.

### 2.3 Status bar
- 22 px tall. `#F3F3F3` fill with 1 px top border.
- Left: live status message (updated by `progress()` callbacks). Default `Ready`.
- Right: `v2.0.0 · Vurctne@gmail.com`. Email pulled from `app_metadata.SUPPORT_EMAIL`.

### 2.4 Tool content area
- Flex-fills the remaining width/height. 16 px left padding. 10 px gap between sections. Background `#F3F3F3`.
- Slots: section header → file-picker rows → action button row → banner → progress → optional metric cards → log viewer and/or result table → muted footer line.

### 2.5 Global interactions
- **Tool switching**: click a rail item; shell swaps the content frame. File-picker values per tool persist in memory for the session (do not discard on switch).
- **Keyboard**: `Tab` cycles through visible widgets; `Enter` triggers focused button; `Esc` clears focus.
- **Font detection on startup**: probe `tkinter.font.families()`; if `Aptos` missing, fall back to `Segoe UI`. If `Cascadia Mono` missing, fall back to `Consolas`.
- **Copy rules**: sentence case for buttons (`Generate budget workbook`). Australian English. No emoji. Unicode minus `−` (U+2212) in negatives.
- **Per-session cache**: no disk persistence in v2. Optional `%APPDATA%/SchoolTool/session.json` reserved for a future release (`last_active_tool_id`, `last_inputs` only — never file contents).

### 2.6 Accessibility / copy baseline
- Colour is never the sole signal: negatives carry `−` sign and red fill; positives carry `+` and green fill.
- All primary buttons show a 2 px accent-blue focus ring (`rgba(43,124,184,.35)`).
- Banner text meets the WCAG AA 4.5:1 contrast already baked into the semantic token palette.

## 3. The five tools

Each tool is a `ttk.Frame` subclass (desktop) declared as a `BaseTool`. Screen layout order is identical across tools: section header → file picker rows → action buttons → banner → progress → optional metrics → log/table → muted footer. Footer line is constant: `Please send feedback to Vurctne@gmail.com`.

### 3.1 Master Budget Compass Autofill — `master-budget` — MB  (Budget, order 10)  *(free, v2.0.0)*
Port of the existing v1 Master Budget Automation Tool. **Look-and-name change only** — zero change to the underlying openpyxl logic, macro preservation, account-code matching, or output format. On identical inputs, v2's output workbook is byte-equivalent to v1.0.2's (modulo the timestamp in the filename).

Imports a Compass Expense Sub-Program export (CSV primary, XLSX/XLSM also accepted) into a Master Budget macro-enabled workbook, matches on account codes, preserves macro bindings, writes annotated output. The "Compass Autofill" name reflects what it actually does: autofills the Master Budget template from the Compass export.

**Inputs**
1. `expense_file` — Compass Expense Sub-Program export (`.csv` primary; `.xlsx` / `.xlsm` also accepted).
2. `master_file` — Master Budget template (`.xlsm`).

**Output**
- `output_file` — Annotated `.xlsm` (suggested name `Master_Budget_<period>_AUTO_<YYYYMMDD_HHMM>.xlsm`).

**Actions (row order)**
- *Generate budget workbook* (primary, focused)
- *Create suggested output name* (secondary — fills output path from source template name + timestamp)
- *Open output folder*
- *Instructions*
- *Clear*

**States**
- idle · running (progress bar, all inputs disabled) · success · warning (mismatches) · error.
- Warning banner copy (example): *Completed with 3 mismatch item(s). Highlighted rows and columns need review.*

**Result surface**
- Log viewer (min 160 px): headings, OK/warn/danger/extra/muted tagged lines (see §5).
- Openpyxl fills written to output: mismatch `#F4CCCC`, source-only `#E2F0D9`, edited (user convention) `#FFF2CC`.

### 3.2 SRP Comparison — `srp` — SR  (Budget, order 20)  *(new)*
Line-by-line compare of Indicative vs Confirmed Student Resource Package PDFs.

**Inputs**
1. `indicative_pdf` — Indicative SRP `.pdf`.
2. `confirmed_pdf` — Confirmed SRP `.pdf`.

**Output**
- `output_file` — `SRP_Compare_<year>_<timestamp>.xlsx`.

**Actions**
- *Generate comparison* (primary) · *Open output folder* · *Instructions* · *Clear*.

**Result surface**
- Info banner with line-count summary: `156 lines matched · 4 new in Confirmed · 0 removed · 12 variances > $1,000. Net +$132,750 (+2.05 %).`
- 4-column metric card row: **Indicative** · **Confirmed** · **Net variance** (tone ok/danger by sign) · **Lines changed**.
- `ttk.Treeview` result table, columns: Category · Line · Indicative · Confirmed · Variance · %. Numeric columns right-aligned, Cascadia Mono, tabular-nums. Row fills: red `#F4CCCC` (decrease), green `#E2F0D9` (increase), blue `#E6EEF5` (new in confirmed).
- Muted legend line under the table.

**Line categorisation** — every row tagged exactly one of: `unchanged`, `increased`, `decreased`, `new_in_confirmed`, `removed`.

### 3.3 Annual Sub-Program Report — `sub-program` — SP  (Budget, order 30)  *(new)*
Reformats the Annual Sub-Program Budget Report, joins in prior-period commentary, flags over-budget lines, produces a School-Council-ready workbook. Left sub-rail (inside the content frame) groups sub-programs by faculty.

**Inputs**
1. `report_file` — Sub-Program report (CASES21 GL21157 `.pdf` primary; `.xlsx` accepted if CASES21 lets the user export that way).
2. `comments_file` — Prior-period comments `.xlsx` — **optional**. If supplied, commentary is joined in; if omitted, the tool runs without the join and the output *Commentary* column is blank.

**Output**
- `output_file` — `Annual_SubProgram_<period>_AUTO_<timestamp>.xlsx`.

**Actions**
- *Generate report* (primary) · *Edit commentary…* (opens modal) · *Open output folder* · *Instructions* · *Clear*.

**Result surface**
- Info banner: *84 sub-programs across 12 faculties. YTD spend 58 % of annual. 1 line over budget: …*
- Two-column split below the banner: **faculty rail** (220 px) on the left · result table on the right.
  - Faculty rail rows: faculty name + right-aligned % used. Selected row: background `#3399FF`, text white.
- Result table columns: Sub-program · Account · Description · Budget · YTD · Remaining · Used %. Over-budget rows filled `#F4CCCC`.

**Secondary modal — *Edit commentary***: allows per-sub-program free text. Text survives session, written into the output workbook as a `Commentary` column.

### 3.4 Camps / Activities Reconciliation — `camps` — CA  (Reconciliation, order 10)  *(new, sample data pending)*
Three-way reconciliation: Camps Register × Supplier Invoices × Sub-Program Ledger. Per-activity variance with Match / Minor / Open status.

**Inputs**
1. `register_file` — Camps register `.xlsx`.
2. `invoices_file` — Supplier invoices `.xlsx`.
3. `ledger_file` — Sub-Program ledger `.xlsx`.

**Output**
- `output_file` — `Camps_Reconciliation_AUTO_<timestamp>.xlsx`.

**Actions**
- *Generate reconciliation* (primary) · *Export variance list…* · *Open output folder* · *Instructions* · *Clear*.

**Result surface**
- Warning banner: *Completed with N open items and M minor variances. $X unreconciled across K variance rows.*
- 4-metric row: Activities · Students · Reconciled (`$`, tone ok) · Unreconciled (`$`, tone warn).
- Result table: Activity · Date · Students · Invoiced · Receipted · Variance · Status. Rows highlighted `#F4CCCC` if status = *Open*, `#FFF2CC` if *Minor*.

**Status thresholds (proposed pending sample data)**
- `Match`: variance = $0.
- `Minor`: |variance| ≤ $250 and ≤ 2 % of invoiced.
- `Open`: otherwise.

> **Open risk**: sample files not yet provided. Three-way join keys, column layouts, and CASES21 ledger format will be confirmed against real exports before implementation starts. Parser code written ahead of that is scaffolding only.

### 3.6 HYIA Transfer Code Generator — `hyia` — HY  (Banking, order 10)  *(free, v2.0.0)*
Westpac High Yield Investment Account security-code calculator. Schools use this code every time they transfer funds to/from the HYIA via the HYIA Portal. Replaces the manual Excel worksheet schools have been passing around since 2007.

**Formula** (per DoE *Updated May 2022* spec):
```
Security Code = SIN + (Amount × 100) + DD + MM + YY
```
Where `Amount × 100` means "the amount with its decimal point removed, cents included" (e.g. $20,000.00 → `2000000`). Date components are **each added separately** — `16/02/07` → `16 + 2 + 7`, not `160207`.

**Worked example** — SIN 12345, amount $20,000.00, date 16/02/07:
`12345 + 2000000 + 16 + 2 + 7 = 2012370`.

**Inputs (form fields, not file pickers — see architecture update)**
1. `sin` — 4–6 digit integer, **secret input** (masked like a password, with an eye-toggle to reveal). Optionally remembered locally (see "SIN storage" below).
2. `amount` — AUD currency entry, `$` prefix, two decimal places, positive only.
3. `date` — date picker, default today.

**No output file.** The "output" is the security code itself, shown in a large monospace result area with a *Copy* button.

**Actions (row order)**
- *Generate code* (primary, focused; disabled until SIN + amount are valid).
- *Copy code*
- *Clear*
- *Instructions* (opens the DoE PDF in the default viewer; bundled as `resources/hyia_transfer_spec.pdf`).

**Result surface**
- Big result: `Security code: 2012370` in 24 px Cascadia Mono, navy foreground.
- Calculation breakdown below, muted, **with the SIN masked**:
  `***** + 2000000 + 16 + 2 + 7 = 2012370`
  (digit count preserved, value hidden; user eyeball-verifies via the total).
- Transfer log (optional, collapsible): appends every successful generation to a session-only list with timestamp, date-of-request, and masked-amount. **Never logs the SIN.** Session log is not persisted.

**States** — idle · valid (all three inputs entered, live code computed) · copied (brief confirmation pill on the Copy button) · error (e.g. SIN out of range).

**SIN storage (opt-in)**
- Checkbox under the SIN field: *"Remember SIN on this device"*.
- When ticked, SIN is encrypted with Windows **DPAPI** (`win32crypt.CryptProtectData`) and written to `%LOCALAPPDATA%\Packages\<MSIX>\LocalCache\hyia_sin.dat`. Only the same Windows user on the same machine can decrypt — survives reboots, not portable.
- Button *Forget stored SIN* deletes the file.
- Default is **unchecked**. Matches DoE advice to "safeguard the SIN".

**Non-goals**
- No network calls. Entirely offline.
- No audit trail written to disk (session-only log).
- No batch mode in v2.0.0. If a user wants 10 codes for 10 transfers, they run the tool 10 times. Batch is a v2.1 candidate if demand materialises.

**Acceptance criteria**
1. Computing the DoE worked example (12345, $20,000.00, 16/02/07) returns exactly `2012370`.
2. Computing `54321, $0.01, 01/01/26` returns `54321 + 1 + 1 + 1 + 26 = 54350`.
3. Leading zeros preserved on day/month (02 vs 2, but added as integer 2).
4. Year always treated as 2-digit — 2026 contributes `26`, not `2026`.
5. SIN input masked by default; eye-toggle reveals; never appears in logs or crash reports.
6. *Remember SIN* round-trips correctly across app restarts.

### 3.5 Operating Statement — `operating` — OS  (Reconciliation, order 20)  *(new)*
Period-over-period GL Operating Statement compare with user-configurable variance threshold.

**Inputs**
1. `current_file` — Current period GL `.xls` (legacy CASES21 export).
2. `prior_file` — Prior period GL `.xls`.

**Controls (inline with action row)**
- `$` threshold (default **5000**, numeric entry, 80 px).
- `%` threshold (default **10**, numeric entry, 50 px).
- Either threshold exceeded → line appears in variance table. Copy: `Variance threshold: [ 5000 ] $ or [ 10 ] %`.

**Output**
- `output_file` — `OpStat_Compare_<timestamp>.xlsx`.

**Actions**
- *Generate comparison* (primary) · *Open output folder* · *Instructions* · *Clear*.

**Result surface**
- Success banner: *Completed successfully. Revenue +$X (+Y %). Expenditure +$… Operating result +$…*.
- 4-metric row: Revenue (tone ok) · Expenditure · Operating result (tone ok if +, danger if −) · Cash at bank.
- Result table: Account · Description · YTD <prior year> · YTD <current year> · Movement · %. Row fills: green `#E2F0D9` for favourable movement, red `#F4CCCC` for adverse movement. *Favourable* depends on the account's natural sign (revenue up = favourable, expense down = favourable).

## 4. PDF reports (School Council submissions)

**Scope for v2.0.0**: Sub-Program Report gets the first PDF output, triggered from `Save as PDF…` secondary action on tool §3.3. All other tools declare PDF as deferred to v2.1.

**Renderer**: WeasyPrint. Templates in `reports/*.html`, shared stylesheet `reports/report.css` imports the same tokens as the product.

**Canonical template rules** (from `ui_kits/brand_type/` artboards 06a/06b):
- A4 portrait by default (794×1123 px @ 96 dpi). Wide tables use `@page { size: A4 landscape; }`.
- Margins: 80 px top, 72 px sides & bottom.
- Every page: running header (toolkit mark left, document context right), running footer (generation timestamp left, `Page N of M` right).
- Cover: 4 px navy top rule, small-caps navy section label, Source Serif 4 display title, italic subtitle, `Prepared by / Reviewed by / Document id` metadata block at foot.
- Body: small-caps navy section number above each Source Serif 4 section title; running prose in Source Serif 4; tables use Cascadia Mono tabular figures.
- Fonts **embedded once in the MSIX** (`assets/fonts/source-serif-4/…`, `assets/fonts/cascadia-mono/…`), referenced as system fonts in the PDF. Keeps each export ≈ 50 KB.
- **No draft watermarking.** Not in scope. Finals only.

## 5. Shared primitives

The shell renders these primitives from tool declarations; no tool owns its own widget toolkit.

| Primitive | Purpose | Canonical look |
|---|---|---|
| `FileRow` | Label + read-only entry + Browse button | 190 px label column, Cascadia Mono value, ellipsis overflow |
| `Banner` | Result status | 5 levels: `neutral / ok / warning / danger / info` with paired fg/bg from tokens |
| `ProgressBar` | 0–100 with text line | Windows vista gradient green |
| `LogView` | Tagged monospace text | Tags: `heading / ok / warning / danger / extra / muted` |
| `Table` | `ttk.Treeview` vista | `anchor='e'` + Cascadia Mono on numeric cols; per-row `_bg`/`_fg` via `tag_configure` |
| `Metric` | Uppercase label + mono value | 4-up grid, ~90 px tall, tone colours `ok / warn / danger` |
| `SectionHeader` | Tool title + subtitle | 16 px bold, 12 px muted subtitle |

## 6. Non-functional requirements

- **Platform**: Windows 10 build 19041+ and Windows 11 (DoE SOE). x64 only.
- **Install size**: ≤ 90 MB MSIX (v1 baseline ~30 MB; +WeasyPrint stack +fonts ≈ +45 MB).
- **Cold-start**: ≤ 3 s to first usable frame on a 4-core SOE laptop.
- **Run-time**: all heavy work on a worker thread; UI never blocks for >50 ms. Cancellation not required for v2.
- **Crash resilience**: unhandled exceptions surface as a *danger* banner with the exception message and log path (`%LOCALAPPDATA%/Packages/<MSIX>/LocalCache/logs/`). App does not crash the window.
- **Privacy**: no network calls. File contents never leave disk. No telemetry. Already documented in v1 `store/PRIVACY_POLICY.md`; update copy for v2.
- **Localisation**: en-AU only.
- **Logging**: Python stdlib `logging`, rotating file handler, max 5 × 1 MB. Level `INFO` default, `DEBUG` toggleable via env `SFTK_DEBUG=1`.

## 7. Deferred / out of scope for v2.0.0

- Web toolkit (`ui_kits/web_toolkit/`) — 12–18 months out, same registry pattern so tools port 1:1.
- PDF outputs for tools other than Sub-Program Report.
- Session persistence (`session.json`).
- Dark mode.
- Multi-monitor / DPI-scaling polish beyond what Tk 8.6 handles.

## 8. Acceptance criteria per tool

Every tool ships only when **all** of:

1. All five states render correctly (visual diff against the matching `tk-tools.jsx` artboard).
2. Happy-path end-to-end test: pick inputs → Generate → expected output file written → banner + log match spec.
3. Warning-path test: at least one mismatch/variance surfaces in the output with correct highlight colour.
4. Error-path test: a corrupt input produces a danger banner with a human-readable message (no stack trace in the UI).
5. Logs contain the run's summary line for audit trail.
6. Primary button keyboard-focusable and triggers with Enter.
7. Sentence-case copy verified; negatives use U+2212.
