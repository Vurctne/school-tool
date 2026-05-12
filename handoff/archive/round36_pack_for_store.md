# Round 36 — Final pre-build verification + Store hotfix submission

**Date:** 2026-05-07
**Scope:** Confirm the codebase is ready to build the v2.2.2.0 hotfix
MSIX, then run it on Windows and submit to Partner Center.

---

## Pre-build verification (sandbox-side, all green)

```
app_metadata sanity:
  APP_NAME = 'School Tool'
  APP_VERSION = '2.2.1.0'              ← auto-bumps to 2.2.2.0 on next build
  APP_TITLE = 'School Tool v2.2.1.0'
  SUPPORT_EMAIL = 'feedback@schooltool.com.au'
  STORE_PACKAGE_IDENTITY_NAME = 'Vurctne.VicSchoolFinanceTools'
  STORE_PUBLISHER = 'CN=E75204F6-F77B-4E0C-89C6-AC00A663F6A0'
  SHOW_USER_TAB = False

ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict            → no issues found in 72 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 550 passed, 66 skipped (env), 1 warning
AST + null-byte + suspicious-tail sweep:  0 issues
TkShell methods (19 required):  all present
Registered tools (5):  hyia, master-budget, srp, sub-program, refined-pal-search
```

---

## What's bundled into v2.2.2.0

* **R32** — `_render_result` rebuilt; Sub-Program Budget Report renders again.
* **R34** — Support email switched to `feedback@schooltool.com.au` everywhere it appears in the app + privacy policy + Store listing copy. Privacy-policy "future paid tier" passage removed.
* **R35** — Paid-tier wording removed from user-visible UI; new "What's new" entry in the rail opens an in-app changelog (CHANGELOG.md ships with the MSIX).

---

## Run on Windows

> Open PowerShell in the repo root.

```powershell
cd D:\Software\Productivity\Vic_School_Finance_Tools

# Make sure the local install still has the Round 30 winrt deps
pip install -e .

# Smoke-test before building (catches issues fast)
python app.py
#   → window opens with title "School Tool v2.2.1.0"
#   → left rail shows: Instructions / What's new / Privacy Policy
#   → close the window
#   → no traceback

# Build the Store upload artifact
pwsh msix\build_msix_package.ps1 -StoreUpload
```

The build pipeline (auto-bump → PyInstaller → stage → makeappx pack →
.msixupload bundle) produces:

```
msix\output\School_Tool_2.2.2.0_x64.msix          ← sideload smoke test
msix\output\School_Tool_2.2.2.0_x64.msixupload    ← Partner Center upload
dist\SHA256SUMS-v2.2.2.0.txt                      ← hash receipt
```

---

## Smoke test the .msix before uploading

```powershell
# Sideload (Developer Mode must be on)
Add-AppxPackage -Path msix\output\School_Tool_2.2.2.0_x64.msix
```

Then open School Tool from the Start menu and verify:

1. Title bar reads `School Tool v2.2.2.0`.
2. Rail static-entries: **Instructions**, **What's new**, **Privacy Policy**.
3. Click **What's new** → modal opens with v2.2.2.0 release notes.
4. Click **Privacy Policy** → modal opens, no "future paid tier" wording.
5. **HYIA Transfer Code** runs on a sample input.
6. **Master Budget Compass Autofill** — both buttons visible: **Generate budget workbook** and **Compare two budgets**.
7. **Sub-Program Budget Report** — pick a CASES21 GL21157 PDF, click **Generate report** → result panel shows the log + 3 view tabs (Revenue / Expense / Combined) + faculty rail. **This is the critical fix — confirm the panel is not empty.**
8. **Refined PAL Search** — only the big "Open Refined PAL Search" button (no Clear button).
9. Status bar at the bottom: `v2.2.2.0 · feedback@schooltool.com.au`.

Uninstall the test:

```powershell
Get-AppxPackage *VicSchoolFinanceTools* | Remove-AppxPackage
```

---

## Submit on Partner Center

1. <https://partner.microsoft.com/dashboard> → **Windows & Xbox > Apps and games > School Tool** → **Start a submission**.
2. **Packages** → upload `msix\output\School_Tool_2.2.2.0_x64.msixupload`.
3. **Store listing** — paste the v2.2.2.0 patch notes into "What's new in this version":

   > **v2.2.2.0 — bug fix release**
   >
   > • Fixed: Sub-Program Budget Report now displays correctly after running.
   > • New "What's new" entry in the left rail opens an in-app changelog.
   > • Support address: feedback@schooltool.com.au.
   > • Privacy Policy wording trimmed.

4. Confirm the **Support contact info** field reads `feedback@schooltool.com.au`.
5. If your Privacy Policy URL points at a static host, redeploy the new content of `docs/store_privacy_policy.md` there so the Store's link stays in sync.
6. **Submit for certification.** Cert turnaround typically 1–3 business days.

After certification clears, the Round 30 Store-update prompt will fire on every existing user's next launch — they'll be offered the install and Sub-Program will work for them automatically.

---

## If anything goes wrong

| Symptom | Fix |
| --- | --- |
| `python app.py` crashes with `AttributeError: SHOW_USER_TAB` | `app_metadata.py` got truncated. Open it in an editor; line 27 must read `SHOW_USER_TAB: bool = False`. If it's just `SHOW_USER_TAB: bool` re-add the ` = False`. |
| `pip install -e .` complains about winrt | The Round 30 deps need Windows. Confirm you're on Windows; on a non-Windows dev box those installs are skipped, which is OK. |
| `makeappx.exe was not found` | Install Windows 10 SDK or copy `makeappx.exe` + `signtool.exe` to `.tools\msixsdk\` in the repo. |
| Identity-mismatch error during build | The script defaults are correct (`Vurctne.VicSchoolFinanceTools` / `CN=E75204F6-…`). Don't pass `-IdentityName` or `-Publisher` flags unless you know why. |
| Partner Center says "Package version conflict" | Some prior submission already used that version. Re-run with `-Version 2.2.2.1` (or higher) to bypass. |
| Store cert rejects with "WACK failure" | Run `appcert.exe runtest -apptype Desktop -packagefullname Vurctne.VicSchoolFinanceTools_2.2.2.0_x64__<publisher hash>` locally first; fix what it flags before re-submitting. |

---

## Files this round

```
ADD   handoff/round36_pack_for_store.md
```

No code changes — verification and Windows-side instructions only.
