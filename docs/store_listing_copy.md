# Microsoft Store listing copy — School Tool v2.0.0

Source-of-truth for all the text fields you'll paste into Partner Center → Store listing. Edit
anything you want; this is a draft. The character/word limits in each heading are Microsoft's
hard limits.

---

## App name (≤50 chars)

**School Tool**

(13 chars. Plain, searchable, doesn't conflict with the existing "Master Budget Automation Tool"
v1 listing — they can coexist on the Store.)

---

## Short description (≤200 chars)

> Free productivity tools for Victorian Government school business managers. Reformat CASES21 reports, fill the Master Budget workbook, and compare SRP budgets — all offline.

(192 chars.)

---

## Long description (≤10,000 chars)

```
School Tool is a free productivity suite for Victorian Government school business managers.
It bundles the workbook helpers and report formatters that finance officers across the state
already build by hand into a single, offline desktop app — saving hours every reporting cycle.

WHAT'S INSIDE

  HYIA Transfer Code Generator (Banking)
  Compute Westpac HYIA transfer security codes from your Sub-Investment Number, transfer
  amount, and date. Optional encrypted SIN remembering uses Windows DPAPI so the value
  never leaves your device. Pure offline. Replaces the manual lookup most schools do
  monthly.

  Master Budget Compass Autofill (Budget)
  Reads your Expense Sub-Program XLSX export and auto-fills the matching cells in your
  school's Master Budget workbook. Preserves macros, highlights mismatches between the
  source and template, and writes a fully-formatted output you can hand to council. Cuts
  a 90-minute manual task down to under a minute.

  SRP Comparison (Budget)
  Compares your Indicative SRP and Confirmed SRP budget PDFs line by line. Categorises
  every line as unchanged, increased, decreased, new in confirmed, or removed — with
  per-category counts and dollar variances. Council-ready output for the next finance
  sub-committee meeting.

  Sub-Program Budget Report (Budget)
  Reformats the CASES21 Annual Sub-Program Budget Report (GL21157) into a clean two-sheet
  workbook split by Revenue and Expenditure. Joins prior-period commentary, flags lines
  over a user-tunable budget threshold, groups by faculty, and includes period-extracted
  date stamps. Tweak the threshold with a live slider before exporting; the result is
  ready for the next School Council pack.

WHO IT'S FOR

  Designed specifically for the way Victorian Government schools work — CASES21 exports,
  the SRP cycle, the Master Budget template, faculty groupings — built by a school
  business manager, for school business managers.

PRIVACY

  School Tool processes every file locally on your device. No file content, no school
  data, no personal information is sent to any server. The app does not require
  registration, sign-in, or any internet connection to use any of its tools.

  See the full privacy policy at: https://vurctne.github.io/school-tool/privacy

OFFLINE BY DEFAULT

  All features work without an internet connection. No cloud sync, no telemetry, no
  account required.

ROADMAP

  More tools are in development — Operating Statement comparison, Camps Reconciliation,
  EOY Prepayments and Revenue in Advance, Family Invoice Import Prep, and more. Visible
  in the app's left rail under "In development". Updates ship through the Microsoft Store
  as they're ready.

SUPPORT

  Email Vurctne@gmail.com — feedback, bug reports, and feature requests welcome.

REQUIREMENTS

  Windows 10 version 1809 (October 2018 Update) or later, including Windows 11.
  Approximately 200 MB of disk space.

  Built and tested for Victorian Government DoE-managed Windows 11 laptops.
```

---

## What's new in this version (≤1,500 chars)

```
First public release.

Includes four free tools:
  • HYIA Transfer Code Generator
  • Master Budget Compass Autofill
  • SRP Comparison
  • Sub-Program Budget Report

Highlights:
  • Two-phase preview/export workflow — adjust the over-budget threshold with a live slider, then export to Excel when ready
  • Faculty rail filters in the Sub-Program Budget Report
  • Period auto-detected from the CASES21 PDF footer
  • Council-ready output formatting with currency formatting, data bars, and frozen header rows
  • 100% offline — no account, no sign-in, no data leaves your device
```

(580 chars.)

---

## Screenshot captions (5–7 captions total — one per uploaded screenshot)

Take screenshots at 1366×768 minimum. Recommended set:

1. **`01_main_window.png`** — full window showing the left rail with all four free tools and
   the In development list
   > Caption: "All four free tools in the left rail, with the development roadmap visible
   > below — see what's coming next."

2. **`02_sub_program_input.png`** — Sub-Program Budget Report input pane with file pickers
   and the threshold slider
   > Caption: "Pick your CASES21 GL21157 PDF, set the over-budget threshold with the live
   > slider, and click Generate report."

3. **`03_sub_program_result.png`** — result panel showing the faculty rail + table with
   pink over-budget rows
   > Caption: "Click any faculty in the rail to filter the table. Rows above your
   > threshold are flagged for the next School Council pack."

