# Tools in Development — Vic School Tool

Publisher: **Vurctne** · Legal seller on invoices: **ZXW Investment Pty Ltd** (ABN <ABN TBD>, GST status TBD) · Support: Vurctne@gmail.com · Annual licence: **$550 + GST** per school.

Status legend: 🟢 shipped · 🟠 in development · 🔵 planned · ⚪ exploratory.

---

## v2.0.0 — launch release *(building now)*

| Status | Tool | Tier | Group | Milestone | Notes |
|---|---|---|---|---|---|
| 🟠 | **HYIA Transfer Code Generator** | Free | Banking | M1 | Westpac security-code calculator (SIN + Amount + Date). Optional DPAPI-encrypted SIN remembering. Pure offline. |
| 🟠 | **Master Budget Compass Autofill** | Free | Budget | M3-a | Port of the existing v1.0.2 *Master Budget Automation Tool*. Same openpyxl logic, macro-preserving write. Re-skinned to v2 design system, renamed. |
| 🟠 | **Sub-Program Budget Report** | Paid | Budget | M3-b | Reformats the Annual Sub-Program Budget Report (CASES21 GL21157 PDF), optionally joins prior-period comments, flags over-budget lines, faculty grouping, Council-ready output. First paid SKU — requires registration + valid licence. |

**Supporting features in v2.0.0 (not tools, but user-facing):**
- 🟠 **User tab** — registration, sign-in, change password, password reset, licence status, invoice history, support mailto (M2).
- 🟠 **Licence flow** — generate invoice → upload signed PO → OCR auto-match (M5) or admin approve → desktop unlocks paid tool.
- 🟠 **Renewal prompts** — 60 days / 30 days / daily in final 7 days (M5).

---

## v2.1.0 — planned next

| Status | Tool | Tier | Group | Milestone | Notes |
|---|---|---|---|---|---|
| 🔵 | **SRP Comparison** | Free | Budget | M7 | Compare Indicative vs Confirmed SRP PDFs line by line. Variance categorisation (unchanged / increased / decreased / new / removed). Sample files: `Samples/SRP budget Report/`. |
| 🔵 | **Operating Statement** | Paid | Reconciliation | M7 | Period-over-period GL Operating Statement compare with user-configurable $/% variance threshold. CASES21 GL21150 PDF input. Sample files: `Samples/Operating Statement/`. |

---

## v2.2.0 — planned after

| Status | Tool | Tier | Group | Milestone | Notes |
|---|---|---|---|---|---|
| 🔵 | **Camps / Activities Reconciliation** | Paid | Reconciliation | M8 | Three-way reconciliation: Camps register × supplier invoices × Sub-Program ledger. Per-activity variance rows with Match / Minor / Open status. **Blocker**: no sample files yet in `Samples/`. |

---

## Exploratory / future ideas

*(Parked — not committed. If we want any of these, we spec and slot into a future milestone.)*

| Status | Tool | Notes |
|---|---|---|
| ⚪ | 
| ⚪ | Family invoice Cases21 import prep
| ⚪ | Subprogram Budget Variance and Transaction compile
| ⚪ | PDF to excel Data Cleaner
| ⚪ | EOY Rev in Advancde and Prepaid Expenses summary
| ⚪ | Web version of the whole toolkit | Deferred 12–18 months. Registry pattern in `EXTENDING.md` ports 1:1 to React. |

---

## Legacy / deprecated

| Status | Product | Notes |
|---|---|---|
| 🟢 | **Master Budget Automation Tool v1.0.2** (standalone MSIX) | Continues to ship free on its current Microsoft Store listing. No updates planned. Superseded by Master Budget Compass Autofill inside the v2 shell. Deprecation date TBD (after v2.0.0 adoption signals are in). |

---

## Quick reference — tool registry

Kebab-case IDs as used in `toolkit/registry.py`:

```python
TOOLS = [
    HyiaTool,                       # id = "hyia"                group = "Banking"
    MasterBudgetTool,               # id = "master-budget"       group = "Budget"
    SubProgramBudgetReportTool,     # id = "sub-program"         group = "Budget"
    # --- v2.1 ---
    # SrpComparisonTool,            # id = "srp"                 group = "Budget"
    # OperatingStatementTool,       # id = "operating"           group = "Reconciliation"
    # --- v2.2 ---
    # CampsReconciliationTool,      # id = "camps"               group = "Reconciliation"
]
```

Adding a new tool is: write `tools/<id>/frame.py` + `tools/<id>/logic.py`, append one line to the list above, and that's it. See `docs/02_ARCHITECTURE.md` ADR-0004 + the handoff's `EXTENDING.md` for the contract.

---

*Last updated: 2026-04-25 (added EOY Prepayments and Revenue in Advance to Exploratory; merged from root `Tools_in_Development.md` stub which was the user's running idea list).*
