// Annual Sub-Program Budget Report & Comments — priority tool.
// Reformats and visualises a CASES21 Annual Sub-Program report; adds manager comments.

function SubProgramScreen() {
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1280 }}>
      <header style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24 }}>
        <div>
          <div style={{ fontSize: 24, fontWeight: 600, display: "flex", alignItems: "center", gap: 10 }}>
            Annual Sub-Program Budget Report <Tag kind="info">Priority</Tag>
          </div>
          <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 4 }}>
            Reformat Jun25 Sub-Program export, add sub-program-level commentary, publish to council.
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button kind="secondary" small>Save draft</Button>
          <Button kind="primary" small>Export to workbook</Button>
        </div>
      </header>

      <Banner
        level="info"
        title="Source: Annual Subprogram Budget Report Jun25.xlsx"
        body="84 sub-programs · 12 faculties · YTD spend 58 % of annual budget"
      />

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 20, alignItems: "start" }}>
        {/* Faculty picker */}
        <Card title="Faculties" style={{ padding: 0 }}>
          <div>
            <FacultyRow active name="English"         sub="10110 · 10120 · 10130" used={0.72} />
            <FacultyRow name="Mathematics"            sub="10210 · 10220"         used={0.58} />
            <FacultyRow name="Science"                sub="10310 · 10320 · 10330" used={0.64} />
            <FacultyRow name="Humanities"             sub="10410 · 10420"         used={0.49} />
            <FacultyRow name="LOTE"                   sub="10510"                 used={0.41} />
            <FacultyRow name="The Arts"               sub="10610 · 10620"         used={0.55} />
            <FacultyRow name="HPE"                    sub="10710 · 10720"         used={0.83} over />
            <FacultyRow name="Technology"             sub="10810 · 10820"         used={0.37} />
            <FacultyRow name="Wellbeing"              sub="20110 · 20120"         used={0.66} />
            <FacultyRow name="Library"                sub="20210"                 used={0.51} />
            <FacultyRow name="Administration"         sub="20310 · 20320 · 20330" used={0.60} />
            <FacultyRow name="Facilities"             sub="30110 · 30120 · 30130" used={0.71} />
          </div>
        </Card>

        {/* Detail + commentary */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <Card title="English — 10110, 10120, 10130" subtitle="YTD spend vs annual budget" style={{ padding: 0 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "var(--bg-muted)" }}>
                  {["Sub-program", "Account", "Description", "Budget", "YTD", "Remaining", "Used"].map((h, i) => (
                    <th key={i} style={{
                      textAlign: i >= 3 && i <= 5 ? "right" : "left",
                      padding: "10px 14px", fontSize: 11, fontWeight: 600,
                      letterSpacing: ".04em", textTransform: "uppercase", color: "var(--fg-3)",
                      borderBottom: "1px solid var(--border-subtle)",
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <SpRow sp="10110" acc="82015" desc="Consumables — paper & print"     bud="8,400"  ytd="6,380"  rem="2,020"  used={0.76} />
                <SpRow sp="10110" acc="82020" desc="Textbooks & reading resources"   bud="14,200" ytd="9,580"  rem="4,620"  used={0.67} />
                <SpRow sp="10110" acc="82210" desc="Excursion costs"                 bud="4,800"  ytd="3,960"  rem="840"    used={0.83} />
                <SpRow sp="10120" acc="82015" desc="Consumables"                     bud="3,200"  ytd="2,040"  rem="1,160"  used={0.64} />
                <SpRow sp="10120" acc="82320" desc="PD — Literacy coaching"          bud="6,400"  ytd="6,820"  rem="−420"   used={1.07} over />
                <SpRow sp="10130" acc="82020" desc="Senior texts — VCE"              bud="12,600" ytd="4,120"  rem="8,480"  used={0.33} />
              </tbody>
              <tfoot>
                <tr style={{ borderTop: "2px solid var(--border-strong)", background: "var(--bg-muted)" }}>
                  <td colSpan="3" style={{ padding: "10px 14px", fontWeight: 700 }}>Faculty total</td>
                  <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontWeight: 700 }}>49,600</td>
                  <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontWeight: 700 }}>32,900</td>
                  <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontWeight: 700 }}>16,700</td>
                  <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontWeight: 700, color: "var(--warn-fg)" }}>66 %</td>
                </tr>
              </tfoot>
            </table>
          </Card>

          <Card
            title="Faculty commentary"
            subtitle="Published alongside the report. Markdown supported."
            actions={<><Tag kind="ok">Saved 14:02</Tag><Button kind="ghost" small>History</Button></>}
          >
            <div style={{
              padding: 14, border: "1px solid var(--border-subtle)", borderRadius: 6,
              background: "var(--bg-inset)", fontSize: 13, lineHeight: 1.55, color: "var(--fg-1)",
              fontFamily: "inherit",
            }}>
              <p style={{ margin: 0 }}>
                English faculty is tracking at <strong>66 %</strong> of annual budget YTD, broadly in line with a 66 % pro-rata benchmark. Two items need attention:
              </p>
              <ul style={{ margin: "10px 0 0 18px", padding: 0 }}>
                <li><strong>10120 · 82320 PD — Literacy coaching</strong> is $420 over budget after a scheduled Literacy Coaching Pilot extension. Requesting a virement from 10130 · 82020 (under-utilised).</li>
                <li><strong>10110 · 82210 Excursion costs</strong> at 83 % — remaining $840 earmarked for the Yr 9 Writers' Festival in October.</li>
              </ul>
              <p style={{ margin: "10px 0 0" }}>No issues flagged for the Council Finance Sub-Committee.</p>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <Button kind="ghost" small>Bold</Button>
              <Button kind="ghost" small>Italic</Button>
              <Button kind="ghost" small>Bullet list</Button>
              <div style={{ flex: 1 }} />
              <Button kind="secondary" small>Assign review</Button>
              <Button kind="primary" small>Save</Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function FacultyRow({ name, sub, used, active, over }) {
  const pct = Math.round(used * 100);
  const barColor = over ? "var(--danger-fg)" : used > 0.8 ? "var(--warn-fg)" : "var(--brand-navy)";
  return (
    <div style={{
      padding: "10px 16px",
      display: "grid", gridTemplateColumns: "1fr auto",
      alignItems: "center", gap: 10,
      borderBottom: "1px solid var(--border-subtle)",
      background: active ? "var(--brand-navy-tint)" : "transparent",
      borderLeft: active ? "2px solid var(--brand-navy)" : "2px solid transparent",
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: active ? 600 : 500, color: active ? "var(--brand-navy)" : "var(--fg-1)" }}>{name}</div>
        <div style={{ fontSize: 11, color: "var(--fg-3)", fontFamily: "var(--font-mono)", marginTop: 2 }}>{sub}</div>
        <div style={{ height: 4, background: "var(--bg-inset)", borderRadius: 2, marginTop: 8, overflow: "hidden" }}>
          <div style={{ width: `${Math.min(100, pct)}%`, height: "100%", background: barColor }} />
        </div>
      </div>
      <div style={{
        fontSize: 13, fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums",
        color: barColor, fontWeight: 600, minWidth: 40, textAlign: "right",
      }}>{pct}%</div>
    </div>
  );
}

function SpRow({ sp, acc, desc, bud, ytd, rem, used, over }) {
  const pct = Math.round(used * 100);
  const color = over ? "var(--danger-fg)" : used > 0.8 ? "var(--warn-fg)" : "var(--fg-1)";
  return (
    <tr style={{ borderBottom: "1px solid var(--border-subtle)", background: over ? "var(--hl-mismatch)" : "transparent" }}>
      <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-2)" }}>{sp}</td>
      <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-2)" }}>{acc}</td>
      <td style={{ padding: "10px 14px", color: "var(--fg-1)" }}>{desc}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>{bud}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>{ytd}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: over ? "var(--danger-fg)" : "var(--fg-1)" }}>{rem}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color, fontWeight: 600 }}>{pct}%</td>
    </tr>
  );
}

window.SubProgramScreen = SubProgramScreen;
