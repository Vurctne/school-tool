# Round 31 — Build MSIX package for Microsoft Store submission

**Date:** 2026-05-02
**Scope:** Codebase prep + step-by-step Windows submission walkthrough.
The actual `pwsh msix\build_msix_package.ps1 -StoreUpload` run happens
on Ivan's Windows machine — this round gets the code into a state
where that command will succeed first try.

---

## What changed in code

```
MOD   app_metadata.py
       - APP_VERSION: 2.1.1.0 → 2.2.0.0  (feature release covering
         Rounds 22-30 — Compare mode, alt_run_buttons, update check,
         output pill, faculty rail data bars, etc.)

MOD   packaging/SchoolTool.spec
       - Added Round 30 winrt hidden imports so the frozen EXE can
         load Windows.Services.Store at runtime:
           winrt, winrt.windows, winrt.windows.foundation,
           winrt.windows.foundation.collections, winrt.windows.services,
           winrt.windows.services.store, winrt._winrt

MOD   docs/store_publish.md
       - Bumped all 2.0.0.0 references to 2.2.0.0
       - New "What's new since v2.0.0" section listing the highlights
         from Rounds 22-30 — useful as Store listing release notes
```

No changes to the manifest template — the Round 16 wiring is still
correct (Vurctne.VicSchoolFinanceTools, runFullTrust capability,
all six tile asset references).

---

## Quality gates (sandbox-side)

```
ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 72 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 550 passed, 66 skipped (env), 1 warning
```

The PyInstaller build itself can only be exercised on Windows
(needs pywin32 + winrt installed natively); the spec parses cleanly
and the hidden-import additions are syntactically correct.

---

## Run on Windows — exact command sequence

> Open **PowerShell** in the repo root (`D:\Software\Productivity\Vic_School_Finance_Tools`) on the Windows machine.

### 1. Install the Round 30 Windows-only deps

```powershell
# In your active venv:
pip install -e .
```

This pulls in `winrt-runtime`, `winrt-Windows.Services.Store`,
`winrt-Windows.Foundation`, `winrt-Windows.Foundation.Collections`
alongside the existing pywin32 / openpyxl / pdfplumber stack. Skip
this step if you already ran `pip install -e .` after the Round 30
commit.

### 2. Sanity-check the launch

```powershell
python app.py
```

* Window should open titled "School Tool v2.2.0.0".
* Sub-Program Budget Report rail entry should still gate to "Refresh
  licence" (free-tier mode is on, paid tools are temporarily free).
