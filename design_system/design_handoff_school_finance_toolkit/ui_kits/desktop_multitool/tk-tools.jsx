// Five Tkinter tool screens — each rendered as a native-feeling ttk form
// using the shared primitives in tk-primitives.jsx.
// Same data as the web kit, so the two sit side-by-side cleanly.

const ROOT_SHELL = { flex: 1, minHeight: 0, padding: 16, display: "flex", flexDirection: "column", gap: 10, background: "#F3F3F3", color: "#1A1D21", fontSize: 13 };
const FOOTER = "Please send suggestions to ivan.wang@education.vic.gov.au";

// ─── 1. Master Budget (the original tool, warning state) ────────────────
function TkMasterBudget() {
  const log = [
    { text: "Run result", tag: "heading" },
    { text: "Import completed with 3 mismatch item(s). Please review highlighted items below.", tag: "warning" },
    { text: "" },
    { text: "Output workbook: C:\\SchoolFinance\\Templates\\Master_Budget_2026_AUTO_20260422_1430.xlsm" },
    { text: "Matched rows: 247 · Matched cells: 1,481" },
    { text: "" },
    { text: "[MISMATCH] Master account codes missing from source", tag: "danger" },
    { text: "- 71022 — Casual relief", tag: "danger" },
    { text: "- 82015 — Consumables", tag: "danger" },
    { text: "" },
    { text: "[SOURCE ONLY] Source account codes not used by Master", tag: "extra" },
    { text: "- 71089 — PD (inserted in numeric position, highlighted light green)", tag: "extra" },
  ];
  return (
    <div style={ROOT_SHELL}>
      <TkSectionHeader subtitle="Import an Expense Sub-Program export into the Master Budget workbook.">Master Budget</TkSectionHeader>
      <TkFileRow label="Expense Sub-Program file" value="C:\Users\ivan\Downloads\ExpenseSubProgram_2026.xlsx" />
      <TkFileRow label="Master Budget template"   value="C:\SchoolFinance\Templates\Master_Budget_2026.xlsm" />
      <TkFileRow label="Output workbook"          value="C:\SchoolFinance\Templates\Master_Budget_2026_AUTO_20260422_1430.xlsm" />
      <div style={{ display: "flex", gap: 10, marginTop: 6, flexWrap: "wrap" }}>
        <TkButton focused>Generate budget workbook</TkButton>
        <TkButton>Create suggested output name</TkButton>
        <TkButton>Open output folder</TkButton>
        <TkButton>Instructions</TkButton>
        <TkButton>Clear</TkButton>
      </div>
      <TkBanner level="warning">Completed with 3 mismatch item(s). Highlighted rows and columns need review.</TkBanner>
      <TkProgress percent={100} text="Completed." />
      <TkLabel style={{ marginTop: 8 }}>Run summary</TkLabel>
      <TkLog lines={log} />
      <TkLabel>Completed with 3 mismatch item(s)</TkLabel>
      <TkLabel muted>{FOOTER}</TkLabel>
    </div>
  );
}