4. **`04_master_budget_result.png`** — Master Budget Compass result with mismatch
   highlighting
   > Caption: "The Master Budget Compass Autofill matches sub-program codes between your
   > source export and the workbook, highlighting any mismatches in pink."

5. **`05_srp_comparison.png`** — SRP Comparison output with categorised lines
   > Caption: "SRP Comparison classifies every Indicative-vs-Confirmed line — unchanged,
   > increased, decreased, new, or removed — and writes a council-ready workbook."

6. **`06_hyia_calculator.png`** — HYIA Transfer Code Generator with a sample SIN +
   amount + date
   > Caption: "HYIA Transfer Code Generator computes Westpac transfer security codes
   > from your SIN, amount, and date — fully offline, with optional encrypted SIN
   > remembering."

7. **`07_export_to_excel.png`** — Sub-Program export confirmation showing the output XLSX
   path
   > Caption: "Export to Excel writes the formatted workbook next to your source PDF."

---

## Categories

- **Primary category:** Productivity
- **Secondary category:** Business

(Microsoft Store category list: Books & reference, Business, Developer tools, Education,
Entertainment, Food & dining, Government & politics, Health & fitness, Kids & family, Lifestyle,
Medical, Multimedia design, Music, Navigation & maps, News & weather, Personal finance,
Photo & video, Productivity, Security, Shopping, Social, Sports, Travel, Utilities & tools,
Weather. Productivity is the cleanest fit; Business as secondary.)

---

## Search keywords (up to 7)

Order them by importance — the first three carry the most weight.

1. school finance
2. CASES21
3. school business manager
4. Victorian schools
5. SRP budget
6. sub-program report
7. school council reporting

---

## Age rating

Use the IARC questionnaire on Partner Center. The honest answers for School Tool:

- **Violence:** None
- **Sexual content:** None
- **Profanity:** None
- **Gambling:** None
- **Drugs / alcohol / tobacco:** None
- **User interaction (chat / messaging):** None
- **In-app purchases:** None
- **Generates user-generated content:** None
- **Shares user location:** No
- **Connects to social networks:** No

Result: **3+ / Everyone** rating across all jurisdictions (IARC Generic, ESRB E, PEGI 3,
USK 0, etc.). Free tier with no in-app purchases makes this trivial.

---

## URLs to provide

| Field | Value | Status |
|---|---|---|
| **Privacy policy URL** | `https://vurctne.github.io/school-tool/privacy` | Need to host the privacy policy file (next section) on GitHub Pages OR `schooltool.com.au` once registered. Until then, can use the GitHub repo's raw markdown URL as a placeholder, or just any temporary public URL. |
| **Support contact info** | `Vurctne@gmail.com` | Already canonical in `app_metadata.SUPPORT_EMAIL` |
| **Website (optional)** | (blank, or `https://schooltool.com.au` once live) | Optional |

Microsoft requires a working privacy policy URL even if the app collects nothing — it's a hard
gate. The HTML/markdown that page hosts is below in `docs/store_privacy_policy.md`.

---

## Markets / availability

- **Primary market:** Australia
- **Secondary markets:** All worldwide (no exclusions). The app's value is Victorian-specific
  but the listing being globally visible doesn't hurt anyone — outside-VIC users will
  self-select away.

---

## Pricing

- **Free** (Round 15 launch)
- **No in-app purchases** (paid tier resumes when you flip `requires_feature` back on the
  paid tools and re-add the User tab — that's a separate Store update later)

---

## System requirements (auto-derived from MSIX, plus optional rich description)

- **Minimum OS:** Windows 10 version 1809 (build 17763) — set in `AppxManifest.xml`
- **Architecture:** x64 only
- **Disk space:** ~200 MB
- **Memory:** ~150 MB during typical use
- **Network:** Not required for any feature

---

## Submission checklist (before clicking "Submit for certification")

- [ ] `Vurctne.VicSchoolFinanceTools` and `CN=E75204F6-F77B-4E0C-89C6-AC00A663F6A0` appear
      exactly in the manifest (Round 16 wired this)
- [ ] All 7 store icons present in `assets/store/` (Round 16 generated these)
- [ ] `pwsh msix\build_msix_package.ps1 -StoreUpload` produces `School_Tool_2.0.0.0_x64.msixupload`
- [ ] Local install of the `.msixupload` works on a clean Windows 11 machine
- [ ] All four free tools open and run a sample PDF/XLSX through end-to-end
- [ ] Privacy policy is hosted at the URL you'll provide
- [ ] All 7 screenshots captured at 1366×768+ and uploaded
- [ ] Short description ≤200 chars, long description ≤10,000 chars
- [ ] Age rating questionnaire completed → 3+ / Everyone
- [ ] Categories selected (Productivity primary, Business secondary)
- [ ] Search keywords entered
- [ ] Pricing set to Free
- [ ] Markets set to Australia (and worldwide if desired)

After submission, certification typically takes 24–72 hours.
