# Vic School Tool v2 — Milestones Roadmap *(revised)*

> **Revision note**: first tool in v2.0.0 is **Annual Sub-Program Budget Report** (paid). Registration + invoice + PO flow must exist at launch. Backend (Cloudflare Workers + D1 + R2) builds in parallel with the desktop shell.
>
> Every work package marked **↯ parallel** dispatches a Sonnet 4.6 sub-agent alongside its siblings in the same message; **→ serial** waits on a predecessor. Each milestone ends with independent Sonnet *code-review* + *test* agents.

---

## Delivery sequence at a glance

| Milestone | Ships | Paid/Free | Needs backend? |
|---|---|---|---|
| M1 | Shell + MSIX pipeline + token port + **HYIA Transfer Code tool (pilot)** | free | no |
| M2 | Backend v0 (Cloudflare) + User tab + registration + licence token | n/a | yes |
| M3 | **Master Budget Compass Autofill port** + **Sub-Program Budget Report tool** (parallel) | mixed | yes (SubProgram only) |
| M4 | Invoice PDF + manual PO review admin dashboard | paid | yes |
| M5 | OCR + auto-matching pipeline + renewal prompts | paid | yes |
| M6 | WACK + signed MSIX + new Partner Center listing submission | release | yes |
| **v2.0.0 ships here (HYIA + MB Compass Autofill free · Sub-Program paid)** | | | |
| M7 | SRP Comparison + Operating Statement | mixed | yes (OpStat paid) |
| **v2.1.0 ships here** | | | |
| M8 | Camps Reconciliation + polish | paid | yes |
| **v2.2.0 ships here** | | | |

---

## M1 — Repo bootstrap + shell scaffold + HYIA pilot *(~4 days)*

**Goal**: shell with left rail + status bar + User-tab stub, with **two** tools registered: HYIA Transfer Code (fully functional, free) and Sub-Program Budget Report (stub — idle state only). CI green. First unsigned MSIX installs.

Building HYIA in M1 serves two purposes: (1) a real fully-shipping tool in v2.0.0 even if paid-tool work slips; (2) validates the BaseTool contract — especially the form-field input extension — before we commit the bigger paid tool against it.

**Entry**: Ivan has dropped v1 codebase at `master_budget_Compass import/` ✅ and samples at `Samples/` ✅

**Packages** *(5 parallel + 1 serial)*
1. **↯ Repo init** — per ADR-0003: `pyproject.toml`, `requirements.txt` / `-dev.txt`, `ruff`, `mypy --strict`, `pytest`, GitHub Actions workflow (lint + type + test). Bump `app_metadata.APP_VERSION → "2.0.0"`, `SUPPORT_EMAIL → "Vurctne@gmail.com"`, `APP_NAME → "School Tool"`.
2. **↯ Token port** — `scripts/port_tokens.py` generates `toolkit/tokens.py` from `colors_and_type.css`. CI drift check.
3. **↯ BaseTool + registry** — `toolkit/base_tool.py` with the **extended InputSpec** (ADR-0004: `FileInput | TextInput | NumberInput | CurrencyInput | DateInput | SecretInput` discriminated union). `toolkit/registry.py` registers `HyiaTool` + `SubProgramReportTool` (stub). `toolkit/crypto_win.py` with DPAPI wrapper for the optional *Remember SIN* path.
4. **↯ Shell chrome + primitives** — `toolkit/shell.py`, `toolkit/primitives.py`. Visual parity to `tk-shell.jsx` + `tk-primitives.jsx`. Rail groups: `Banking` (HYIA), `Budget` (Sub-Program), divider, `User`, `Instructions`, `About`. Shell must render form-field inputs (new primitives `TextField`, `NumberField`, `CurrencyField`, `DateField`, `SecretField`) alongside the existing `FileRow`.
5. **↯ HYIA tool end-to-end** — `tools/hyia/logic.py` (pure `compute_security_code(sin: int, amount_cents: int, d: date) -> int`), `tools/hyia/frame.py` (the 3 form fields + result area + Copy button + optional *Remember SIN*), golden tests that pin the DoE worked example `(12345, $20,000.00, 16/02/07) → 2012370` plus 5 edge cases. Bundle `resources/hyia_transfer_spec.pdf` (the DoE PDF) for the *Instructions* button.
6. **→ MSIX pipeline** — refactor v1 `build_msix_package.ps1` → `msix/build_msix_package.ps1`. PyInstaller spec. Copy MSIX logos. Produce v2.0.0-alpha unsigned MSIX that installs via `Add-AppxPackage`.