* No popup at launch (you're sideloaded, so the Store update check
  silently returns None — that's correct).
* HYIA Transfer Code Generator should run on a sample.
* Master Budget Compass Autofill should show TWO primary-style
  buttons: **Generate budget workbook** + **Compare two budgets**.
* Refined PAL Search should show ONLY the big "Open Refined PAL
  Search" button (no Clear button).

If anything's wrong, fix before continuing — a failed cert is 24-48 h
of wasted Store review time.

### 3. Build the Store upload artifact

```powershell
pwsh msix\build_msix_package.ps1 -StoreUpload
```

The pipeline runs all 6 stages:

1. **Clean** — wipe `build/`, `dist/`, `msix/staging/`, `msix/output/`; regenerate `assets/brand/app.ico` and `msix/staging/Assets/*.png` via `scripts/generate_store_icons.py`.
2. **PyInstaller** — onedir build via `packaging/SchoolTool.spec` → `dist/School Tool v2.2.0.0/`.
3. **Stage** — copy the frozen app + tile PNGs into `msix/staging/`, write a filled `AppxManifest.xml` (Identity, Version, Description). The Identity guard fails the build if the manifest doesn't match the Partner Center values (`Vurctne.VicSchoolFinanceTools` / `CN=E75204F6-…`).
4. **Pack** — `makeappx.exe pack /d msix/staging /p msix/output/School_Tool_2.2.0.0_x64.msix /o`.
5. **Sign** — skipped (`-StoreUpload` defers signing to Partner Center after upload).
6. **Bundle** — wrap the `.msix` in a `.msixupload` ZIP for Partner Center auto-ingestion.

Final artifacts:

```
msix/output/School_Tool_2.2.0.0_x64.msix          (raw package — local install / WACK test)
msix/output/School_Tool_2.2.0.0_x64.msixupload    (upload to Partner Center)
dist/SHA256SUMS-v2.2.0.0.txt                      (hash for receipt records)
```

### 4. Pre-submission checklist (run on Windows BEFORE upload)

- [ ] **Sideload smoke test** — `Add-AppxPackage -Path msix\output\School_Tool_2.2.0.0_x64.msix` (Developer Mode must be on; the unsigned `.msix` works for this purpose).
- [ ] Open the installed app from the Start menu — title bar reads "School Tool v2.2.0.0".
- [ ] Run HYIA on a known-good input → output XLSX saves correctly, "Show formula" press-and-hold reveals the formula.
- [ ] Run Master Budget Compass Autofill on a sample Compass + template pair → output XLSM produced, macros intact, mismatch highlighting works.
- [ ] Click **Compare two budgets** with two sample Master Budgets → diff table renders, Export comparison Excel saves a readable XLSX.
- [ ] Sub-Program Budget Report — sample PDF → table, faculty filter, slider, Export to Excel, Combined sheet toggle on Yes.
- [ ] No crash on close.
- [ ] **WACK test** — open Windows App Certification Kit, point it at the installed package family name. Wait ~10 min. All test categories should be "Passed".
- [ ] Uninstall the test install: `Get-AppxPackage *VicSchoolFinanceTools* | Remove-AppxPackage`.

### 5. Submit on Partner Center

1. Open <https://partner.microsoft.com/dashboard>, sign in as the Vurctne account owner.
2. **Windows & Xbox > Apps and games > School Tool**.
3. Click **Start a submission** (or **New submission** if a draft exists for v2.2.0.0).
4. **Packages** → upload `msix/output/School_Tool_2.2.0.0_x64.msixupload`. Wait for ingestion validation to complete (~2-5 min). Fix any errors flagged at this stage before continuing.
5. **Store listing** — paste the release notes from the new "What's new since v2.0.0" section in `docs/store_publish.md`. Screenshots / category / privacy URL come from `docs/store_listing_copy.md` (Round 16 deliverable; check it's up to date).
6. **Pricing & availability** — Free tier; markets = Australia primary + English-speaking optional. Confirm previous in-app purchase / licence-gate config still applies (Sub-Program Budget Report is paid; HYIA + Master Budget Compass Autofill + Refined PAL Search are free).
7. **Age rating (IARC)** — General audience.
8. **Submit for certification.** Cert turnaround typically 1-3 business days; rejection reasons appear in the dashboard.

### 6. After certification clears

* The Store auto-rolls v2.2.0.0 to enrolled devices within 24h.
* Round 30's update check fires on those devices' next launch and prompts users still on v2.0.0 / v2.1.x to install — closing the loop on the new feature.

---

## What to verify *before* the run

The Cowork sandbox can't run the actual build (it needs Windows + pywin32 + Win10 SDK). Quick visual checks Ivan should do before invoking the build script:

* `app_metadata.APP_VERSION == "2.2.0.0"` ✅ (set this round)
* `app_metadata.STORE_PACKAGE_IDENTITY_NAME == "Vurctne.VicSchoolFinanceTools"` ✅ (Round 16)
* `app_metadata.STORE_PUBLISHER == "CN=E75204F6-F77B-4E0C-89C6-AC00A663F6A0"` ✅ (Round 16)
* `msix/AppxManifest.template.xml` contains `<rescap:Capability Name="runFullTrust" />` ✅ (needed for pywin32 + winrt)
* `packaging/SchoolTool.spec` lists the winrt hidden imports ✅ (added this round)
* `pyproject.toml` lists the winrt deps ✅ (added Round 30)

---

## Cowork-side files touched this round

```
MOD   app_metadata.py                       (version 2.1.1.0 → 2.2.0.0)
MOD   packaging/SchoolTool.spec             (winrt hidden imports)
MOD   docs/store_publish.md                 (version refs + What's new)
ADD   handoff/round31_msix_store_submission.md
```

No source code or test changes — Round 31 is pure release prep.

---

## If the build fails on Windows

| Error | Fix |
| --- | --- |
| `winrt module not found` at runtime | `pip install -e .` to pull the new Windows-only deps in `pyproject.toml`. |
| `makeappx.exe was not found` | Install Windows 10 SDK or copy `makeappx.exe` + `signtool.exe` to `.tools/msixsdk/` in the repo. |
| `Identity mismatch detected` | The `Identity/Name` or `Identity/Publisher` in the manifest doesn't match Partner Center. Don't override `-IdentityName` / `-Publisher` flags — let the script use the defaults baked in. |
| Partner Center upload rejects with `Package version conflict` | The Store stores the highest version ever submitted. If 2.2.0.0 was already submitted (even rejected), bump to 2.2.0.1 (run with `-Version 2.2.0.1`) and rebuild. |
| WACK fails on `runFullTrust capability` | The `<rescap:Capability>` line in the manifest must remain — without it, pywin32 + WinRT calls will be blocked. |
| WACK fails on missing assets | Run `python scripts/generate_store_icons.py` then re-run the build. The clean stage wipes the assets dir, so they're regenerated each build. |

---

## TL;DR for Ivan

1. `pip install -e .` on Windows (once).
2. `pwsh msix\build_msix_package.ps1 -StoreUpload`.
3. Sideload + smoke-test from `msix/output/School_Tool_2.2.0.0_x64.msix`.
4. Upload `msix/output/School_Tool_2.2.0.0_x64.msixupload` to Partner Center.
5. Paste the "What's new since v2.0.0" block from `docs/store_publish.md` into the release notes field.
6. Submit.
