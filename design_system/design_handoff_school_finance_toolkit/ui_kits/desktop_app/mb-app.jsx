// Master Budget Automation Tool — recreation of the Tkinter app (app.py).
// Faithful to the source: same row order, same labels, same banner colors,
// Consolas log. Takes `state` to render the four UI states (idle, running,
// success-no-issues, warning-with-mismatches, error).

const MB_BANNER = {
  neutral: { bg: "#f3f3f3", fg: "#222222" },
  success: { bg: "#e8f5e9", fg: "#0b6e0b" },
  warning: { bg: "#fff7e6", fg: "#9a6700" },
  error:   { bg: "#fdecea", fg: "#b00020" },
};

const MB_LOG_COLORS = {
  success: "#0b6e0b",
  warning: "#9a6700",
  danger:  "#b00020",
  ok:      "#0b6e0b",
  extra:   "#2e7d32",
  muted:   "#555555",
  heading: "#1a1d21",
};

// ttk.Button — flat Fluent/vista look. Slight border, 1 px inset on press.
function TtkButton({ children, kind = "normal", disabled, focused, width }) {
  const base = {
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    fontFamily: "inherit", fontSize: 13,
    padding: "6px 14px", minHeight: 28,
    border: "1px solid #ADADAD", borderRadius: 2,
    background: disabled ? "#F5F5F5" : "#FDFDFD",
    color: disabled ? "#A0A0A0" : "#1A1D21",
    cursor: disabled ? "not-allowed" : "default",
    boxShadow: focused ? "0 0 0 2px rgba(43,124,184,.35)" : "inset 0 1px 0 rgba(255,255,255,.6)",
    width,
  };
  return <button style={base} disabled={disabled}>{children}</button>;
}

function TtkEntry({ value, placeholder }) {
  return (
    <div style={{
      flex: 1, minWidth: 0,
      padding: "5px 8px",
      background: "#FFFFFF",
      border: "1px solid #ABADB3",
      borderTopColor: "#7A7A7A",
      borderRadius: 2,
      fontSize: 13, lineHeight: "18px",
      color: value ? "#1A1D21" : "#8A8F97",
      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
      fontFamily: "inherit",
    }}>
      {value || placeholder || ""}
    </div>
  );
}

function FileRow({ label, value, placeholder }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "190px 1fr auto", alignItems: "center", columnGap: 12, padding: "6px 0" }}>
      <label style={{ fontSize: 13, color: "#1A1D21" }}>{label}</label>
      <TtkEntry value={value} placeholder={placeholder} />
      <TtkButton>Browse</TtkButton>
    </div>
  );
}

function Banner({ level = "neutral", children }) {
  const { bg, fg } = MB_BANNER[level] || MB_BANNER.neutral;
  return (
    <div style={{
      background: bg,
      color: fg,
      padding: "10px 12px",
      fontSize: 13,
      // Tkinter relief=groove: 1-1 dark-light-light-dark. We approximate:
      border: "1px solid",
      borderColor: "#D6D6D6 #EFEFEF #EFEFEF #D6D6D6",
      boxShadow: "inset 0 0 0 1px rgba(0,0,0,.04)",
      marginTop: 10, marginBottom: 10,
      whiteSpace: "pre-wrap",
      lineHeight: 1.4,
    }}>{children}</div>
  );
}

function Progress({ percent = 0, text = "Idle" }) {
  return (
    <>
      <div style={{ fontSize: 13, color: "#1A1D21" }}>{text}</div>
      <div style={{
        height: 16, marginTop: 6, marginBottom: 2,
        background: "#E6E6E6",
        border: "1px solid #B5B5B5", borderRadius: 2,
        overflow: "hidden",
      }}>
        <div style={{
          height: "100%", width: `${percent}%`,
          background: "linear-gradient(180deg,#9BD16D 0%,#5FA841 50%,#4E9433 50%,#6CB34A 100%)",
          transition: "width .2s",
        }} />
      </div>
    </>
  );
}