**Exit**: `python app.py` launches; rail + status bar render; **HYIA tool is fully functional and passes the DoE worked example test**; Sub-Program Budget Report stub shows idle state; User tab stub renders placeholder; ruff/mypy/pytest green; unsigned MSIX installs.

**Verification** *(2 parallel agents)*: code-review checks token parity + BaseTool contract (especially the new input-kind dispatch in the shell) + DPAPI usage; test agent smoke-launches, runs the HYIA golden suite, and installs the MSIX on a Windows runner.

---

## M2 — Backend v0 + User tab + registration *(~5 days)*

**Goal**: registered user can sign in from the desktop; their account, school, and (empty) licence state render in the User tab; server stores users + schools + issues draft invoices; no paid tool is usable yet.

This milestone **runs in parallel** with M3 once the API contract (below) is frozen on day 1 — desktop team mocks the API, backend team builds it, integration on day 4.

**Packages** *(5 parallel)*
1. **↯ Cloudflare project bootstrap** — `backend/` folder, `wrangler.toml`, Worker entrypoint. D1 database provisioned. R2 bucket for invoice PDFs. Secrets (licence signing key, SMTP, admin password hash) into `wrangler secret`. Deploy to `https://sft-api.<you>.workers.dev` (free tier subdomain — swap to custom domain later as one-line config).
2. **↯ Data model + migrations** — D1 schema for `users`, `schools`, `invoices`, `purchase_orders`, `licences`, `licence_devices`, `admin_events` (per `04_BACKEND_DESIGN.md §4`, ported from Postgres SQL to D1 SQLite — swap `JSONB` → `TEXT` with JSON coercion, keep everything else).
3. **↯ API v1 — auth + users + schools** — Hono routes on Workers:
   - `POST /v1/auth/register` `{email, password, first_name, last_name, school_name, abn}` → creates user + school, sends verification email via Resend (Cloudflare-friendly ESP).
   - `POST /v1/auth/verify-email` `{token}`.
   - `POST /v1/auth/login` `{email, password, device_id}` → JWT (90-day HS256).
   - `POST /v1/auth/password-reset/request` `{email}` → email with token.
   - `POST /v1/auth/password-reset/confirm` `{token, new_password}`.
   - `POST /v1/auth/password/change` `{old_password, new_password}`.
   - `GET /v1/me` → user + school + licence summary + invoices list.
4. **↯ Desktop User tab** — left rail `User` entry opens a `UserFrame`. Four sub-sections (tabs or accordion):
   - **Account** — sign-in form → after sign-in, shows email + school + ABN + *Change password* + *Forgot password* + *Sign out*.
   - **Service** — licence status (*Active until YYYY-MM-DD* / *No licence* / *Expired*), bound devices, *Refresh licence* button.
   - **Invoices** — list of issued invoices with *Download* links.
   - **Support** — pre-filled `mailto:Vurctne@gmail.com` draft with version + device + user info.
5. **↯ Desktop API client** — `toolkit/api_client.py` (httpx), `toolkit/account.py` (stores JWT + device_id in DPAPI-protected file at `%LOCALAPPDATA%\Packages\<MSIX>\LocalCache\account.dat`), `toolkit/licence.py` (Ed25519 verify, read/write `licence.json`).

**Exit**: user can register in the app, verify email, sign in, change password, and see their profile. No paid tool yet; User tab functional.

**Verification**: backend integration tests hit D1 via Miniflare; desktop tests use an httpx mock transport; end-to-end smoke on a real Cloudflare preview deployment.

---

## M3 — MB Compass Autofill port + Sub-Program Budget Report *(~8 days)*

**Goal**: two tools end-to-end in the v2 shell — Master Budget Compass Autofill (free, no gate) and Sub-Program Budget Report (paid, licence-gated). Run them in parallel.