// ─── 2. SRP Comparison ─────────────────────────────────────────────────
function TkSrp() {
  const cols = [
    { key: "cat",  label: "Category",   width: 130 },
    { key: "line", label: "Line" },
    { key: "ind",  label: "Indicative", width: 110, align: "right", mono: true },
    { key: "cnf",  label: "Confirmed",  width: 110, align: "right", mono: true },
    { key: "var",  label: "Variance",   width: 110, align: "right", mono: true },
    { key: "pct",  label: "%",          width: 70,  align: "right", mono: true },
  ];
  const red = { _bg: "#F4CCCC" }, grn = { _bg: "#E2F0D9" }, inf = { _bg: "#E6EEF5" };
  const rows = [
    { cat: "Core Funding", line: "Per capita — Secondary",       ind: "3,420,000", cnf: "3,482,100", var: "+62,100",  pct: "+1.82" },
    { cat: "Core Funding", line: "Base school allocation",       ind: "1,240,000", cnf: "1,240,000", var: "0",        pct: "0.00" },
    { cat: "Equity",       line: "Equity (Social Disadvantage)", ind: "412,880",   cnf: "448,530",   var: "+35,650",  pct: "+8.63", ...grn },
    { cat: "Equity",       line: "Equity (Catch Up)",            ind: "182,000",   cnf: "168,420",   var: "−13,580",  pct: "−7.46", ...red },
    { cat: "Targeted",     line: "Students with Disability",     ind: "326,500",   cnf: "352,920",   var: "+26,420",  pct: "+8.09", ...grn },
    { cat: "Targeted",     line: "Mental Health in Schools",     ind: "—",         cnf: "42,800",    var: "new",      pct: "—",     ...inf },
    { cat: "Credits",      line: "Cash grants",                  ind: "84,000",    cnf: "79,230",    var: "−4,770",   pct: "−5.68", ...red },
    { cat: "Credits",      line: "Credit adjustments",           ind: "12,400",    cnf: "10,780",    var: "−1,620",   pct: "−13.06", ...red },
  ];
  return (
    <div style={ROOT_SHELL}>
      <TkSectionHeader subtitle="Compare Indicative vs Confirmed SRP budgets line by line.">SRP Comparison</TkSectionHeader>
      <TkFileRow label="Indicative SRP (PDF)" value="C:\Finance\SRP\2026 Indicative Budget SRP.pdf" />
      <TkFileRow label="Confirmed SRP (PDF)"  value="C:\Finance\SRP\2026 confirmed SRP Budget.pdf" />
      <TkFileRow label="Output workbook"      value="C:\Finance\SRP\SRP_Compare_2026_20260422_1502.xlsx" />
      <div style={{ display: "flex", gap: 10, marginTop: 6, flexWrap: "wrap" }}>
        <TkButton focused>Generate comparison</TkButton>
        <TkButton>Open output folder</TkButton>
        <TkButton>Instructions</TkButton>
        <TkButton>Clear</TkButton>
      </div>
      <TkBanner level="info">156 lines matched · 4 new in Confirmed · 0 removed · 12 variances {'>'} $1,000. Net +$132,750 (+2.05 %).</TkBanner>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginTop: 4 }}>
        <TkMetric label="Indicative"     value="$6,482,130" />
        <TkMetric label="Confirmed"      value="$6,614,880" />
        <TkMetric label="Net variance"   value="+$132,750" tone="ok" />
        <TkMetric label="Lines changed"  value="27 / 156" />
      </div>
      <TkLabel style={{ marginTop: 6 }}>Line-by-line comparison</TkLabel>
      <TkTable cols={cols} rows={rows} height={260} />
      <TkLabel muted>Red fill = decrease. Green fill = increase. Blue fill = new line in Confirmed.</TkLabel>
      <TkLabel muted>{FOOTER}</TkLabel>
    </div>
  );
}

