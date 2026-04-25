// SRP Comparison — Indicative vs Confirmed SRP budgets.

function SrpScreen() {
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1280 }}>
      <header style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24 }}>
        <div>
          <div style={{ fontSize: 24, fontWeight: 600 }}>SRP Comparison</div>
          <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 4 }}>
            Compare Indicative vs Confirmed Student Resource Package budgets line by line.
          </div>
        </div>
        <Stepper step={3} steps={["Select files", "Match", "Compare"]} />
      </header>

      <Banner
        level="info"
        title="Comparing 2026 Confirmed against 2026 Indicative"
        body="156 lines matched · 4 new in Confirmed · 0 removed · 12 variances > $1,000"
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Metric label="Indicative total"       value="$6,482,130" />
        <Metric label="Confirmed total"        value="$6,614,880" />
        <Metric label="Net variance"           value="+$132,750" tone="up"   delta="+2.05 %" mono={false} />
        <Metric label="Lines with variance"    value="27 / 156"  tone="neutral" delta="17 % of lines" mono={false} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20, alignItems: "start" }}>
        <Card
          title="Line-by-line comparison"
          actions={
            <div style={{ display: "flex", gap: 6 }}>
              <Tag kind="danger">12 decrease</Tag>
              <Tag kind="ok">15 increase</Tag>
              <Tag kind="info">4 new</Tag>
            </div>
          }
          style={{ padding: 0 }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "var(--bg-muted)" }}>
                {["Category", "Line", "Indicative", "Confirmed", "Variance", "%"].map((h, i) => (
                  <th key={i} style={{
                    textAlign: i >= 2 ? "right" : "left",
                    padding: "10px 14px", fontSize: 11, fontWeight: 600,
                    letterSpacing: ".04em", textTransform: "uppercase", color: "var(--fg-3)",
                    borderBottom: "1px solid var(--border-subtle)",
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <SrpRow cat="Core Funding" line="Per capita — Secondary"      ind="3,420,000" cnf="3,482,100" d="+62,100"  pct="+1.82" />
              <SrpRow cat="Core Funding" line="Base school allocation"      ind="1,240,000" cnf="1,240,000" d="0"        pct="0.00" />
              <SrpRow cat="Equity"       line="Equity (Social Disadvantage)" ind="412,880"   cnf="448,530"   d="+35,650"  pct="+8.63" up />
              <SrpRow cat="Equity"       line="Equity (Catch Up)"           ind="182,000"   cnf="168,420"   d="−13,580"  pct="−7.46" down />
              <SrpRow cat="Targeted"     line="Students with Disability"    ind="326,500"   cnf="352,920"   d="+26,420"  pct="+8.09" up />
              <SrpRow cat="Targeted"     line="Mental Health in Schools"    ind="—"         cnf="42,800"    d="new"      pct="—" newline />
              <SrpRow cat="Credits"      line="Cash grants"                 ind="84,000"    cnf="79,230"    d="−4,770"   pct="−5.68" down />
              <SrpRow cat="Credits"      line="Credit adjustments"          ind="12,400"    cnf="10,780"    d="−1,620"   pct="−13.06" down />
            </tbody>
          </table>
        </Card>

        <Card title="Significant movements" subtitle="Variance ≥ $10,000 or ≥ 5 %">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Move dir="up"   line="Equity (Social Disadvantage)" val="+$35,650" pct="+8.63 %" />
            <Move dir="up"   line="Students with Disability"     val="+$26,420" pct="+8.09 %" />
            <Move dir="up"   line="Per capita — Secondary"       val="+$62,100" pct="+1.82 %" />
            <Move dir="down" line="Equity (Catch Up)"            val="−$13,580" pct="−7.46 %" />
            <Move dir="new"  line="Mental Health in Schools"     val="+$42,800" pct="new line" />
          </div>
        </Card>
      </div>
    </div>
  );
}

function SrpRow({ cat, line, ind, cnf, d, pct, up, down, newline }) {
  const color = up ? "var(--ok-fg)" : down ? "var(--danger-fg)" : newline ? "var(--brand-navy)" : "var(--fg-1)";
  const bg = newline ? "var(--brand-navy-tint)" : "transparent";
  return (
    <tr style={{ borderBottom: "1px solid var(--border-subtle)", background: bg }}>
      <td style={{ padding: "10px 14px", fontSize: 12, color: "var(--fg-3)" }}>{cat}</td>
      <td style={{ padding: "10px 14px", color: "var(--fg-1)" }}>{line}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-2)" }}>{ind}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-1)" }}>{cnf}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color, fontWeight: (up||down||newline) ? 600 : 400 }}>{d}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color }}>{pct}</td>
    </tr>
  );
}

function Move({ dir, line, val, pct }) {
  const fg = dir === "down" ? "var(--danger-fg)" : dir === "new" ? "var(--brand-navy)" : "var(--ok-fg)";
  const bg = dir === "down" ? "var(--danger-bg)" : dir === "new" ? "var(--brand-navy-tint)" : "var(--ok-bg)";
  const sym = dir === "down" ? "↓" : dir === "new" ? "+" : "↑";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "28px 1fr auto", gap: 10, alignItems: "center" }}>
      <div style={{ width: 28, height: 28, borderRadius: 6, background: bg, color: fg, display: "grid", placeItems: "center", fontWeight: 700 }}>{sym}</div>
      <div>
        <div style={{ fontSize: 13, color: "var(--fg-1)" }}>{line}</div>
        <div style={{ fontSize: 11, color: "var(--fg-3)" }}>{pct}</div>
      </div>
      <div style={{ fontSize: 13, fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: fg, fontWeight: 600 }}>{val}</div>
    </div>
  );
}

window.SrpScreen = SrpScreen;