### M3-a — Master Budget Compass Autofill port *(~4 days, parallel with M3-b)*

**Packages** *(3 parallel + 1 serial)*
1. **↯ Lift v1 logic** — copy v1 `budget_automation.py` into `tools/master_budget/logic.py`. Strip all Tk coupling (v1's logic was partly entangled with its UI). Expose pure functions: `detect_schema(path)`, `match_account_codes(source, master)`, `write_annotated(master_template, matches, output_path)`. Keep macro-preserving path via pywin32.
2. **↯ Re-skin frame** — build `tools/master_budget/frame.py` as a `BaseTool` matching the `tk-tools.jsx` TkMasterBudget artboard (new navy/Aptos/Cascadia tokens, 5 states, re-skinned banner/progress/log). Label: "Master Budget Compass Autofill". Short: "MB". Tier: free (no licence gate).
3. **↯ Golden-file parity tests** — fixtures in `tools/master_budget/tests/fixtures/` (a redacted Compass Expense Sub-Program XLSX + a Master Budget XLSM template + the expected annotated output). Assert openpyxl cell values + fill colours match v1.0.2 byte-for-byte (ignoring timestamp).
4. **→ Regression run** — install v1.0.2 MSIX and v2.0.0-alpha MSIX side-by-side on a Windows VM, run both against the shared fixture, `diff` outputs. Zero cell-level diff expected.

**Exit**: MB Compass Autofill in v2 produces identical output to v1.0.2 on a shared fixture. All 5 states (idle/running/success/warning/error) render per the design system.

### M3-b — Sub-Program Budget Report *(~6 days, parallel with M3-a)*

**Packages** *(4 parallel)*
1. **↯ Parser** — `tools/sub_program/logic.py` pure functions: read the CASES21 GL21157 PDF (`pdfplumber`), optionally join prior-period comments XLSX if supplied, flag over-budget lines, group by faculty. Unit tests against `Samples/Annual Subprogram Budget Report/GL21157_Annual Subprogram budget report.pdf`.
2. **↯ Tool frame** — `tools/sub_program/frame.py`: 2 file rows (comments input optional), banner, faculty rail (220 px) + result table split. Matches `tk-tools.jsx` TkSubProgram artboard.
3. **↯ Commentary modal** — `CommentaryDialog` primitive. Per-sub-program free text, survives to output. Esc cancels, Enter saves, focus returns to caller.
4. **↯ Licence gate** — shell-level `require_licence(feature="sub_program")` decorator. Before the tool frame renders, check `licence.json` for an active `sub_program` feature. If missing or expired past grace, replace the frame with a *Get started* CTA linking to User → Service.

**Exit**: on a seat with a valid licence, full tool works; without one, the *Get started* wall appears. Coverage ≥ 80 % on `tools/sub_program/logic.py`.

### M3 joint verification *(2 parallel agents)*
- **Code review** — v1→v2 port parity (macro preservation, openpyxl fill colours, schema detection edge cases); modal a11y; token compliance across both tool frames.
- **Tests** — golden-file diff for MB; faculty-rail filter + licence-gate for Sub-Program; coverage gates for both logic modules.

---

## M4 — Invoice PDF + PO upload + manual admin review *(~5 days)*

**Goal**: user can generate a real annual invoice from the app, download it as a PDF, upload a signed PO via drop-zone, and (from the admin side) you can log in to the dashboard, see the PO queue, open a PO, and approve it — which issues a licence token that the desktop picks up on *Refresh licence*.

**Packages** *(4 parallel + 1 serial)*
1. **↯ Invoice PDF generator** — WeasyPrint-style HTML/CSS template at `backend/templates/invoice.html` using the product's colour/type tokens. Fields: ZXW Investment Pty Ltd seller block (ABN <ABN TBD>, GST status TBD), buyer school block, `SFT-<YYYY>-<seq>` number, issue + due dates, line item *School Tool Pro — Annual licence*, $550.00 ex GST, $55.00 GST, **$605.00 total inc GST**. Render via a workerised print path (Cloudflare Workers don't bundle WeasyPrint cleanly — we'll run rendering in a containerised [Browser Rendering API](https://developers.cloudflare.com/browser-rendering/) call or switch to `@react-pdf/renderer` on a Worker; I'll pick whichever is cleaner on M4 day 1). Output to R2 `invoices/{id}.pdf`; return time-limited signed URL.
2. **↯ Invoice + PO API** — `POST /v1/invoices` (creates invoice + renders PDF + returns URL), `GET /v1/invoices/{id}/pdf` (redirect to signed URL), `POST /v1/purchase-orders` (multipart → stored in R2 `pos/{id}.pdf` with metadata row; status `uploaded` → `needs_review`).
3. **↯ Admin dashboard v0** — `admin.<your-domain>` Worker with server-rendered HTML + HTMX. Pages: Overview (counters), Users, Invoices, POs queue (*Needs review* default view), PO detail (iframe PDF + fields + invoice panel + Approve / Reject buttons), Licences, Audit log. Password + TOTP auth. Admin routes isolated from `/v1/*`.
4. **↯ Desktop billing UI** — Service tab: *Generate annual invoice* button, post-generation *Download invoice* link and *Upload signed PO* drop-zone. Status pills *Invoice issued* → *PO uploaded* → *Under review* → *Approved* → *Active licence*.
5. **→ End-to-end smoke** — full flow once packages 1–4 land: register → invoice → download → upload PO → admin approve → refresh → paid tool unlocks. Single Sonnet agent drives the scenario on a preview deployment.

