// Windows 11-ish window chrome for the Master Budget Tkinter recreation.
// Not a pixel-perfect OS skin — a calm frame that communicates "native Windows app"
// while letting the Fluent/vista-themed form inside speak for itself.

function WindowsWindow({ title = "Master Budget Automation Tool v1.0.2", width = 900, height = 760, children, style }) {
  return (
    <div style={{
      width, height,
      background: "#F3F3F3",
      borderRadius: 8,
      border: "1px solid #D6D6D6",
      boxShadow: "0 20px 48px -12px rgba(16,24,40,0.28), 0 4px 12px -2px rgba(16,24,40,0.12)",
      display: "flex", flexDirection: "column",
      overflow: "hidden",
      fontFamily: "'Segoe UI','Segoe UI Web',Inter,system-ui,sans-serif",
      ...style,
    }}>
      {/* Title bar */}
      <div style={{
        height: 32,
        background: "#F3F3F3",
        borderBottom: "1px solid #EAEAEA",
        display: "grid",
        gridTemplateColumns: "1fr auto",
        alignItems: "center",
        paddingLeft: 12,
        fontSize: 12,
        color: "#1A1D21",
        userSelect: "none",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* app icon: MB mark */}
          <div style={{
            width: 16, height: 16, borderRadius: 3, background: "#185787",
            color: "#fff", fontSize: 8, fontWeight: 700,
            display: "flex", alignItems: "center", justifyContent: "center",
            letterSpacing: "-0.02em",
          }}>MB</div>
          <span>{title}</span>
        </div>
        <div style={{ display: "flex", height: 32 }}>
          <WinCtl>
            <svg viewBox="0 0 10 10" width="10" height="10"><line x1="0" y1="5" x2="10" y2="5" stroke="#1A1D21" strokeWidth="1" /></svg>
          </WinCtl>
          <WinCtl>
            <svg viewBox="0 0 10 10" width="10" height="10"><rect x="0.5" y="0.5" width="9" height="9" stroke="#1A1D21" strokeWidth="1" fill="none" /></svg>
          </WinCtl>
          <WinCtl hover="#C42B1C" hoverFg="#fff">
            <svg viewBox="0 0 10 10" width="10" height="10"><line x1="0" y1="0" x2="10" y2="10" stroke="currentColor" strokeWidth="1" /><line x1="10" y1="0" x2="0" y2="10" stroke="currentColor" strokeWidth="1" /></svg>
          </WinCtl>
        </div>
      </div>
      {/* Client area */}
      <div style={{ flex: 1, background: "#F3F3F3", display: "flex", flexDirection: "column", minHeight: 0 }}>
        {children}
      </div>
    </div>
  );
}

function WinCtl({ children }) {
  return (
    <div style={{
      width: 46, height: 32,
      display: "flex", alignItems: "center", justifyContent: "center",
      color: "#1A1D21",
    }}>
      {children}
    </div>
  );
}

window.WindowsWindow = WindowsWindow;