// ─── 3. Sub-Program Report ─────────────────────────────────────────────
function TkSubProgram() {
  const cols = [
    { key: "sp",   label: "Sub-program", width: 90,  mono: true },
    { key: "acc",  label: "Account",     width: 80,  mono: true },
    { key: "desc", label: "Description" },
    { key: "bud",  label: "Budget",     width: 90,  align: "right", mono: true },
    { key: "ytd",  label: "YTD",        width: 90,  align: "right", mono: true },
    { key: "rem",  label: "Remaining",  width: 90,  align: "right", mono: true },
    { key: "used", label: "Used %",     width: 70,  align: "right", mono: true },
  ];
  const over = { _bg: "#F4CCCC" };
  const rows = [
    { sp: "10110", acc: "82015", desc: "Consumables — paper & print",     bud: "8,400",  ytd: "6,380",  rem: "2,020", used: "76" },
    { sp: "10110", acc: "82020", desc: "Textbooks & reading resources",   bud: "14,200", ytd: "9,580",  rem: "4,620", used: "67" },
    { sp: "10110", acc: "82210", desc: "Excursion costs",                 bud: "4,800",  ytd: "3,960",  rem: "840",   used: "83" },
    { sp: "10120", acc: "82015", desc: "Consumables",                     bud: "3,200",  ytd: "2,040",  rem: "1,160", used: "64" },
    { sp: "10120", acc: "82320", desc: "PD — Literacy coaching",          bud: "6,400",  ytd: "6,820",  rem: "−420",  used: "107", ...over },
    { sp: "10130", acc: "82020", desc: "Senior texts — VCE",              bud: "12,600", ytd: "4,120",  rem: "8,480", used: "33" },
  ];
  return (
    <div style={ROOT_SHELL}>
      <TkSectionHeader subtitle="Reformat and comment the Annual Sub-Program Budget report.">Annual Sub-Program Budget Report</TkSectionHeader>
      <TkFileRow label="Sub-Program report (XLSX)" value="C:\Finance\Reports\Annual Subprogram Budget Report Jun25.xlsx" />
      <TkFileRow label="Last-period comments"      value="C:\Finance\Reports\SubProgram_comments_202412.xlsx" />
      <TkFileRow label="Output workbook"           value="C:\Finance\Reports\Annual_SubProgram_Jun25_AUTO_20260422_1510.xlsx" />
      <div style={{ display: "flex", gap: 10, marginTop: 6, flexWrap: "wrap" }}>
        <TkButton focused>Generate report</TkButton>
        <TkButton>Edit commentary…</TkButton>
        <TkButton>Open output folder</TkButton>
        <TkButton>Instructions</TkButton>
        <TkButton>Clear</TkButton>
      </div>
      <TkBanner level="info">84 sub-programs across 12 faculties. YTD spend 58 % of annual. 1 line over budget: 10120/82320 PD — Literacy coaching (+$420).</TkBanner>
      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 10, marginTop: 4, minHeight: 0, flex: 1 }}>
        <div style={{
          border: "1px solid #ABADB3", borderTopColor: "#7A7A7A", borderRadius: 2, background: "#FFFFFF",
          fontSize: 12, overflow: "auto",
        }}>
          {[
            ["English",         "72", true],
            ["Mathematics",     "58", false],
            ["Science",         "64", false],
            ["Humanities",      "49", false],
            ["LOTE",            "41", false],
            ["The Arts",        "55", false],
            ["HPE",             "83", false],
            ["Technology",      "37", false],
            ["Wellbeing",       "66", false],
            ["Library",         "51", false],
            ["Administration",  "60", false],
            ["Facilities",      "71", false],
          ].map(([n, p, on], i) => (
            <div key={n} style={{
              padding: "5px 10px",
              background: on ? "#3399FF" : (i % 2 ? "#FAFBFC" : "#FFFFFF"),
              color: on ? "#FFFFFF" : "#1A1D21",
              display: "grid", gridTemplateColumns: "1fr auto", gap: 8,
              borderBottom: "1px solid #EAEAEA",
            }}>
              <span>{n}</span>
              <span style={{ fontFamily: "'Cascadia Mono',Consolas,monospace", fontVariantNumeric: "tabular-nums" }}>{p} %</span>
            </div>
          ))}
        </div>
        <TkTable cols={cols} rows={rows} />
      </div>
      <TkLabel muted>{FOOTER}</TkLabel>
    </div>
  );
}

