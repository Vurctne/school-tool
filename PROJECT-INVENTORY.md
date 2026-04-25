# PROJECT-INVENTORY.md

**Snapshot date:** 2026-04-25
**Inventoried by:** Opus 4.7 orchestrator (no sub-agent dispatch — planning phase)
**Limit:** repo is not under git in the sandbox (`fatal: not a git repository`); commit-history portion of the inventory is therefore blank. Rest of the inventory is from filesystem + docs.

---

## 1. Project goal (one sentence)

Ship **School Tool v2.0.0** — a Windows MSIX desktop app for Victorian Government school business managers — to the Microsoft Store with three tools (HYIA / Master Budget / Sub-Program), a backend (Cloudflare Workers + D1 + R2) for registration + paid-tool licensing, and an admin dashboard for invoice + PO review.

Publisher: **Vurctne**. Legal seller on invoices: **ZXW Investment Pty Ltd** (ABN TBD). Support: `Vurctne@gmail.com`. Annual licence: **$550 + GST** per school for the paid tool (Sub-Program).

---

## 2. Authoritative documents (source of truth)

`docs/` is canonical per `README.md`. Read these before any structural decision:

| File | Purpose |
| --- | --- |
| `docs/01_REQUIREMENTS.md` | Product scope, per-tool specs, NFRs, acceptance criteria |
| `docs/02_ARCHITECTURE.md` | 14 ADRs (Tkinter, Python 3.12, BaseTool, threading, WeasyPrint, MSIX, etc.) |
| `docs/03_ROADMAP.md` | 6 milestones (M1–M6 ship v2.0.0; M7–M8 ship v2.1+); explicitly designed around Sonnet 4.6 sub-agents with parallel/serial dispatch + post-milestone code-review/test agents |
| `docs/04_BACKEND_DESIGN.md` | Cloudflare Workers layout, D1 schema, REST API surface, OCR pipeline, admin dashboard |
| `docs/05_DOMAIN_SETUP.md` | `schooltool.com.au` domain registration walk-through |
| `docs/Tools_in_Development.md` | Tool-by-tool status table (🟢 / 🟠 / 🔵 / ⚪) |
| `design_system/design_handoff_school_finance_toolkit/` | Read-only design reference (README + EXTENDING + colors_and_type.css + ui_kits) |
| `CLAUDE.md` | Runtime notes for AI agents — see §10 below; **partially out of date** |
| `handoff/phase1_drift_map.md`, `handoff/phase3_final_report.md` | Last round's highlight-colour alignment work |
| `TESTING.md` | Manual test paths (A: double-click, B: MSIX install, C: backend-connected) |
| `README.md` | Top-level orientation; points to `docs/` for detail |

**Key architectural insight:** the ROADMAP **already specifies the Orchestrator + Sonnet 4.6 sub-agent model** as the working method (every milestone has explicit "↯ parallel" and "→ serial" packages dispatched to Sonnet sub-agents, then independent code-review + test agents at milestone close). The reorg the user asked for in this round is to **operationally enforce** what the architecture already documents.

---

## 3. Milestone status — actual vs planned

Cross-referenced against TESTING.md ("alpha covers M1 + M2"), the registry, the backend layout, and the test corpus.

