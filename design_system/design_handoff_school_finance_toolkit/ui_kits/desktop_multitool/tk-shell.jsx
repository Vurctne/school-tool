// Shared Tkinter shell: Windows window chrome + left rail tool picker.
// Mimics an expanded v2 of app.py: same BudgetAutomationApp on the right,
// plus a left rail (ttk.Treeview style) for switching between tools.

function TkWindow({ title = "School Finance Toolkit v2.0.0 — Master Budget", children, width = 1200, height = 820 }) {
  return (
    <div style={{
      width, height,
      background: "#F3F3F3",
      borderRadius: 8,
      border: "1px solid #D6D6D6",
      boxShadow: "0 20px 48px -12px rgba(16,24,40,0.28), 0 4px 12px -2px rgba(16,24,40,0.12)",
      display: "flex", flexDirection: "column", overflow: "hidden",
      fontFamily: "'Segoe UI','Segoe UI Web',Inter,system-ui,sans-serif",
    }}>
      <div style={{
        height: 32, background: "#F3F3F3", borderBottom: "1px solid #EAEAEA",
        display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center",
        paddingLeft: 12, fontSize: 12, userSelect: "none",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 16, height: 16, borderRadius: 3, background: "#185787",
            color: "#fff", fontSize: 8, fontWeight: 700,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>MB</div>
          <span>{title}</span>
        </div>
        <div style={{ display: "flex", height: 32 }}>
          {["min","max","close"].map(k => (
            <div key={k} style={{ width: 46, height: 32, display: "grid", placeItems: "center" }}>
              <svg viewBox="0 0 10 10" width="10" height="10">
                {k === "min" && <line x1="0" y1="5" x2="10" y2="5" stroke="#1A1D21" />}
                {k === "max" && <rect x="0.5" y="0.5" width="9" height="9" stroke="#1A1D21" fill="none" />}
                {k === "close" && (<>
                  <line x1="0" y1="0" x2="10" y2="10" stroke="#1A1D21" />
                  <line x1="10" y1="0" x2="0" y2="10" stroke="#1A1D21" />
                </>)}
              </svg>
            </div>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>{children}</div>
    </div>
  );
}

// Left rail — ttk.Treeview look: flat, small indent carets, selection blue.
const TK_TOOLS = [
  { id: "master-budget", group: "Budget",         label: "Master Budget" },
  { id: "srp",           group: "Budget",         label: "SRP Comparison" },
  { id: "sub-program",   group: "Budget",         label: "Sub-Program Report" },
  { id: "camps",         group: "Reconciliation", label: "Camps / Activities" },
  { id: "operating",     group: "Reconciliation", label: "Operating Statement" },
];

function TkRail({ active }) {
  const groups = {};
  TK_TOOLS.forEach(t => { (groups[t.group] = groups[t.group] || []).push(t); });
  return (
    <div style={{
      width: 220, background: "#FFFFFF",
      borderRight: "1px solid #D6D6D6",
      fontSize: 13, padding: "6px 0",
      overflow: "auto",
    }}>
      {Object.keys(groups).map(g => (
        <div key={g}>
          <div style={{ padding: "4px 12px 4px 10px", color: "#1A1D21", fontWeight: 600, fontSize: 12 }}>
            <span style={{ display: "inline-block", width: 12, color: "#6B737D" }}>▾</span>{g}
          </div>
          {groups[g].map(t => {
            const on = t.id === active;
            return (
              <div key={t.id} style={{
                padding: "4px 12px 4px 30px",
                background: on ? "#3399FF" : "transparent",
                color: on ? "#FFFFFF" : "#1A1D21",
                fontSize: 13,
              }}>{t.label}</div>
            );
          })}
        </div>
      ))}
      <div style={{ borderTop: "1px solid #EAEAEA", marginTop: 8, padding: "6px 12px 6px 10px", color: "#1A1D21" }}>
        <div style={{ padding: "3px 0" }}>Instructions</div>
        <div style={{ padding: "3px 0" }}>About</div>
      </div>
    </div>
  );
}

function TkStatusBar({ left = "Ready", right = "v2.0.0 · ivan.wang@education.vic.gov.au" }) {
  return (
    <div style={{
      height: 22, background: "#F3F3F3",
      borderTop: "1px solid #D6D6D6",
      display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center",
      padding: "0 12px", fontSize: 11, color: "#555555",
    }}>
      <div>{left}</div>
      <div>{right}</div>
    </div>
  );
}

Object.assign(window, { TkWindow, TkRail, TkStatusBar, TK_TOOLS });
