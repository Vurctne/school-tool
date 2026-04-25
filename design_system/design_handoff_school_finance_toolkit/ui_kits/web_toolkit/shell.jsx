// Web toolkit shell — left rail + work area. Shared across all 5 tools.

const TOOLS = [
  { id: "master-budget", group: "Budget",         name: "Master Budget",        short: "MB",
    sub: "Import Compass Expense Sub-Program into Master",
    icon: (<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 3v18"/></>) },
  { id: "srp",           group: "Budget",         name: "SRP Comparison",       short: "SRP",
    sub: "Indicative vs Confirmed SRP budgets",
    icon: (<><path d="M3 3v18h18"/><path d="M7 13l3-3 4 4 5-6"/></>) },
  { id: "sub-program",   group: "Budget",         name: "Sub-Program Report",   short: "SP",
    sub: "Reformat and comment annual Sub-Program report",
    icon: (<><path d="M4 6h16M4 12h16M4 18h10"/></>) },
  { id: "camps",         group: "Reconciliation", name: "Camps / Activities",   short: "CA",
    sub: "Reconcile camp costings across workbooks",
    icon: (<><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></>) },
  { id: "operating",     group: "Reconciliation", name: "Operating Statement",  short: "OS",
    sub: "Period-over-period reconciliation",
    icon: (<><path d="M4 4h16v6H4zM4 14h16v6H4z"/></>) },
];

function Icon({ d, size = 16, stroke = 1.5, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
         strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">{d}</svg>
  );
}
window.Icon = Icon;

function Shell({ activeId = "master-budget", userName = "Ivan W.", userSchool = "Greenhill Secondary College", children }) {
  const groups = {};
  TOOLS.forEach(t => { (groups[t.group] = groups[t.group] || []).push(t); });
  return (
    <div className="vsft-typography" style={{
      display: "grid", gridTemplateColumns: "260px 1fr", gridTemplateRows: "48px 1fr 28px",
      height: "100%", minHeight: 0,
      background: "var(--bg-app)",
      color: "var(--fg-1)",
    }}>
      {/* Top bar */}
      <div style={{
        gridColumn: "1 / span 2", display: "grid",
        gridTemplateColumns: "260px 1fr auto", alignItems: "center",
        borderBottom: "1px solid var(--border-subtle)", background: "#fff",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, paddingLeft: 16 }}>
          <div style={{
            width: 26, height: 26, borderRadius: 6, background: "var(--brand-navy)",
            color: "#fff", fontSize: 11, fontWeight: 700,
            display: "grid", placeItems: "center", letterSpacing: "-0.02em",
          }}>MB</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg-1)" }}>Vic School Finance Toolkit</div>
        </div>
        <div style={{ paddingLeft: 20, fontSize: 13, color: "var(--fg-3)" }}>
          {TOOLS.find(t => t.id === activeId)?.name}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, paddingRight: 16 }}>
          <div style={{ fontSize: 12, color: "var(--fg-3)" }}>FY 2026</div>
          <div style={{ fontSize: 12, color: "var(--fg-2)" }}>{userSchool}</div>
          <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--brand-navy-tint)",
            color: "var(--brand-navy)", fontSize: 11, fontWeight: 600,
            display: "grid", placeItems: "center" }}>{userName.split(" ").map(s => s[0]).join("").slice(0,2)}</div>
        </div>
      </div>

      {/* Rail */}
      <nav style={{ borderRight: "1px solid var(--border-subtle)", background: "#fff", overflow: "auto", padding: "12px 0" }}>
        {Object.keys(groups).map(g => (
          <div key={g}>
            <div style={{
              fontSize: 11, fontWeight: 600, letterSpacing: ".06em", textTransform: "uppercase",
              color: "var(--fg-3)", padding: "10px 16px 4px",
            }}>{g}</div>
            {groups[g].map(t => {
              const active = t.id === activeId;
              return (
                <div key={t.id} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "8px 16px",
                  fontSize: 13,
                  color: active ? "var(--brand-navy)" : "var(--fg-2)",
                  background: active ? "var(--brand-navy-tint)" : "transparent",
                  borderLeft: active ? "2px solid var(--brand-navy)" : "2px solid transparent",
                  fontWeight: active ? 600 : 400,
                  cursor: "default",
                }}>
                  <Icon d={t.icon} />
                  <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                    <div>{t.name}</div>
                    {active && <div style={{ fontSize: 11, color: "var(--fg-3)", fontWeight: 400, marginTop: 1 }}>{t.sub}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
        <div style={{ borderTop: "1px solid var(--border-subtle)", marginTop: 8, paddingTop: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 16px", fontSize: 13, color: "var(--fg-2)" }}>
            <Icon d={<><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></>} /> Instructions
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 16px", fontSize: 13, color: "var(--fg-2)" }}>
            <Icon d={<><path d="M12 2l3 7h7l-5.5 4.5L18 21l-6-4-6 4 1.5-7.5L2 9h7z"/></>} /> What's new
          </div>
        </div>
      </nav>

      {/* Work area */}
      <main style={{ minWidth: 0, minHeight: 0, overflow: "auto" }}>
        {children}
      </main>

      {/* Status bar */}
      <div style={{
        gridColumn: "1 / span 2",
        borderTop: "1px solid var(--border-subtle)",
        background: "#fff",
        display: "grid", gridTemplateColumns: "260px 1fr auto",
        alignItems: "center",
        fontSize: 12, color: "var(--fg-3)",
      }}>
        <div style={{ paddingLeft: 16 }}>Ready</div>
        <div />
        <div style={{ paddingRight: 16, fontFamily: "var(--font-mono)" }}>v2.0.0 · ivan.wang@education.vic.gov.au</div>
      </div>
    </div>
  );
}

// ─── Small shared bits ───────────────────────────────────────

function Button({ kind = "primary", children, icon, disabled, small, style }) {
  const styles = {
    primary:   { background: "var(--brand-navy)", color: "#fff", borderColor: "var(--brand-navy)" },
    secondary: { background: "#fff", color: "var(--fg-1)", borderColor: "var(--border-strong)" },
    ghost:     { background: "transparent", color: "var(--fg-1)", borderColor: "transparent" },
    danger:    { background: "#fff", color: "var(--danger-fg)", borderColor: "var(--danger-border)" },
  }[kind];
  return (
    <button disabled={disabled} style={{
      display: "inline-flex", alignItems: "center", gap: 8,
      fontFamily: "inherit", fontSize: small ? 12 : 13, fontWeight: 500,
      padding: small ? "5px 10px" : "7px 14px", borderRadius: 6,
      border: "1px solid", cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.55 : 1, lineHeight: 1.2,
      ...styles, ...style,
    }}>
      {icon}{children}
    </button>
  );
}
window.Button = Button;

function Card({ children, title, subtitle, actions, style }) {
  return (
    <section style={{
      background: "var(--bg-panel)",
      border: "1px solid var(--border-subtle)",
      borderRadius: 8,
      ...style,
    }}>
      {(title || actions) && (
        <header style={{
          padding: "14px 20px",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
        }}>
          <div>
            {title && <div style={{ fontSize: 16, fontWeight: 600, color: "var(--fg-1)" }}>{title}</div>}
            {subtitle && <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 2 }}>{subtitle}</div>}
          </div>
          {actions && <div style={{ display: "flex", gap: 8 }}>{actions}</div>}
        </header>
      )}
      <div style={{ padding: 20 }}>{children}</div>
    </section>
  );
}
window.Card = Card;

function Banner({ level = "info", title, body, actions }) {
  const map = {
    info:    { bg: "var(--info-bg)",    fg: "var(--info-fg)",    bd: "var(--info-border)",    ic: <Icon d={<><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></>} /> },
    success: { bg: "var(--ok-bg)",      fg: "var(--ok-fg)",      bd: "var(--ok-border)",      ic: <Icon d={<><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></>} /> },
    warning: { bg: "var(--warn-bg)",    fg: "var(--warn-fg)",    bd: "var(--warn-border)",    ic: <Icon d={<><path d="M12 2l10 18H2z"/><path d="M12 9v5M12 18h.01"/></>} /> },
    danger:  { bg: "var(--danger-bg)",  fg: "var(--danger-fg)",  bd: "var(--danger-border)",  ic: <Icon d={<><circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/></>} /> },
  };
  const s = map[level];
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 12, alignItems: "flex-start",
      padding: "12px 14px", background: s.bg, color: s.fg,
      border: "1px solid", borderColor: s.bd, borderRadius: 6,
    }}>
      <div style={{ color: s.fg, marginTop: 1 }}>{s.ic}</div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600 }}>{title}</div>
        {body && <div style={{ fontSize: 12, marginTop: 2, opacity: 0.88 }}>{body}</div>}
      </div>
      {actions && <div style={{ display: "flex", gap: 8 }}>{actions}</div>}
    </div>
  );
}
window.Banner = Banner;