// Log line renderer. Mirrors _append_line with tags.
function Log({ lines = [] }) {
  return (
    <div style={{
      flex: 1, minHeight: 0,
      background: "#FFFFFF",
      border: "1px solid #ABADB3",
      borderTopColor: "#7A7A7A",
      borderRadius: 2,
      padding: "8px 10px",
      fontFamily: "'Cascadia Mono',Consolas,ui-monospace,monospace",
      fontSize: 12,
      lineHeight: 1.55,
      color: "#1A1D21",
      overflow: "auto",
      whiteSpace: "pre-wrap",
    }}>
      {lines.map((ln, i) => (
        <div key={i} style={{
          color: ln.tag ? MB_LOG_COLORS[ln.tag] : "#1A1D21",
          fontWeight: ln.tag === "heading" ? 700 : 400,
          minHeight: "1em",
        }}>{ln.text || "\u00A0"}</div>
      ))}
    </div>
  );
}

// ─── State presets ───────────────────────────────────────────

const IDLE = {
  source: "", template: "", output: "",
  banner: { level: "neutral", text: "Waiting to run." },
  progress: { percent: 0, text: "Idle" },
  status: "Ready",
  running: false,
  log: [],
};

const RUNNING = {
  source: "C:\\Users\\ivan\\Downloads\\ExpenseSubProgram_2026.xlsx",
  template: "C:\\SchoolFinance\\Templates\\Master_Budget_2026.xlsm",
  output:   "C:\\SchoolFinance\\Templates\\Master_Budget_2026_AUTO_20260422_1430.xlsm",
  banner: { level: "neutral", text: "Running import. Please wait..." },
  progress: { percent: 42, text: "42% - Writing Master sheet" },
  status: "Writing Master sheet",
  running: true,
  log: [
    { text: "Import started..." },
    { text: "Tip: the app stays responsive while the workbook is being processed." },
    { text: "" },
    { text: "5% - Reading source workbook", tag: "muted" },
    { text: "18% - Validating account codes", tag: "muted" },
    { text: "30% - Opening Master template", tag: "muted" },
    { text: "42% - Writing Master sheet", tag: "muted" },
  ],
};

const SUCCESS = {
  source: "C:\\Users\\ivan\\Downloads\\ExpenseSubProgram_2026.xlsx",
  template: "C:\\SchoolFinance\\Templates\\Master_Budget_2026.xlsm",
  output:   "C:\\SchoolFinance\\Templates\\Master_Budget_2026_AUTO_20260422_1430.xlsm",
  banner: { level: "success", text: "Completed successfully. No mismatch or concern found." },
  progress: { percent: 100, text: "Completed." },
  status: "Completed - no issues found",
  running: false,
  log: [
    { text: "Run result", tag: "heading" },
    { text: "No mismatch or concern found. Import completed successfully.", tag: "success" },
    { text: "" },
    { text: "Output workbook: C:\\SchoolFinance\\Templates\\Master_Budget_2026_AUTO_20260422_1430.xlsm" },
    { text: "Report file:    C:\\SchoolFinance\\Templates\\Master_Budget_2026_AUTO_20260422_1430.report.txt" },
    { text: "Matched rows:   247" },
    { text: "Matched cells:  1,483" },
    { text: "" },
    { text: "[OK] Master account codes missing from source", tag: "ok" },
    { text: "Tracked account mismatch check only includes 5-digit account codes starting with 7 or 8.", tag: "muted" },
    { text: "None" },
    { text: "" },
    { text: "[OK] Source account codes not used by Master", tag: "ok" },
    { text: "None" },
  ],
};

const WARNING = {
  source: "C:\\Users\\ivan\\Downloads\\ExpenseSubProgram_2026.xlsx",
  template: "C:\\SchoolFinance\\Templates\\Master_Budget_2026.xlsm",
  output:   "C:\\SchoolFinance\\Templates\\Master_Budget_2026_AUTO_20260422_1430.xlsm",
  banner: { level: "warning", text: "Completed with 3 mismatch item(s). Highlighted rows and columns need review." },
  progress: { percent: 100, text: "Completed." },
  status: "Completed with 3 mismatch item(s)",
  running: false,
  log: [
    { text: "Run result", tag: "heading" },
    { text: "Import completed with 3 mismatch item(s). Please review highlighted items below.", tag: "warning" },
    { text: "" },
    { text: "Output workbook: C:\\SchoolFinance\\Templates\\Master_Budget_2026_AUTO_20260422_1430.xlsm" },
    { text: "Report file:    C:\\SchoolFinance\\Templates\\Master_Budget_2026_AUTO_20260422_1430.report.txt" },
    { text: "Matched rows:   247" },
    { text: "Matched cells:  1,481" },
    { text: "" },
    { text: "[MISMATCH] Master account codes missing from source", tag: "danger" },
    { text: "Tracked account mismatch check only includes 5-digit account codes starting with 7 or 8.", tag: "muted" },
    { text: "- 71022 — Casual relief", tag: "danger" },
    { text: "- 82015 — Consumables", tag: "danger" },
    { text: "" },
    { text: "[SOURCE ONLY] Source account codes not used by Master", tag: "extra" },
    { text: "These tracked source account codes exist in the source file but not on Master. They are added into the", tag: "muted" },
    { text: "Master sheet in numeric position with descriptions and light green highlighting.", tag: "muted" },
    { text: "- 71089 — PD", tag: "extra" },
  ],
};