| Milestone | Planned scope | Status | Evidence |
| --- | --- | --- | --- |
| **M1** — shell + MSIX pipeline + HYIA pilot | done | ✅ shipped | `app.py`, full `toolkit/` module set, `tools/hyia/` with `frame.py` + `logic.py` + tests, `Run School Tool.bat`, `Build MSIX.bat`, `msix/` + `packaging/`, `.github/workflows/build.yml`, `assets/` MSIX logos all present. TESTING.md path A documents working HYIA flow. |
| **M2** — backend v0 + User tab + registration | partial | 🟠 ~70% | `backend/src/{index.ts, routes/{auth,me,schools,index}.ts, lib/{argon2,db,ed25519,env,ids,jwt,mailer,time}.ts}` exist with vitest tests; `migrations/0001_init.sql` present. **Missing**: `routes/invoices.ts`, `routes/pos.ts`, `routes/licences.ts`, OCR consumer worker, renewal-reminder cron worker. **Desktop side**: `toolkit/account.py`, `toolkit/api_client.py`, `toolkit/licence.py`, `toolkit/user_frame.py`, `toolkit/crypto_win.py` all present. **Blocked on configuration**: `app_metadata.LICENCE_PUBLIC_KEY = b""` (empty — Ed25519 keypair not yet generated/wired). |
| **M3** — MB Compass Autofill port + Sub-Program | mostly done | 🟠 ~90% | Both tools shipped (`tools/master_budget/`, `tools/sub_program/`) with logic.py + frame.py + tests. Last round's highlight-colour alignment work passed 191 tests. **3 bug reports from this session pending** (see §6). Licence-gate decorator existence not yet verified — needs check. |
| **M4** — invoice PDF + admin dashboard + PO upload | not started | ❌ | No `backend/src/routes/invoices.ts`, no admin Worker, no admin HTML templates, no R2 bucket integration code. |
| **M5** — OCR + auto-matching + renewal prompts | not started | ❌ | No OCR consumer, no template classifier, no renewal prompt logic on the desktop side. |
| **M6** — WACK + signed MSIX + Store submission | not started | ❌ | Privacy policy v1 only. No signed builds. |
| **M7** — SRP Comparison + Operating Statement | not started | ❌ | No `tools/srp/`, no `tools/operating/`. Sample data present in `Samples/`. |
| **M8** — Camps Reconciliation | blocked | ❌ | No `tools/camps/`. **Blocker**: sample exports not yet provided per ROADMAP §"Known blockers". |

**Net read:** project is mid-M2/M3 transition. M2 has the auth tier of the API but is missing the billing+licensing tier. M3 ship-readiness depends on M2 completion + the 3 pending bug fixes.

---

## 4. Code/data inventory by category

### 4.1 Production code (Python — `~13K LOC` across 52 files)

```
app.py                       — entrypoint (boot Tk + shell)
app_metadata.py              — APP_NAME, VERSION, SUPPORT_EMAIL, API_BASE_URL, LICENCE_PUBLIC_KEY (empty)
toolkit/
  __init__.py
  base_tool.py               — BaseTool ABC + InputSpec union (FileInput / TextInput / NumberInput / CurrencyInput / DateInput / SecretInput) + OutputSpec + ToolResult + LogLine
  registry.py                — _registered list + register() + all_tools() (imports tools.hyia + tools.master_budget + tools.sub_program)
  shell.py                   — TkShell window + rail + tool swap
  primitives.py              — FileRow, Banner, ProgressBar, LogView, Table, Metric, SectionHeader, CommentaryDialog
  tokens.py                  — AUTO-GENERATED from colors_and_type.css; do not hand-edit
  fills.py                   — argb() + bgr_int() helpers; HL_* ↔ --hl-* CSS docstring (added in last round)
  fonts.py                   — startup font probe (Aptos / Cascadia Mono / Source Serif 4)
  logging_setup.py           — rotating-file %LOCALAPPDATA% logger
  account.py                 — register/login/verify/reset flows (M2)
  api_client.py              — httpx wrapper around backend (M2)
  licence.py                 — Ed25519 verify, licence.json read/write, prompt schedule (M2/M5)
  user_frame.py              — User tab in left rail (Account/Service/Invoices/Support) (M2)
  crypto_win.py              — DPAPI wrapper (M1, used by HYIA "Remember SIN" + M2 account.dat)

tools/
  hyia/                      — HYIA Transfer Code Generator (M1)
    frame.py + logic.py + tests/{test_frame.py, test_logic.py}
  master_budget/             — Master Budget Compass Autofill (M3-a)
    frame.py + logic.py + tests/{test_frame.py, test_integration.py, test_logic.py, test_excel.py}
  sub_program/               — Sub-Program Budget Report (M3-b)
    frame.py + logic.py + tests/{test_frame.py, test_logic.py}
```

### 4.2 Backend code (TypeScript on Cloudflare Workers)