// ─── 4. Camps / Activities Reconciliation ──────────────────────────────
function TkCamps() {
  const cols = [
    { key: "name",     label: "Activity" },
    { key: "date",     label: "Date",       width: 90,  mono: true },
    { key: "students", label: "Students",   width: 80,  align: "right", mono: true },
    { key: "inv",      label: "Invoiced",   width: 90,  align: "right", mono: true },
    { key: "rec",      label: "Receipted",  width: 90,  align: "right", mono: true },
    { key: "var",      label: "Variance",   width: 90,  align: "right", mono: true },
    { key: "status",   label: "Status",     width: 110 },
  ];
  const red = { _bg: "#F4CCCC" }, ylw = { _bg: "#FFF2CC" };
  const rows = [
    { name: "Yr 9 City Experience",   date: "18/03/2026", students: "148", inv: "42,380", rec: "42,380", var: "0",      status: "Match" },
    { name: "Yr 7 Camp Oasis",        date: "24/02/2026", students: "182", inv: "38,220", rec: "38,040", var: "+180",   status: "Minor", ...ylw },
    { name: "Instrumental tour",      date: "09/05/2026", students: "26",  inv: "8,140",  rec: "8,140",  var: "0",      status: "Match" },
    { name: "Yr 10 Ski camp",         date: "01/08/2026", students: "64",  inv: "51,840", rec: "45,200", var: "+6,640", status: "Open",  ...red },
    { name: "Debating state finals",  date: "14/06/2026", students: "8",   inv: "620",    rec: "620",    var: "0",      status: "Match" },
    { name: "Yr 11 Outdoor Ed",       date: "20/04/2026", students: "42",  inv: "26,880", rec: "21,540", var: "+5,340", status: "Open",  ...red },
    { name: "Art gallery excursion",  date: "30/04/2026", students: "16",  inv: "640",    rec: "640",    var: "0",      status: "Match" },
  ];
  return (
    <div style={ROOT_SHELL}>
      <TkSectionHeader subtitle="Reconcile camp costings across the Camps register, supplier invoices, and Sub-Program ledger.">Camps / Activities Reconciliation</TkSectionHeader>
      <TkFileRow label="Camps register"      value="C:\Finance\Camps\Camps_Register_2026.xlsx" />
      <TkFileRow label="Supplier invoices"   value="C:\Finance\Camps\Invoices_S1_2026.xlsx" />
      <TkFileRow label="Sub-Program ledger"  value="C:\Finance\Camps\SubProgram_30120_30140.xlsx" />
      <TkFileRow label="Output workbook"     value="C:\Finance\Camps\Camps_Reconciliation_AUTO_20260422_1518.xlsx" />
      <div style={{ display: "flex", gap: 10, marginTop: 6, flexWrap: "wrap" }}>
        <TkButton focused>Generate reconciliation</TkButton>
        <TkButton>Export variance list…</TkButton>
        <TkButton>Open output folder</TkButton>
        <TkButton>Instructions</TkButton>
        <TkButton>Clear</TkButton>
      </div>
      <TkBanner level="warning">Completed with 2 open items and 1 minor variance. $13,780 unreconciled across 7 variance rows.</TkBanner>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginTop: 4 }}>
        <TkMetric label="Activities"       value="12" />
        <TkMetric label="Students"         value="486" />
        <TkMetric label="Reconciled"       value="$184,210" tone="ok" />
        <TkMetric label="Unreconciled"     value="$13,780"  tone="warn" />
      </div>
      <TkLabel style={{ marginTop: 6 }}>Activities</TkLabel>
      <TkTable cols={cols} rows={rows} height={220} />
      <TkLabel muted>{FOOTER}</TkLabel>
    </div>
  );
}

