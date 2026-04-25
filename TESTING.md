# Testing School Tool v2.0.0-alpha

This is an early test build covering **M1 + M2**. You can test three slices:

| Path | How to launch | What you test | Time | Needs backend? |
|---|---|---|---|---|
| **A — Double-click run** | Double-click `Run School Tool.bat` | HYIA tool, shell chrome, User tab layout | ~2 min first run, instant after | No |
| **B — MSIX install** | Double-click `Build MSIX.bat` | Full install flow, Start-menu tile, real usage | ~5 min first time | No (for HYIA) · Yes (for User tab sign-in) |
| **C — Backend-connected** | `wrangler deploy` + rerun path A/B | Registration, email verification, sign-in, User tab state | ~1 hour first time | Yes |

Start with **A**. When you're happy, move to **B**. Do **C** when you want to test the account flow end-to-end.

---

## Prerequisites (Windows 11)

- **Python 3.12.x** — [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12`
- **git** — for cloning
- **(Path B only)** PyInstaller + Windows 10 SDK (for `makeappx.exe`). The `.tools/msixsdk/` from v1 is NOT in this repo yet — we'll pull it across if you want to sign builds.
- **(Path C only)** Node.js 20+ and a Cloudflare account (free tier is fine).

---

## Path A — Double-click run *(do this first)*

Goal: see the shell, use the HYIA tool, poke around the User tab.

**Open the `Vic_School_Finance_Tools` folder in File Explorer and double-click `Run School Tool.bat`.**

That's it. The launcher handles everything:
- Checks Python 3.12 is installed (hint if not).
- Creates a local `.venv\` on first run (~30 s).
- Installs dependencies on first run (~60 s).
- Launches the app.

On subsequent double-clicks it skips setup and launches in under a second.

If you prefer the manual path:
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python app.py
```

### What you should see
- Window titled **`School Tool v2.0.0 — HYIA Transfer Code`** opens at 1200×820.
- Navy chip reading **`HY`** top-left.
- Left rail with two groups: **Banking → HYIA Transfer Code** (highlighted), **Budget → Sub-Program Budget Report** (grey, will be wired in M3). Below the divider: **User**, **Instructions**, **About**.
- Tool screen shows: SIN field (masked, with eye toggle), Transfer amount ($ prefix), Date of request (default today), *Generate code* button.

### Things to try

1. **DoE worked example** — SIN `12345`, amount `$20,000.00`, date `16/02/2007` → click *Generate code* → you should see **Security code: 2012370** and the breakdown line `***** + 2000000 + 16 + 2 + 7 = 2012370` (SIN masked).
2. **Your real calculation** — plug in your school's SIN, today's amount, today's date. Tick *Remember SIN on this device* if you want — it'll DPAPI-encrypt the SIN to `%LOCALAPPDATA%` so you don't need to retype next time.
3. **Copy the code** — the big number is selectable; copy with Ctrl+C.
4. **Switch tools** — click *Sub-Program Budget Report* in the rail. Expect the idle screen to render but the primary button to be stubbed (`Coming in M3`).
5. **User tab** — click **User** in the rail. You'll see the Account / Service / Invoices / Support sections. *Sign in* and *Register* buttons will error because there's no backend running yet — that's path C.
6. **Support button** — click *Email support* in the Support section. It should open your default mail client composing to `Vurctne@gmail.com` with app version + OS + user email prefilled in the body.

### Known limitations in path A

- Sub-Program Budget Report is a placeholder — clicking *Generate* does nothing useful.
- Sign-in / Register / Generate annual invoice / Upload PO / Refresh licence all error out with `Network error (0)` because there's no backend. Expected.
- Fonts: if you see **Segoe UI** instead of **Aptos**, your Windows is < 22H2. Falls back gracefully; not a bug.

---

## Path B — MSIX install

Goal: install the app like a real Store product.

**Double-click `Build MSIX.bat`** at the repo root.

The builder:
1. Reuses the venv from path A (creates one if missing).
2. Runs PyInstaller via `packaging/SchoolTool.spec` → produces `dist/School Tool v2.0.0-alpha/`.
3. Stages assets + manifest.
4. Packages into `msix/output/SchoolTool_v2.0.0-alpha.msix` via the vendored `makeappx.exe`.
5. Leaves the window open with the output path.

Equivalent PowerShell one-liner:
```powershell
.\msix\build_msix_package.ps1 -Version 2.0.0-alpha -NoSign
```

The script:
1. Cleans `build/`, `dist/`, `msix/staging/`, `msix/output/`.
2. Runs PyInstaller via `packaging/SchoolTool.spec` → produces `dist/School Tool v2.0.0-alpha/` (one folder with the exe + dependencies).
3. Stages the folder + tile assets into `msix/staging/`.
4. Packages into `msix/output/SchoolToolkit_v2.0.0-alpha.msix` via `makeappx.exe`.

### Install the unsigned MSIX (developer mode required)

```powershell
# Enable developer mode once: Settings → Privacy & security → For developers → Developer Mode = On
Add-AppxPackage -Path .\msix\output\SchoolToolkit_v2.0.0-alpha.msix -AllowUnsigned
```

### What to test

- Start menu shows **School Tool** with the ST navy tile.
- Launch — same app you saw in path A, but packaged.
- Uninstall via Settings → Apps, or:
  ```powershell
  Get-AppxPackage *SchoolTool* | Remove-AppxPackage
  ```

### Path B is ready

The vendored MSIX SDK (`.tools/msixsdk/` with `makeappx.exe`, `signtool.exe`, and supporting DLLs) is now copied across from your v1 repo. No Windows 10 SDK install needed.

---

## Path C — Backend-connected (account flow)

Goal: register a test account, verify email, sign in from the desktop, see the User tab reflect real state.

### 1. Deploy the backend (one-time)

```powershell
cd backend
npm install
# Creates the D1 database (one-time):
npx wrangler login                  # opens browser, authenticate
npx wrangler d1 create sft          # note the database_id it prints
# paste the database_id into wrangler.toml where the placeholder sits
npx wrangler r2 bucket create sft-assets

# Generate an Ed25519 keypair for licence signing:
node -e "const n=require('@noble/ed25519'); n.utils.randomPrivateKey().then(async k=>{const pk=await n.getPublicKeyAsync(k); console.log('PRIV_B64=' + Buffer.from(k).toString('base64')); console.log('PUB_B64=' + Buffer.from(pk).toString('base64'));})"

# Feed secrets:
npx wrangler secret put JWT_SECRET_USER            # paste a 32-byte random hex
npx wrangler secret put JWT_SECRET_ADMIN           # another random
npx wrangler secret put LICENCE_SIGNING_PRIVATE_KEY_ED25519   # paste PRIV_B64 from above
npx wrangler secret put RESEND_API_KEY             # your Resend key (from resend.com, free tier)
npx wrangler secret put ADMIN_PASSWORD_ARGON2_HASH # placeholder '$argon2id$test' — M4 uses it
npx wrangler secret put ADMIN_TOTP_SECRET          # placeholder 'TESTSECRET'

# Run migrations:
npx wrangler d1 execute sft --remote --file ./migrations/0001_init.sql

# Deploy:
npx wrangler deploy
# Prints your URL, e.g. https://sft-api.<your-account>.workers.dev
```

### 2. Wire the desktop to your backend

Edit `app_metadata.py`:

```python
API_BASE_URL = "https://sft-api.<your-account>.workers.dev"
LICENCE_PUBLIC_KEY = b"<PUB_B64 from step 1 as bytes>"
```

Then run `python app.py` again.

### 3. Test the account flow

1. **User → Register** — enter a real email you can check, password (10+ chars), first/last name, your school name, ABN.
2. Check inbox for the verification link (from Resend). Click it — takes you to a simple success page served by the Worker.
3. **User → Account → Sign in** — same email + password. The sign-in pill should flip to your name + school.
4. **User → Service** — shows `No licence` (M2 doesn't issue licences yet; that's M4).
5. **User → Change password** — verify the flow.
6. **User → Forgot password** — enter the same email, get a reset link, change password.

### 4. Backend admin sanity

Check the D1 console in the Cloudflare dashboard. You should see:
- 1 row in `users`
- 1 row in `schools`
- 1 row in `user_schools` linking you to your school
- 2 rows in `email_tokens` (verify + any reset you requested)

### Known limitations in path C

- No admin dashboard yet — that's M4.
- No invoice PDF generation — M4.
- No PO upload or OCR — M5.
- No actual licence issuance — every login will show `state: "none"` in the Service tab.

---

## What I'm tracking in this test window

Before M3 fires, let me know:

1. **Does the HYIA tool work for you on a real transfer?** (path A)
2. **Does the rebrand look right?** (ST tile, navy, Source Serif 4 wordmark)
3. **Any copy you want changed** in the User tab or error banners?
4. **Does the MSIX install cleanly?** (path B — optional)
5. **Does registration + sign-in round-trip for you?** (path C — optional)

Any bug, surprise, or thing that feels off — just paste the reproduction here and I'll fix.

---

## Reset between test runs

```powershell
# Wipe the local cache (licence.json, account.dat, device_id.dat, stored SIN):
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Packages\SchoolTool*\LocalCache" -ErrorAction SilentlyContinue
# Reinstall the MSIX if you built one:
Get-AppxPackage *SchoolTool* | Remove-AppxPackage
Add-AppxPackage -Path .\msix\output\*.msix -AllowUnsigned
```