```
backend/
  wrangler.toml              — D1 / R2 / Queue / AI bindings, secrets
  package.json
  migrations/0001_init.sql   — full D1 schema (users, email_tokens, schools, user_schools, invoices, purchase_orders, licences, licence_devices, admin_events)
  src/
    index.ts                 — Hono app mount
    routes/
      index.ts
      auth.ts                — register / verify-email / login / password-reset / change
      me.ts                  — GET /v1/me
      schools.ts             — POST /v1/schools
    lib/
      argon2.ts, db.ts, ed25519.ts, env.ts, ids.ts, jwt.ts, mailer.ts, time.ts
  tests/{auth,db,me,schools}.test.ts   — vitest

NOT YET PRESENT (M2 incomplete + M4):
  src/routes/invoices.ts, pos.ts, licences.ts
  src/routes/admin/*
  src/workers/ocr_consumer.ts, renewal_reminder.ts
  src/templates/{invoice.html, emails/*}
```

### 4.3 Build / packaging / store

```
.github/workflows/build.yml           — CI: ruff + mypy + pytest (Linux runner with apt-get python3-tk + xvfb)
.github/workflows/backend.yml         — backend CI
Build MSIX.bat                        — convenience wrapper around msix/build_msix_package.ps1
Run School Tool.bat                   — local dev launcher
msix/                                 — AppxManifest.template.xml + build_msix_package.ps1 + makeappx.exe (vendored .tools/msixsdk/)
packaging/SchoolTool.spec             — PyInstaller spec
assets/                               — Square44 / Square150 / Wide310x150 / SplashScreen logos (PNG)
resources/                            — runtime resources (DoE PDFs etc.)
scripts/port_tokens.py                — regenerates toolkit/tokens.py from CSS
```

### 4.4 Tests

```
tests/                                — toolkit-level + drift guards
  test_account.py, test_api_client.py, test_base_tool.py, test_commentary_dialog.py,
  test_licence.py, test_licence_gate.py, test_registry.py, test_shell_smoke.py,
  test_tokens_drift.py (3 guards: drift / no-rogue-hex / canonical-PatternFill — Phase 3 of last round),
  test_user_frame.py
tools/<tool>/tests/                   — per-tool unit + integration

Last full run: 191 passed, 15 environmental skips, 0 failures.
```

### 4.5 Sample data (`Samples/`)

Inventory not deeply enumerated; ROADMAP confirms presence of:
- HYIA: spec PDF + xlsx reference ✅
- Sub-Program: GL21157 PDF ✅ + prior-period commentary XLSX (optional input) ✅
- SRP: `Samples/SRP budget Report/` ✅
- Operating Statement: `Samples/Operating Statement/` ✅
- Purchase Orders (for M5 OCR): `CR21107S_Purchase Orders by Batch.pdf`, `PurchaseOrder_P024900.pdf` ✅
- Camps reconciliation: ❌ blocker, samples not yet provided

### 4.6 Design system (`design_system/`)

Read-only canonical reference. Contains README, EXTENDING, colors_and_type.css, and `ui_kits/{brand_type, desktop_app, desktop_multitool, web_toolkit}/` — `.jsx` files are design references, not active code (web_toolkit deferred 12–18 months).

---

## 5. Stray / cruft / inconsistencies found during inventory

These are **not** in-flight work; they're maintenance items the inventory surfaced.

| Item | Path | Action recommendation |
| --- | --- | --- |
| Zero-byte stray file `=42` at repo root | `=42` | Delete. Looks like a stray shell redirect (e.g. `> =42`). |
| Duplicate `Tools_in_Development.md` | root vs `docs/` | Root version is **4-line obsolete stub** ("待开发项目" + 3 lines). `docs/` version is the canonical one. Archive the root copy or replace with a one-line redirect. |
| 12 vitest cruft files | `backend/vitest.config.ts.timestamp-*.mjs` | Add to `.gitignore` if not already; sweep. |
| Two `egg-info` directories | `school_finance_toolkit.egg-info/`, `school_tool.egg-info/` | Old project name still surviving. The current `pyproject.toml` says `name = "school-tool"` so the old egg-info is dead. |
| `backend/README` and `backend/README.md` | both | Possibly duplicate; verify whether one is intentional. |
| `CLAUDE.md` is partially out of date | root | (a) Says hyia is "off-spec / not in original 5" — actually IS in v2.0.0 scope per ROADMAP; (b) doesn't mention `backend/`, `docs/01-05`, `User tab`, licence flow, or M2-M6 work. Needs update before sub-agents read it as context (would mislead them). |

---

## 6. Active in-flight work (queue surfaced in this session)

