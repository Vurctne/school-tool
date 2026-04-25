// Operating Statement — period-over-period reconciliation.

function OpstatScreen() {
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1280 }}>
      <header style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24 }}>
        <div>
          <div style={{ fontSize: 24, fontWeight: 600 }}>Operating Statement</div>
          <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 4 }}>
            Reconcile Operating Statement balances across periods and investigate movements.
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={{ fontSize: 12, color: "var(--fg-3)" }}>Compare</div>
          <PeriodChip>YTD Mar 2026</PeriodChip>
          <div style={{ fontSize: 12, color: "var(--fg-3)" }}>vs</div>
          <PeriodChip>YTD Mar 2025</PeriodChip>
        </div>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Metric label="Revenue"          value="$2,482,310" delta="+$126,400 YoY · +5.4 %" tone="up"   mono={false} />
        <Metric label="Expenditure"      value="$2,318,640" delta="+$84,520 YoY · +3.8 %"  tone="down" mono={false} />
        <Metric label="Operating result" value="+$163,670"  delta="+$41,880 YoY"           tone="up"   mono={false} />
        <Metric label="Cash at bank"     value="$1,084,200" delta="+$218,400 YoY"          tone="up"   mono={false} />
      </div>

      <Card title="Revenue vs expenditure — last 6 periods" subtitle="Monthly totals from CASES21 operating statement">
        <OpstatChart />
      </Card>

      <Card
        title="Variance analysis"
        subtitle="Lines where YoY movement exceeds the threshold"
        actions={
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--fg-3)" }}>Threshold</span>
            <Tag kind="info">≥ $5,000 or ≥ 10 %</Tag>
          </div>
        }
        style={{ padding: 0 }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "var(--bg-muted)" }}>
              {["Account", "Description", "YTD 2025", "YTD 2026", "Movement", "Comment"].map((h, i) => (
                <th key={i} style={{
                  textAlign: i >= 2 && i <= 4 ? "right" : "left",
                  padding: "10px 14px", fontSize: 11, fontWeight: 600,
                  letterSpacing: ".04em", textTransform: "uppercase", color: "var(--fg-3)",
                  borderBottom: "1px solid var(--border-subtle)",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <OsRow code="64001" desc="Voluntary contributions" y0="82,340"  y1="124,680" mov="+42,340" pct="+51.4"  up    comment="Early-payment campaign in Feb" />
            <OsRow code="71001" desc="Teaching salaries"       y0="1,128,400" y1="1,184,210" mov="+55,810" pct="+4.9" up    comment="EBA step increase · 2 new hires" />
            <OsRow code="82015" desc="Consumables"             y0="62,100"  y1="42,110"  mov="−19,990" pct="−32.2" down  comment="Deferred curriculum materials" />
            <OsRow code="82101" desc="Utilities"               y0="72,400"  y1="86,400"  mov="+14,000" pct="+19.3" down  comment="Gas tariff increase · winter usage up" />
            <OsRow code="83110" desc="ICT — subscriptions"     y0="28,400"  y1="42,840"  mov="+14,440" pct="+50.8" down  comment="Compass seats + new LMS" />
            <OsRow code="84200" desc="Camps & excursions"      y0="108,600" y1="96,200"  mov="−12,400" pct="−11.4" up    comment="Yr 9 camp moved to T3" />
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function PeriodChip({ children }) {
  return (
    <div style={{
      padding: "6px 12px", borderRadius: 999,
      background: "var(--brand-navy-tint)", color: "var(--brand-navy)",
      fontSize: 12, fontWeight: 600, letterSpacing: ".02em",
    }}>{children}</div>
  );
}

function OsRow({ code, desc, y0, y1, mov, pct, up, down, comment }) {
  const color = up ? "var(--ok-fg)" : down ? "var(--danger-fg)" : "var(--fg-1)";
  return (
    <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
      <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-2)" }}>{code}</td>
      <td style={{ padding: "10px 14px", color: "var(--fg-1)" }}>{desc}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-2)" }}>{y0}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-1)" }}>{y1}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color, fontWeight: 600 }}>{mov} · {pct}%</td>
      <td style={{ padding: "10px 14px", color: "var(--fg-2)", fontSize: 12, maxWidth: 320 }}>{comment}</td>
    </tr>
  );
}

// Simple inline revenue vs expenditure chart (no deps).
function OpstatChart() {
  const periods = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"];
  const rev = [392, 404, 368, 408, 452, 458];
  const exp = [372, 388, 396, 382, 392, 388];
  const max = 480;
  const H = 180, W = 1120;
  const cw = W / periods.length;
  const bw = 18;
  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={W} height={H + 40} viewBox={`0 0 ${W} ${H + 40}`}>
        {/* Gridlines */}
        {[0, 120, 240, 360, 480].map(v => {
          const y = H - (v / max) * H + 8;
          return (
            <g key={v}>
              <line x1={48} y1={y} x2={W - 12} y2={y} stroke="var(--border-subtle)" strokeDasharray={v === 0 ? "none" : "2 4"} />
              <text x={40} y={y + 4} textAnchor="end" fontSize="10" fill="var(--fg-3)" fontFamily="var(--font-mono)">${v}k</text>
            </g>
          );
        })}
        {periods.map((p, i) => {
          const cx = 48 + i * ((W - 60) / periods.length) + ((W - 60) / periods.length) / 2;
          const rH = (rev[i] / max) * H;
          const eH = (exp[i] / max) * H;
          return (
            <g key={p}>
              <rect x={cx - bw - 2} y={H - rH + 8} width={bw} height={rH} fill="var(--brand-navy)" rx="2" />
              <rect x={cx + 2}     y={H - eH + 8} width={bw} height={eH} fill="var(--brand-accent)" opacity="0.55" rx="2" />
              <text x={cx} y={H + 26} textAnchor="middle" fontSize="11" fill="var(--fg-2)">{p}</text>
            </g>
          );
        })}
        {/* Legend */}
        <g transform={`translate(${W - 220}, ${H + 20})`}>
          <rect x={0}  y={-8} width={10} height={10} fill="var(--brand-navy)" rx="2" />
          <text x={16} y={1}  fontSize="11" fill="var(--fg-2)">Revenue</text>
          <rect x={90} y={-8} width={10} height={10} fill="var(--brand-accent)" opacity="0.55" rx="2" />
          <text x={106} y={1} fontSize="11" fill="var(--fg-2)">Expenditure</text>
        </g>
      </svg>
    </div>
  );
}

window.OpstatScreen = OpstatScreen;