function Stepper({ step = 1, steps = ["Select files", "Review", "Export"] }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      {steps.map((s, i) => {
        const n = i + 1, done = n < step, cur = n === step;
        return (
          <React.Fragment key={s}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{
                width: 22, height: 22, borderRadius: "50%",
                background: done ? "var(--brand-navy)" : cur ? "#fff" : "var(--bg-muted)",
                color: done ? "#fff" : cur ? "var(--brand-navy)" : "var(--fg-3)",
                border: "1px solid",
                borderColor: done ? "var(--brand-navy)" : cur ? "var(--brand-navy)" : "var(--border-subtle)",
                display: "grid", placeItems: "center",
                fontSize: 11, fontWeight: 700,
              }}>{done ? "✓" : n}</div>
              <div style={{ fontSize: 13, color: cur ? "var(--fg-1)" : "var(--fg-3)", fontWeight: cur ? 600 : 400 }}>{s}</div>
            </div>
            {i < steps.length - 1 && <div style={{ flex: "0 0 36px", height: 1, background: "var(--border-subtle)" }} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}
window.Stepper = Stepper;

function FileField({ label, value, hint, placeholder = "Click Browse to select", error }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label style={{ fontSize: 13, fontWeight: 500, color: "var(--fg-1)" }}>{label}</label>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
        <div style={{
          padding: "8px 10px",
          border: "1px solid",
          borderColor: error ? "var(--danger-border)" : "var(--border-strong)",
          borderRadius: 4,
          background: error ? "var(--danger-bg)" : value ? "var(--bg-inset)" : "#fff",
          color: value ? "var(--fg-1)" : "var(--fg-3)",
          fontSize: 13, fontFamily: value ? "var(--font-mono)" : "inherit",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>{value || placeholder}</div>
        <Button kind="secondary" small>Browse</Button>
      </div>
      {hint && !error && <div style={{ fontSize: 12, color: "var(--fg-3)" }}>{hint}</div>}
      {error && <div style={{ fontSize: 12, color: "var(--danger-fg)" }}>{error}</div>}
    </div>
  );
}
window.FileField = FileField;

function Metric({ label, value, delta, tone = "neutral", mono = true }) {
  const toneColor = { up: "var(--ok-fg)", down: "var(--danger-fg)", neutral: "var(--fg-3)" }[tone];
  return (
    <div style={{
      padding: "16px 18px",
      background: "var(--bg-panel)",
      border: "1px solid var(--border-subtle)",
      borderRadius: 8,
      display: "flex", flexDirection: "column", gap: 6,
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, letterSpacing: ".02em", textTransform: "uppercase", color: "var(--fg-3)" }}>{label}</div>
      <div style={{
        fontSize: 28, fontWeight: 600, lineHeight: 1.15, color: "var(--fg-1)",
        fontFamily: mono ? "var(--font-mono)" : "inherit",
        fontVariantNumeric: "tabular-nums",
      }}>{value}</div>
      {delta && <div style={{ fontSize: 12, color: toneColor, fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>{delta}</div>}
    </div>
  );
}
window.Metric = Metric;

function Tag({ kind = "neutral", children }) {
  const map = {
    neutral: { bg: "var(--bg-muted)",     fg: "var(--fg-2)"     },
    ok:      { bg: "var(--ok-bg)",        fg: "var(--ok-fg)"    },
    warn:    { bg: "var(--warn-bg)",      fg: "var(--warn-fg)"  },
    danger:  { bg: "var(--danger-bg)",    fg: "var(--danger-fg)"},
    info:    { bg: "var(--brand-navy-tint)", fg: "var(--brand-navy)"},
  };
  const s = map[kind];
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 11, fontWeight: 600, letterSpacing: ".02em",
      padding: "2px 8px", borderRadius: 999,
      background: s.bg, color: s.fg, whiteSpace: "nowrap",
    }}>{children}</span>
  );
}
window.Tag = Tag;

window.Shell = Shell;
window.TOOLS = TOOLS;