Three buckets the user has explicitly raised, by priority:

### 6.1 Three pending bug reports (this session, screenshot-driven)

Source: previous user turn, with screenshot of Master Budget Compass Autofill output.

1. **OneDrive "Open output folder" doesn't open the right folder.** Root cause identified: `subprocess.Popen(["explorer", f"/select,{path}"])` in `tools/master_budget/frame.py:286`. When OneDrive paths contain spaces (e.g. `OneDrive - DET Schools`), Python's `list2cmdline` quotes the whole `/select,<path>` together; explorer.exe doesn't recognise that form. Fix is well-understood: pass as a single string so `CreateProcess` hands it to explorer's parser intact.
2. **IMPORT SUMMARY log uses wrong colours.** `tools/master_budget/frame.py:223` tags mismatch codes with `tag="warning"` (orange `#9A6700`) but Excel + Instructions text both say "Pink / red". Source-only uses `tag="extra"` (already green, close enough). Fix: change mismatch tag from `warning` to `danger` (`DANGER_FG = "#B00020"`); keep source-only as `extra`.
3. **IMPORT SUMMARY only reports row mismatches, never column mismatches.** `ImportSummary` dataclass only carries `mismatch_codes` (= `missing_master_codes`) and `source_only_codes` (= `missing_source_codes`); the parallel `missing_subprogram_codes` and `source_extra_subprogram_codes` (column mismatches) are passed to `_apply_mismatch_highlights_excel` for painting but never propagated to the frame for log/banner display. Fix: extend `ImportSummary` with `mismatch_subprogram_codes` + `source_only_subprogram_codes`; update `import_expense_sub_program` return; rewrite `_build_result` to render rows AND columns; update test fixtures.

### 6.2 Unfinished items from last round (highlight-colour alignment)

Per `handoff/phase1_drift_map.md` §"Suggested new tests" — Agent D proposed 6 new test assertions in Phase 1; Phase 3 Agent H implemented 2 (the AST drift guards). Still open:

4. Refactor `tools/sub_program/tests/test_frame.py:268` (`assert "F4CCCC" in row["_bg"]`) and `tools/sub_program/tests/test_logic.py:267-268` (`found_fill = "F4CCCC" in fill.fgColor.rgb.upper()`) to import `HL_MISMATCH` from `toolkit.tokens`.
5. Add `test_canonical_token_values` to `tests/test_tokens_drift.py` pinning the absolute hex of all three `HL_*`.
6. Add `test_over_budget_fill_all_columns` to verify every cell in an over-budget row is filled, not just column 1.
7. Replace `pytest.skip("No over-budget lines in sample PDF")` in `test_over_budget_fill_present` with a hard assertion.

### 6.3 Cosmetic / follow-up

8. Clean up `tools/sub_program/frame.py:91` comment `_OVER_BG = "#" + HL_MISMATCH  # "#F4CCCC"` (the trailing comment is stale).
9. Extend `scripts/port_tokens.py` to emit `# matches --hl-mismatch in colors_and_type.css` linking comments above each `HL_*` in the auto-generated `tokens.py`.

### 6.4 M2 backend completion (not yet on user's queue but blocks M3 ship)

10. `backend/src/routes/invoices.ts` — invoice creation + PDF render via Cloudflare Browser Rendering API or `@react-pdf/renderer`.
11. `backend/src/routes/pos.ts` — multipart upload to R2, OCR job enqueue.
12. `backend/src/routes/licences.ts` — `/v1/licences/activate` + `/refresh` returning Ed25519-signed token.
13. Generate Ed25519 keypair; populate `LICENCE_PUBLIC_KEY` in `app_metadata.py`; `wrangler secret put LICENCE_SIGNING_PRIVATE_KEY_ED25519`.
14. Resend integration for verification + reset emails (template HTML in `backend/src/templates/emails/`).

---

## 7. Known blockers / open decisions (from ROADMAP §"Known blockers")

| Blocker | Affects | Status |
| --- | --- | --- |
| ZXW Investment Pty Ltd ABN | Invoice template (M4 build can proceed; live invoicing cannot) | TBD — Ivan to provide |
| Seller bank details (BSB + account number) + registered address | First live invoice | TBD — Ivan to provide before billing |
| Camps Reconciliation sample exports | M8 entirely | TBD — Ivan to provide |
| Custom domain `schooltool.com.au` | M6 launch polish (optional at M2) | Pre-wired; awaiting Ivan to register at AU registrar |