const ERROR_STATE = {
  source: "C:\\Users\\ivan\\Downloads\\ExpenseSubProgram_2026.xlsx",
  template: "C:\\SchoolFinance\\Templates\\Master_Budget_2026.xlsm",
  output:   "C:\\SchoolFinance\\Templates\\Master_Budget_2026.xlsm",
  banner: { level: "error", text: "Error: Output workbook cannot be the same as the Master Budget template. Choose a different output file name." },
  progress: { percent: 0, text: "Stopped." },
  status: "Error",
  running: false,
  log: [
    { text: "Import started..." },
    { text: "" },
    { text: "Budget automation error: Output workbook cannot be the same as the Master Budget template.", tag: "danger" },
    { text: "Choose a different output file name, or click Create suggested output name.", tag: "muted" },
  ],
};

const MB_STATES = { idle: IDLE, running: RUNNING, success: SUCCESS, warning: WARNING, error: ERROR_STATE };

// ─── The app ─────────────────────────────────────────────────

function MasterBudgetApp({ stateName = "idle" }) {
  const s = MB_STATES[stateName] || IDLE;
  return (
    <div style={{
      flex: 1, minHeight: 0,
      padding: 20,
      display: "flex", flexDirection: "column",
      background: "#F3F3F3",
      color: "#1A1D21",
      fontSize: 13,
    }}>
      {/* Title */}
      <div style={{ fontFamily: "'Segoe UI',Inter,sans-serif", fontSize: 16, fontWeight: 700, color: "#1A1D21" }}>
        Master Budget Automation Tool v1.0.2
      </div>
      <div style={{ fontSize: 13, color: "#1A1D21", marginTop: 8, marginBottom: 16, lineHeight: 1.4, maxWidth: 820 }}>
        Use this tool to import an Expense Sub-Program export into the Master Budget workbook without using OFFSET/MATCH formulas.
      </div>

      {/* File rows */}
      <FileRow label="Expense Sub-Program file" value={s.source} />
      <FileRow label="Master Budget template"   value={s.template} />
      <FileRow label="Output workbook"          value={s.output} />

      {/* Button row */}
      <div style={{ display: "flex", gap: 10, marginTop: 10, marginBottom: 4, flexWrap: "wrap" }}>
        <TtkButton disabled={s.running} focused={stateName === "idle"}>Generate budget workbook</TtkButton>
        <TtkButton disabled={s.running}>Create suggested output name</TtkButton>
        <TtkButton disabled={s.running}>Open output folder</TtkButton>
        <TtkButton>Instructions</TtkButton>
        <TtkButton disabled={s.running}>Clear</TtkButton>
      </div>

      {/* Banner (grooved Tk label) */}
      <Banner level={s.banner.level}>{s.banner.text}</Banner>

      {/* Progress */}
      <Progress percent={s.progress.percent} text={s.progress.text} />

      {/* Run summary label */}
      <div style={{ marginTop: 14, fontSize: 13, color: "#1A1D21" }}>Run summary</div>

      {/* Log */}
      <div style={{ marginTop: 6, flex: 1, minHeight: 180, display: "flex", flexDirection: "column" }}>
        <Log lines={s.log} />
      </div>

      {/* Status + footer */}
      <div style={{ marginTop: 8, fontSize: 13, color: "#1A1D21" }}>{s.status}</div>
      <div style={{ marginTop: 4, fontSize: 13, color: "#555555" }}>
        Please send suggestions to ivan.wang@education.vic.gov.au
      </div>
    </div>
  );
}

window.MasterBudgetApp = MasterBudgetApp;