**Exit**: the happy path works end-to-end. Invoices are correct (ABN / GST / totals match). The manual review lane works without the OCR layer.

**Verification**: code-review of invoice PDF rendering + admin auth hardening; test agent runs the full scenario 3× against the preview deploy with fresh state each time.

---

## M5 — OCR + auto-matching + renewal prompts *(~5 days)*

**Entry**: Ivan has dropped both sample PO forms into `Samples/`. Without them OCR work halts — parser accuracy lives or dies on real references.

**Packages** *(4 parallel)*
1. **↯ OCR client** — Worker-side OCR via Cloudflare AI or external (Aliyun OCR / Google Document AI — TBD in M5 kickoff based on what's cheapest + reliably English-on-AU-form-layouts). Pluggable interface.
2. **↯ Template classifier** — pHash of the two reference PDFs + text-marker fallback. Unknown template → `needs_review` with reason.
3. **↯ Field extractor + matcher** — regex + layout-box extraction per template; weighted match score vs invoice; `≥0.95` auto-approves, otherwise to admin queue. All thresholds configurable via D1 `settings` key-value.
4. **↯ Renewal prompts** — client-side logic:
   - On launch, compute `days_left = licence.expires_at - now`.
   - At 60 days: one-time modal "*Your licence expires in N days. Renew now?*" with *Renew* / *Remind me later* buttons. Flag in `licence.json` so it doesn't repeat.
   - At 30 days: second one-time modal.
   - At 7, 6, 5, 4, 3, 2, 1 days: show modal once per calendar day (deduped by `last_prompted_on`).
   - After expiry: the 14-day grace-period warning banner we already designed.
   - *Renew* button just deep-links to User tab → Service → *Generate renewal invoice*; reuses the M4 flow.

**Exit**: high-confidence auto-match unlocks licence within 30 s of upload; low-confidence lands in admin queue; renewal prompts fire on the correct schedule (tested via a clock-injection fixture).

**Verification**: accuracy spot-check on 10 real-and-fake POs; clock-injection test on prompt schedule; penetration sanity-check on admin auth.

---

## M6 — Store submission *(~4 days)*

**Goal**: v2.0.0 signed MSIX, WACK green, Partner Center submission created.

**Packages** *(3 parallel + 2 serial)*
1. **↯ Store listing** — refresh `store/listing_content.en-AU.md` for the Pro SKU; updated screenshots per `store/STORE_SCREENSHOT_SHOTLIST_*.md`; **new privacy policy** (replaces v1's "no network calls" copy — must disclose backend data flow: email, school + ABN, PO content, device id, app version, IP).
2. **↯ Signed MSIX** — build with Partner Center publisher identity; `signtool` with your cert; archive at `dist/`.
3. **↯ Custom domain decision** — buy `xmotor.com.au` (or similar) and point it at the Workers app, OR stay on `*.workers.dev` for launch and swap later. Either works; domain swap is a one-line `wrangler.toml` change.
4. **→ WACK** — Windows App Certification Kit on the signed MSIX. Fix blockers.
5. **→ Partner Center submission** — fill the submission form per v1's `PARTNER_CENTER_MSIX_SUBMISSION_v1.0.2.md`, attach MSIX + screenshots + notes for certification.

**Exit**: v2.0.0 submitted to Microsoft Store for certification. Partner Center receipt in hand.

**Verification**: full cross-tool audit (though we only have one tool in v2.0.0); security review on file-IO + backend endpoints; WACK output parsed for warnings.

---

## M7 — SRP + Operating Statement *(post v2.0.0, ~7 days)*

Two parsers (both PDFs per the sample files), two frames. SRP Comparison is free; Operating Statement is paid. Reuses the licence-gate decorator from M3-b. Ships as v2.1.0.

## M8 — Camps Reconciliation *(post v2.1.0, ~5 days)*

Gated on sample exports arriving (register + supplier invoices + Sub-Program ledger — not yet in `Samples/`). Three-way join, fourth metric strip, status thresholds. Paid. Ships as v2.2.0.

---

## Dependency view

```
v1 drop ──► M1 ──► M2 ──► M3 ──► M4 ──► M5 ──► M6 ──► STORE SUBMIT
                    │      │      │       │
                    │      │      │       └─ sample POs
                    │      │      └─ invoice template + admin UI
                    │      └─ licence gate primitive
                    └─ API contract frozen on day 1 of M2 → M3 can mock
                                                         │
                                                    v2.0.0 ships
                                                         │
                                                  ┌──────┴──────┐
                                                 M7            M8 ──► M9
                                            (free MB)       (paid)
```

## Parallelism snapshot

| Milestone | Parallel packages | Serial packages | Verification agents |
|---|---|---|---|
| M1 | 5 | 1 | 2 |
| M2 | 5 | 0 | 2 |
| M3 | 7 (3 MB + 4 SubProgram) | 1 | 2 |
| M4 | 4 | 1 | 2 |
| M5 | 4 | 0 | 2 |
| M6 | 3 | 2 | 2 |

## Cadence

- End of each milestone: I report to Ivan with file links via `computer://`, call out open risks, and get sign-off before dispatching the next milestone.
- Inside a milestone: I don't ping unless something is blocking (missing sample file, ambiguous design, or architecture question).
- Agent reports: capped at 300 words; I Read key files myself to verify before accepting.

## Known blockers / confirmed

- **M1** — nothing blocking. HYIA spec PDF + xlsx reference are in `Samples/` ✅.
- **M3** — Sub-Program Report fixture in `Samples/Annual Subprogram Budget Report/` ✅. Prior-period comments input now **optional** (tool runs with or without) — not blocking.
- **M4** — invoice template is parameterised; ZXW Investment registered address + BSB + account number will be supplied *when billing starts* (before first live invoice is issued). Not blocking M4 build — blocker for going live.
- **M5** — both sample PO PDFs landed in `Samples/Purchase Orders/` ✅ (`CR21107S_Purchase Orders by Batch.pdf` + `PurchaseOrder_P024900.pdf`).
- **M8** — SRP samples present (`Samples/SRP budget Report/`) ✅. Operating Statement samples present (`Samples/Operating Statement/`) ✅ (both PDFs — parser stack adjusted in architecture).
- **M9** — Camps register + supplier invoices + Sub-Program ledger samples still needed.
- **Packaging** — one MSIX bundles all three v2.0.0 tools (HYIA + MB Compass Autofill + Sub-Program Budget Report). New Microsoft Store listing (new Partner Center product / Identity Name), parallel to the frozen v1.0.2 listing.

## Out of scope

- Web toolkit (`ui_kits/web_toolkit/`) — 12–18 months out; same registry ports 1:1.
- Card payments / Stripe — v3.
- Multi-tool bundles / tiered pricing — start flat.
- Session persistence beyond licence/account caches.
- Dark mode, ARM64.