---

## 8. Constraints / non-negotiables

From `docs/02_ARCHITECTURE.md` ADRs and CLAUDE.md / EXTENDING.md:

- **Stack:** Python 3.12 x64 only · Tkinter / ttk vista · openpyxl · pdfplumber · pywin32 · WeasyPrint
- **MSIX install size budget:** ≤ 90 MB
- **Cold-start:** ≤ 3 s; UI never blocks > 50 ms (all heavy work on worker thread)
- **Localisation:** en-AU only · sentence case · no emoji · U+2212 minus
- **Quality gates** (CI enforced): `ruff format --check` + `ruff check` + `mypy --strict` + `pytest`
- **Every Python file** must begin with `from __future__ import annotations`
- **`BaseTool` contract is frozen** (ADR-0004) — `run(paths, progress) -> ToolResult` is pure; tools never touch Tk, shell, or registry
- **`toolkit/tokens.py` is auto-generated** (see ADR-0009 + `scripts/port_tokens.py`); CI fails on drift via `tests/test_tokens_drift.py`
- **Highlight colour semantics frozen:** `HL_MISMATCH` (pink) = mismatch · `HL_SOURCE_ONLY` (green) = source-only · `HL_EDITED` (yellow) = legend-only ghost constant (no fill site applies it)
- **Locked-by-design surfaces** (require deliberate design-review cycle): window chrome, rail width 220 px, focus-ring colour, font stack, 4 px spacing grid, BaseTool contract
- **Privacy posture:** free tools 100 % offline; paid tools one server hit/year at activation, then offline; tool file contents never leave disk

---

## 9. Limitations of this inventory

1. **No git history.** The Cowork sandbox does not expose `.git/` for this repo (`fatal: not a git repository`). Either the working copy on Windows has `.git/` and it's not mounted, or the project is not under version control. **The "recent N commits" portion of the user's spec cannot be filled in from here.** If commit history is needed, Ivan can paste `git log --oneline -25` output, or this orchestrator can be run in an environment where git is reachable.
2. **No deep enumeration of `Samples/`.** Existence of each sample bucket is confirmed via ROADMAP cross-reference, but contents not enumerated. Sub-agents that need a specific sample should be given the path explicitly in their brief.
3. **`backend/node_modules/` skipped** — typical for an inventory of authored code.
4. **Cross-filesystem caveat (encountered in last round):** the Cowork Linux mount can lag the Windows-side view of recently-edited files. If sub-agents see `SyntaxError` at line numbers that don't exist in the Read-tool view of a file, the `pathlib.Path(p).write_text(p.read_text())` workaround restores parity. Documented in `CLAUDE.md` §Gotchas.

---

## 10. Open questions for the user before Step 2

1. **CLAUDE.md correction policy.** It's partially out of date (treats hyia as off-spec; doesn't describe backend / User tab / licensing). Sub-agents will read it as context. Two options: (a) fix it in this round before dispatching any sub-agent (~30 min of orchestrator work), or (b) leave it and write a richer `CONTEXT-SUMMARY.md` (Step 3) that supersedes it for sub-agent purposes. **Recommendation: (a)** — keeps a single canonical runtime doc for AI agents, no parallel summary to maintain.
2. **Reorg scope.** The user said "已经做完的工作不要推倒重来。只重组剩余工作。" Confirmed scope: nothing already in `tools/hyia/`, `tools/master_budget/`, `tools/sub_program/`, `toolkit/`, or `backend/src/routes/{auth,me,schools}.ts` gets touched unless we're fixing one of the §6 in-flight items. **Confirm.**
3. **Stray-cruft cleanup.** Items in §5 (`=42`, root-level `Tools_in_Development.md` stub, vitest timestamp cruft, dead egg-info, double `backend/README*`) — sweep them in Step 3 (context compression) or leave for a separate housekeeping pass? **Recommendation: sweep in Step 3.**
4. **Git mount.** Is `.git/` deliberately not in the Cowork mount, or is it absent on the Windows side too? If the latter, we should `git init` before reorg work piles up — orchestration progress without version control is fragile.
