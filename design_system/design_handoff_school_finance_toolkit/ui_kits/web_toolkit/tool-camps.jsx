// Camps / Activities Reconciliation.

function CampsScreen() {
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1280 }}>
      <header>
        <div style={{ fontSize: 24, fontWeight: 600 }}>Camps / Activities Reconciliation</div>
        <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 4 }}>
          Reconcile camp costings across the Camps register, supplier invoices, and the Sub-Program ledger.
        </div>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        <FileField label="Camps register"    hint="Camps spreadsheet maintained by the business manager."
                   value="C:\Finance\Camps\Camps_Register_2026.xlsx" />
        <FileField label="Supplier invoices" hint="Folder or single workbook of supplier invoice exports."
                   value="C:\Finance\Camps\Invoices_S1_2026.xlsx" />
        <FileField label="Sub-Program ledger" hint="Expense Sub-Program export filtered to camp codes."
                   value="C:\Finance\Camps\SubProgram_30120_30140.xlsx" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Metric label="Activities"         value="12"     mono={false} />
        <Metric label="Students billed"    value="486"    mono={false} />
        <Metric label="Reconciled"         value="$184,210" tone="up"   delta="93 % of expenditure" mono={false} />
        <Metric label="Unreconciled"       value="$13,780"  tone="down" delta="7 variance items"    mono={false} />
      </div>

      <Card title="Activities" subtitle="Totals per camp with reconciliation status" style={{ padding: 0 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr .6fr repeat(4, .8fr) .8fr", fontSize: 13 }}>
          {["Activity", "Date", "Students", "Invoiced", "Receipted", "Variance", "Status"].map((h, i) => (
            <div key={i} style={{
              padding: "10px 14px", fontSize: 11, fontWeight: 600, letterSpacing: ".04em",
              textTransform: "uppercase", color: "var(--fg-3)", background: "var(--bg-muted)",
              borderBottom: "1px solid var(--border-subtle)",
              textAlign: i >= 2 && i <= 5 ? "right" : "left",
            }}>{h}</div>
          ))}
          <CampRow name="Yr 9 City Experience"  date="18/03/2026" students={148} inv="42,380" rec="42,380" var_="0"     status="match" />
          <CampRow name="Yr 7 Camp Oasis"       date="24/02/2026" students={182} inv="38,220" rec="38,040" var_="+180"  status="minor" />
          <CampRow name="Instrumental tour"     date="09/05/2026" students={26}  inv="8,140"  rec="8,140"  var_="0"     status="match" />
          <CampRow name="Yr 10 Ski camp"        date="01/08/2026" students={64}  inv="51,840" rec="45,200" var_="+6,640" status="open" />
          <CampRow name="Debating state finals" date="14/06/2026" students={8}   inv="620"    rec="620"    var_="0"     status="match" />
          <CampRow name="Yr 11 Outdoor Ed"      date="20/04/2026" students={42}  inv="26,880" rec="21,540" var_="+5,340" status="open" />
          <CampRow name="Art gallery excursion" date="30/04/2026" students={16}  inv="640"    rec="640"    var_="0"     status="match" />
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20, alignItems: "start" }}>
        <Card
          title="Yr 10 Ski camp — outstanding items"
          subtitle="Open reconciliation for review"
          actions={<Button kind="secondary" small>Assign to...</Button>}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto auto", rowGap: 10, columnGap: 16, fontSize: 13, alignItems: "center" }}>
            <div style={{ color: "var(--fg-3)", fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".04em" }}>Item</div>
            <div style={{ color: "var(--fg-3)", fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".04em", textAlign: "right" }}>Expected</div>
            <div style={{ color: "var(--fg-3)", fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".04em", textAlign: "right" }}>Receipted</div>
            <div style={{ color: "var(--fg-3)", fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".04em" }}>Status</div>

            <OpenItem item="Bus hire — Coach Lines Vic" exp="8,400"  rec="8,400"  status="match" />
            <OpenItem item="Ski hire (4 not returned)"  exp="960"    rec="0"      status="chase" />
            <OpenItem item="Accommodation deposit"      exp="18,400" rec="15,200" status="variance" note="Invoice vs supplier statement off by $3,200" />
            <OpenItem item="Meals — on-mountain"        exp="11,680" rec="9,200"  status="variance" note="4 students withdrew late — refund pending" />
            <OpenItem item="Instructor fees"            exp="12,400" rec="12,400" status="match" />
          </div>
        </Card>

        <Card title="Export" subtitle="After reconciling">
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Button kind="primary" icon={<Icon d={<><path d="M12 4v12M7 11l5 5 5-5M4 20h16"/></>} />}>Generate reconciliation workbook</Button>
            <Button kind="secondary" small>Export variance list (CSV)</Button>
            <Button kind="ghost" small>Email report to principal</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

function CampRow({ name, date, students, inv, rec, var_, status }) {
  const statusTag = {
    match:    <Tag kind="ok">Match</Tag>,
    minor:    <Tag kind="warn">Minor</Tag>,
    open:     <Tag kind="danger">Open</Tag>,
  }[status];
  const varColor = var_ === "0" ? "var(--fg-3)" : (var_.startsWith("+") ? "var(--ok-fg)" : "var(--danger-fg)");
  return (
    <>
      <div style={{ padding: "10px 14px", color: "var(--fg-1)", borderBottom: "1px solid var(--border-subtle)" }}>{name}</div>
      <div style={{ padding: "10px 14px", color: "var(--fg-2)", borderBottom: "1px solid var(--border-subtle)", fontFamily: "var(--font-mono)" }}>{date}</div>
      <div style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", borderBottom: "1px solid var(--border-subtle)" }}>{students}</div>
      <div style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-1)", borderBottom: "1px solid var(--border-subtle)" }}>{inv}</div>
      <div style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-1)", borderBottom: "1px solid var(--border-subtle)" }}>{rec}</div>
      <div style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: varColor, fontWeight: var_ === "0" ? 400 : 600, borderBottom: "1px solid var(--border-subtle)" }}>{var_}</div>
      <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border-subtle)" }}>{statusTag}</div>
    </>
  );
}

function OpenItem({ item, exp, rec, status, note }) {
  return (
    <>
      <div>
        <div style={{ color: "var(--fg-1)" }}>{item}</div>
        {note && <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 2 }}>{note}</div>}
      </div>
      <div style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>{exp}</div>
      <div style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>{rec}</div>
      <div>
        {status === "match"    && <Tag kind="ok">Match</Tag>}
        {status === "chase"    && <Tag kind="warn">Chase</Tag>}
        {status === "variance" && <Tag kind="danger">Variance</Tag>}
      </div>
    </>
  );
}

window.CampsScreen = CampsScreen;
