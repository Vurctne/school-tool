// Shared Tkinter-flavored UI primitives for the multi-tool desktop kit.
// Mirrors the ttk/vista look: flat 1px borders, Segoe UI, Consolas logs.

const TK_BANNER = {
  neutral: { bg: "#f3f3f3", fg: "#222222" },
  success: { bg: "#e8f5e9", fg: "#0b6e0b" },
  warning: { bg: "#fff7e6", fg: "#9a6700" },
  error:   { bg: "#fdecea", fg: "#b00020" },
  info:    { bg: "#e6eef5", fg: "#124466" },
};

function TkButton({ children, disabled, focused, onClick, width, compact }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      fontFamily: "inherit", fontSize: 13,
      padding: compact ? "4px 10px" : "6px 14px", minHeight: compact ? 24 : 28,
      border: "1px solid #ADADAD", borderRadius: 2,
      background: disabled ? "#F5F5F5" : "#FDFDFD",
      color: disabled ? "#A0A0A0" : "#1A1D21",
      cursor: disabled ? "not-allowed" : "default",
      boxShadow: focused ? "0 0 0 2px rgba(43,124,184,.35)" : "inset 0 1px 0 rgba(255,255,255,.6)",
      width, whiteSpace: "nowrap",
    }}>{children}</button>
  );
}

function TkEntry({ value, placeholder, readOnly, mono, width }) {
  return (
    <div style={{
      flex: width ? undefined : 1, width, minWidth: 0,
      padding: "5px 8px",
      background: readOnly ? "#F5F5F5" : "#FFFFFF",
      border: "1px solid #ABADB3",
      borderTopColor: "#7A7A7A",
      borderRadius: 2,
      fontSize: 13, lineHeight: "18px",
      color: value ? "#1A1D21" : "#8A8F97",
      fontFamily: mono ? "'Cascadia Mono',Consolas,ui-monospace,monospace" : "inherit",
      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
    }}>
      {value || placeholder || ""}
    </div>
  );
}

function TkLabel({ children, muted, bold, fontSize = 13, style }) {
  return <div style={{
    fontSize, color: muted ? "#555555" : "#1A1D21",
    fontWeight: bold ? 700 : 400, fontFamily: "inherit", ...style,
  }}>{children}</div>;
}

function TkFileRow({ label, value, placeholder, labelWidth = 190 }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: `${labelWidth}px 1fr auto`, alignItems: "center", columnGap: 12, padding: "6px 0" }}>
      <TkLabel>{label}</TkLabel>
      <TkEntry value={value} placeholder={placeholder} mono={!!value} />
      <TkButton>Browse</TkButton>
    </div>
  );
}

function TkBanner({ level = "neutral", children }) {
  const { bg, fg } = TK_BANNER[level] || TK_BANNER.neutral;
  return (
    <div style={{
      background: bg, color: fg,
      padding: "10px 12px", fontSize: 13,
      border: "1px solid", borderColor: "#D6D6D6 #EFEFEF #EFEFEF #D6D6D6",
      boxShadow: "inset 0 0 0 1px rgba(0,0,0,.04)",
      whiteSpace: "pre-wrap", lineHeight: 1.4,
    }}>{children}</div>
  );
}

function TkProgress({ percent = 0, text = "Idle" }) {
  return (
    <>
      <TkLabel>{text}</TkLabel>
      <div style={{
        height: 16, marginTop: 6, marginBottom: 2,
        background: "#E6E6E6",
        border: "1px solid #B5B5B5", borderRadius: 2,
        overflow: "hidden",
      }}>
        <div style={{
          height: "100%", width: `${percent}%`,
          background: "linear-gradient(180deg,#9BD16D 0%,#5FA841 50%,#4E9433 50%,#6CB34A 100%)",
        }} />
      </div>
    </>
  );
}

const TK_LOG_COLORS = {
  ok:      "#0b6e0b",
  success: "#0b6e0b",
  warning: "#9a6700",
  danger:  "#b00020",
  extra:   "#2e7d32",
  muted:   "#555555",
  heading: "#1a1d21",
};

function TkLog({ lines = [], minHeight = 160 }) {
  return (
    <div style={{
      flex: 1, minHeight,
      background: "#FFFFFF",
      border: "1px solid #ABADB3", borderTopColor: "#7A7A7A",
      borderRadius: 2, padding: "8px 10px",
      fontFamily: "'Cascadia Mono',Consolas,ui-monospace,monospace",
      fontSize: 12, lineHeight: 1.55, color: "#1A1D21",
      overflow: "auto", whiteSpace: "pre-wrap",
    }}>
      {lines.map((ln, i) => (
        <div key={i} style={{
          color: ln.tag ? TK_LOG_COLORS[ln.tag] : "#1A1D21",
          fontWeight: ln.tag === "heading" ? 700 : 400,
          minHeight: "1em",
        }}>{ln.text || "\u00A0"}</div>
      ))}
    </div>
  );
}

// Treeview-style table (ttk.Treeview with vista theme).
// cols: [{key, label, width, align?, mono?}], rows: [{...keyed values, _tag?, _bg?}]
function TkTable({ cols, rows, height }) {
  return (
    <div style={{
      border: "1px solid #ABADB3", borderTopColor: "#7A7A7A",
      borderRadius: 2, background: "#FFFFFF",
      height, overflow: "auto",
    }}>
      <div style={{ display: "grid", gridTemplateColumns: cols.map(c => c.width ? `${c.width}px` : "1fr").join(" "), fontSize: 12 }}>
        {cols.map((c, i) => (
          <div key={i} style={{
            padding: "6px 8px",
            background: "#F0F0F0",
            borderBottom: "1px solid #B5B5B5",
            borderRight: i < cols.length - 1 ? "1px solid #D6D6D6" : "none",
            fontWeight: 600, fontSize: 12,
            textAlign: c.align || "left",
            position: "sticky", top: 0,
          }}>{c.label}</div>
        ))}
        {rows.map((r, ri) => cols.map((c, ci) => (
          <div key={`${ri}-${ci}`} style={{
            padding: "5px 8px",
            borderBottom: "1px solid #EAEAEA",
            borderRight: ci < cols.length - 1 ? "1px solid #F0F0F0" : "none",
            background: r._bg || (ri % 2 ? "#FAFBFC" : "#FFFFFF"),
            color: r._fg || "#1A1D21",
            textAlign: c.align || "left",
            fontFamily: c.mono ? "'Cascadia Mono',Consolas,ui-monospace,monospace" : "inherit",
            fontVariantNumeric: c.mono ? "tabular-nums" : "normal",
            fontSize: 12, lineHeight: 1.45,
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>{r[c.key]}</div>
        )))}
      </div>
    </div>
  );
}

function TkSectionHeader({ children, subtitle }) {
  return (
    <div>
      <div style={{ fontFamily: "'Segoe UI',Inter,sans-serif", fontSize: 16, fontWeight: 700, color: "#1A1D21" }}>{children}</div>
      {subtitle && <TkLabel muted style={{ marginTop: 4, maxWidth: 820, lineHeight: 1.4 }}>{subtitle}</TkLabel>}
    </div>
  );
}

Object.assign(window, {
  TkButton, TkEntry, TkLabel, TkFileRow, TkBanner, TkProgress, TkLog, TkTable, TkSectionHeader, TK_LOG_COLORS,
});
