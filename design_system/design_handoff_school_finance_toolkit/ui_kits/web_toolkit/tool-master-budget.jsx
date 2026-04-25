// Master Budget tool screen — step flow: Select files → Import running → Review mismatches.

function MasterBudgetScreen({ variant = "review" }) {
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 1280 }}>
      <header style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24 }}>
        <div>
          <div style={{ fontSize: 24, fontWeight: 600, color: "var(--fg-1)" }}>Master Budget</div>
          <div style={{ fontSize: 13, color: "var(--fg-3)", marginTop: 4 }}>
            Import an Expense Sub-Program export from Compass into a Master Budget workbook.
          </div>
        </div>
        <Stepper step={variant === "review" ? 3 : 2} steps={["Select files", "Import", "Review"]} />
      </header>

      {variant === "review" && <ReviewBody />}
    </div>
  );
}

function ReviewBody() {
  return (
    <>
      <Banner
        level="warning"
        title="Import completed with 3 mismatch item(s). Highlighted rows and columns need review."
        body="Output workbook saved. Mismatches are also listed in the run report."
        actions={<><Button kind="secondary" small>Open output folder</Button><Button kind="primary" small>Download report</Button></>}
      />

      {/* Metric cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Metric label="Matched rows"  value="247" />
        <Metric label="Matched cells" value="1,481" />
        <Metric label="Mismatch items" value="2" tone="down" delta="Account codes missing from source" mono={false} />
        <Metric label="Source-only items" value="1" tone="up" delta="Inserted in numeric position" mono={false} />
      </div>

      {/* Source summary */}
      <Card
        title="Files used"
        actions={<Button kind="ghost" small>Re-run import</Button>}
      >
        <div style={{ display: "grid", gridTemplateColumns: "200px 1fr auto", rowGap: 8, columnGap: 16, fontSize: 13 }}>
          <div style={{ color: "var(--fg-3)" }}>Expense Sub-Program file</div>
          <div style={{ fontFamily: "var(--font-mono)" }}>C:\Users\ivan\Downloads\ExpenseSubProgram_2026.xlsx</div>
          <Tag kind="ok">Validated</Tag>

          <div style={{ color: "var(--fg-3)" }}>Master Budget template</div>
          <div style={{ fontFamily: "var(--font-mono)" }}>C:\SchoolFinance\Templates\Master_Budget_2026.xlsm</div>
          <Tag kind="ok">Macros preserved</Tag>

          <div style={{ color: "var(--fg-3)" }}>Output workbook</div>
          <div style={{ fontFamily: "var(--font-mono)" }}>C:\SchoolFinance\Templates\Master_Budget_2026_AUTO_20260422_1430.xlsm</div>
          <Tag kind="info">Saved 22/04/2026 14:30</Tag>
        </div>
      </Card>

      {/* Mismatch preview table */}
      <Card
        title="Highlighted items"
        subtitle="Rows and columns flagged during the import. The same list is written to the run report."
        actions={
          <div style={{ display: "flex", gap: 6 }}>
            <Tag kind="danger">2 mismatch</Tag>
            <Tag kind="ok">1 source only</Tag>
          </div>
        }
        style={{ padding: 0 }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "var(--bg-muted)" }}>
              {["", "Sub-program", "Account code", "Description", "Source", "Master", "Status"].map((h,i) => (
                <th key={i} style={{
                  textAlign: i >= 4 && i !== 6 ? "right" : "left",
                  padding: "10px 14px", fontSize: 11, fontWeight: 600,
                  letterSpacing: ".04em", textTransform: "uppercase", color: "var(--fg-3)",
                  borderBottom: "1px solid var(--border-subtle)",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <MMRow hl="mismatch" sub="10110 Core"     code="71022" desc="Casual relief"      src="—"      mst="98,420" status={<Tag kind="danger">Missing from source</Tag>} />
            <MMRow hl="mismatch" sub="20301 ES"       code="82015" desc="Consumables"        src="—"      mst="42,110" status={<Tag kind="danger">Missing from source</Tag>} />
            <MMRow hl="source"   sub="10110 Core"     code="71089" desc="PD"                 src="14,200" mst="inserted" status={<Tag kind="ok">Source only — inserted</Tag>} />
            <MMRow               sub="30120 Camps"    code="82101" desc="Utilities"          src="86,400" mst="86,400"   status={<Tag kind="ok">Match</Tag>} />
            <MMRow               sub="40500 Programs" code="82210" desc="Excursion costs"    src="12,040" mst="12,040"   status={<Tag kind="ok">Match</Tag>} />
          </tbody>
        </table>
      </Card>
    </>
  );
}

function MMRow({ hl, sub, code, desc, src, mst, status }) {
  const hlBg = hl === "mismatch" ? "var(--hl-mismatch)" : hl === "source" ? "var(--hl-source-only)" : "transparent";
  return (
    <tr style={{ background: hlBg, borderBottom: "1px solid var(--border-subtle)" }}>
      <td style={{ width: 6, padding: 0, background: hl === "mismatch" ? "var(--danger-fg)" : hl === "source" ? "var(--ok-fg)" : "transparent" }} />
      <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-1)" }}>{sub}</td>
      <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-1)" }}>{code}</td>
      <td style={{ padding: "10px 14px", color: "var(--fg-1)" }}>{desc}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-1)" }}>{src}</td>
      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--fg-1)" }}>{mst}</td>
      <td style={{ padding: "10px 14px" }}>{status}</td>
    </tr>
  );
}

window.MasterBudgetScreen = MasterBudgetScreen;