// ─── 5. Operating Statement ────────────────────────────────────────────
function TkOpstat() {
  const cols = [
    { key: "code", label: "Account",     width: 80,  mono: true },
    { key: "desc", label: "Description" },
    { key: "y0",   label: "YTD 2025",    width: 95,  align: "right", mono: true },
    { key: "y1",   label: "YTD 2026",    width: 95,  align: "right", mono: true },
    { key: "mov",  label: "Movement",    width: 100, align: "right", mono: true },
    { key: "pct",  label: "%",           width: 70,  align: "right", mono: true },
  ];
  const up = { _bg: "#E2F0D9" }, dn = { _bg: "#F4CCCC" };
  const rows = [
    { code: "64001", desc: "Voluntary contributions", y0: "82,340",    y1: "124,680",   mov: "+42,340", pct: "+51.4", ...up },
    { code: "71001", desc: "Teaching salaries",       y0: "1,128,400", y1: "1,184,210", mov: "+55,810", pct: "+4.9",  ...dn },
    { code: "82015", desc: "Consumables",             y0: "62,100",    y1: "42,110",    mov: "−19,990", pct: "−32.2", ...up },
    { code: "82101", desc: "Utilities",               y0: "72,400",    y1: "86,400",    mov: "+14,000", pct: "+19.3", ...dn },
    { code: "83110", desc: "ICT — subscriptions",     y0: "28,400",    y1: "42,840",    mov: "+14,440", pct: "+50.8", ...dn },
    { code: "84200", desc: "Camps & excursions",      y0: "108,600",   y1: "96,200",    mov: "−12,400", pct: "−11.4", ...up },
  ];
  return (
    <div style={ROOT_SHELL}>
      <TkSectionHeader subtitle="Reconcile Operating Statement balances period-over-period.">Operating Statement</TkSectionHeader>
      <TkFileRow label="Current period (XLS)" value="C:\Finance\OpStatement\GL21157_202603.xls" />
      <TkFileRow label="Prior period (XLS)"   value="C:\Finance\OpStatement\GL21157_202503.xls" />
      <TkFileRow label="Output workbook"      value="C:\Finance\OpStatement\OpStat_Compare_20260422_1525.xlsx" />
      <div style={{ display: "flex", gap: 10, marginTop: 6, alignItems: "center", flexWrap: "wrap" }}>
        <TkButton focused>Generate comparison</TkButton>
        <TkButton>Open output folder</TkButton>
        <TkButton>Instructions</TkButton>
        <TkButton>Clear</TkButton>
        <div style={{ marginLeft: 16, fontSize: 12, color: "#555555" }}>
          Variance threshold:
        </div>
        <TkEntry value="5000" width={80} mono />
        <div style={{ fontSize: 12, color: "#555555" }}>$ or</div>
        <TkEntry value="10" width={50} mono />
        <div style={{ fontSize: 12, color: "#555555" }}>%</div>
      </div>
      <TkBanner level="success">Completed successfully. Revenue +$126,400 (+5.4 %). Expenditure +$84,520 (+3.8 %). Operating result +$41,880.</TkBanner>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginTop: 4 }}>
        <TkMetric label="Revenue"          value="$2,482,310" tone="ok" />
        <TkMetric label="Expenditure"      value="$2,318,640" />
        <TkMetric label="Operating result" value="+$163,670"  tone="ok" />
        <TkMetric label="Cash at bank"     value="$1,084,200" />
      </div>
      <TkLabel style={{ marginTop: 6 }}>Variance analysis (lines exceeding threshold)</TkLabel>
      <TkTable cols={cols} rows={rows} height={200} />
      <TkLabel muted>{FOOTER}</TkLabel>
    </div>
  );
}

function TkMetric({ label, value, tone }) {
  const fg = tone === "ok" ? "#0b6e0b" : tone === "warn" ? "#9a6700" : tone === "danger" ? "#b00020" : "#1A1D21";
  return (
    <div style={{
      background: "#FFFFFF", border: "1px solid #ABADB3", borderTopColor: "#7A7A7A", borderRadius: 2,
      padding: "8px 12px", display: "flex", flexDirection: "column", gap: 3,
    }}>
      <div style={{ fontSize: 11, color: "#555555", textTransform: "uppercase", letterSpacing: ".04em", fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: fg, fontFamily: "'Cascadia Mono',Consolas,monospace", fontVariantNumeric: "tabular-nums" }}>{value}</div>
    </div>
  );
}

Object.assign(window, { TkMasterBudget, TkSrp, TkSubProgram, TkCamps, TkOpstat });
