# CLAUDE.md — School Tool v2.0.0

Working notes for Claude (and other agentic developers) on this repo. Two parts: the **permanent design contract** (read-only — comes from `docs/` and the v2 design handoff; don't litigate it here, point to it) and a **current-state snapshot** (dated; will go stale; update when reality changes).

---

## What this is

**School Tool v2.0.0** — a multi-tool Windows desktop application for Victorian Government school business managers, shipped as an MSIX through the Microsoft Store on DoE-managed Windows 11 laptops. v2 of an existing single-tool Tkinter app (`app.py` → `toolkit/shell.py` + per-tool frames).

Three tools at v2.0.0 launch:

| Tool | Group | Tier | Status |
| --- | --- | --- | --- |
| HYIA Transfer Code Generator | Banking | Free | M1 ✅ shipped |
| Master Budget Compass Autofill | Budget | Free | M3-a ~shipped |
| Sub-Program Budget Report | Budget | Paid — $550 + GST/year/school | M3-b ~shipped |

Stack: **Python 3.12 + Tkinter + openpyxl + pdfplumber + pywin32 + WeasyPrint** (desktop) + **Cloudflare Workers + D1 + R2 + Hono + Resend** (backend, M2-M5).

Publisher: **Vurctne**. Legal seller on invoices: **ZXW Investment Pty Ltd** (ABN `<TBD>`). Support: `Vurctne@gmail.com`.

---

## Permanent design contract (canonical — do not relitigate here)

Authoritative documents live in two places. **Read these before any structural decision.**

### `docs/` — the project's source of truth (per `README.md`)

- `docs/01_REQUIREMENTS.md` — product scope, per-tool specs, NFRs, acceptance criteria.
- `docs/02_ARCHITECTURE.md` — 14 ADRs (Tkinter, Python 3.12, BaseTool, threading, WeasyPrint, MSIX, etc.).
- `docs/03_ROADMAP.md` — 8 milestones (M1-M6 ship v2.0.0; M7-M8 ship v2.1+). **Already specifies the Orchestrator + Sonnet 4.6 sub-agent working method** — every milestone has explicit "↯ parallel" / "→ serial" packages dispatched to Sonnet sub-agents, then independent code-review + test agents at milestone close.
- `docs/04_BACKEND_DESIGN.md` — Cloudflare Workers layout, D1 schema, REST API surface, OCR pipeline, admin dashboard, licence model.
- `docs/05_DOMAIN_SETUP.md` — `schooltool.com.au` registration walk-through.
- `docs/Tools_in_Development.md` — tool-by-tool status table.

### `design_system/design_handoff_school_finance_toolkit/` — read-only design reference

- `README.md` — the visual v2 plan: shell anatomy, design tokens, numerics contract, PDF templates.
- `EXTENDING.md` — the framework contract: `BaseTool`, registration, what's extendable vs locked, the 10-minute "add a tool" checklist.
- `colors_and_type.css` — single source of truth for every colour, type token, spacing unit, and radius. **`toolkit/tokens.py` is auto-generated from this file by `scripts/port_tokens.py`** — see "gotchas".
- `ui_kits/` — `.jsx` files are design references, NOT active code. `web_toolkit/` is deferred 12–18 months.

### Hard rules from those docs that are easy to violate by accident

- **`BaseTool` is non-negotiable** (ADR-0004). A tool is a class with `id`, `group`, `label`, `order`, `short`, `inputs` (a discriminated union of `FileInput | TextInput | NumberInput | CurrencyInput | DateInput | SecretInput`), `output`, optional `pdf_template`/`pdf_body`, and `run(paths, progress) -> ToolResult`. The shell renders pickers, primary button, progress, banner, log, and table from that declaration. **Never put shell-aware code inside a tool**; if the tool needs something the shell doesn't provide, extend `BaseTool` / `toolkit/shell.py`, not the tool.
- **Registration = one line in `toolkit/registry.py`** (the registry imports the tool package and `tools/<id>/__init__.py` calls `register(<ToolClass>)`). Adding a tool should not touch the shell, the installer, or the build script.
- **Locked surfaces** (deliberate design change to touch — see ADR-0014): window chrome, left rail layout (220 px), focus-ring colour, font stack, 4 px spacing grid, sentence-case button copy, Australian English, no emoji, U+2212 minus, BaseTool contract.
- **Extendable without touching the shell:** banner levels (`toolkit.primitives.BANNER_COLORS`), log tags (`LOG_TAGS`), highlight fills (via `toolkit/fills.py`), tool-specific modals (override `BaseTool.open_dialog`), extra toolbar buttons (`secondary_actions()`).
- **Highlight colour semantics are frozen:** pink (`HL_MISMATCH = F4CCCC`) = over budget / mismatch; green (`HL_SOURCE_ONLY = E2F0D9`) = source-only inserted row; yellow (`HL_EDITED = FFF2CC`) = user-edited convention (legend-only ghost constant — no fill site applies it today). Do not invent new highlight colours without changing the CSS first.
- **Numerics contract** (REQ §6, design handoff §4): tabular figures everywhere; comma thousands separator; Unicode minus (U+2212), not hyphen; `$` prefix with no space; banker's rounding; colour is never the only signal (negative is red **and** has a minus).
- **PDF output via WeasyPrint** (ADR-0006), never ReportLab. Templates in `reports/<tool>_cover.html` + `reports/<tool>_body.html` + `reports/report.css`. Fonts (Source Serif 4, Cascadia Mono) embedded **once** in the MSIX.
- **CI quality gates — all four must pass before merge:** `ruff format --check`, `ruff check`, `mypy --strict`, `pytest`. Enforced by `.github/workflows/build.yml`.
- **Every Python file** must begin with `from __future__ import annotations` (per `README.md`).
- **Privacy posture:** free tools 100% offline, zero server calls. Paid tools do one server hit per year at activation, then fully offline. Tool file contents never leave disk.

### Backend specifics (`docs/04_BACKEND_DESIGN.md`)

- Workers + D1 (SQLite) + R2 (object storage) + Queues (OCR jobs) + Workers AI (OCR) + Resend (email).
- Auth: Argon2id passwords; HS256 user JWTs (90-day); admin password + TOTP.
- Licences: device-bound annual tokens, **Ed25519-signed**, cached at `%LOCALAPPDATA%\Packages\<MSIX>\LocalCache\licence.json`. Public key embedded in `toolkit/licence.py` (currently `b""` placeholder — populated when the keypair is generated at the start of M2 completion).
- Pricing: $550 ex GST + $55 GST = **$605 inc GST** annual. Renewal prompts at 60 / 30 / last-7-daily.
- Admin actions exposed as first-class buttons: *Extend licence*, *Grant licence* (for comp / pilot / EFT-without-PO scenarios), *Revoke*. Every action writes to `admin_events` (audit trail).

---

## Current-state snapshot (2026-04-25)

This drifts. Update when it changes.

### Milestone status

| Milestone | Planned | Status | Notes |
| --- | --- | --- | --- |
| M1 | Shell + MSIX pipeline + token port + HYIA tool | ✅ shipped | All present; HYIA tool functional per TESTING.md path A |
| M2 | Backend v0 + User tab + registration + licence token | 🟠 ~70% | `auth/`, `me`, `schools` routes + tests done. **Missing**: `routes/invoices.ts`, `routes/pos.ts`, `routes/licences.ts`, OCR consumer, renewal cron. `app_metadata.LICENCE_PUBLIC_KEY = b""` (Ed25519 keypair not generated). |
| M3 | MB Compass Autofill port + Sub-Program tool | 🟠 ~90% | Both tools shipped; 191 tests green; **3 bug reports + 4 unfinished tests pending** (see below). |
| M4 | Invoice PDF + admin dashboard + PO upload | ❌ | not started |
| M5 | OCR + auto-matching + renewal prompts | ❌ | not started |
| M6 | WACK + signed MSIX + Store submission | ❌ | not started |
| M7 | SRP Comparison + Operating Statement | ❌ | not started; samples in `Samples/` |
| M8 | Camps Reconciliation | ❌ blocked | sample exports not yet provided |

### Tools currently in the registry

`toolkit/registry.py` imports three tool packages (each registers its class via `tools/<id>/__init__.py`):

- `tools.hyia` (M1 — `HyiaTool`, group `Banking`)
- `tools.master_budget` (M3-a — `MasterBudgetTool`, group `Budget`)
- `tools.sub_program` (M3-b — `SubProgramBudgetReportTool`, group `Budget`, paid/licence-gated)

### Token / fill architecture (after 2026-04-25 alignment work)

- `toolkit/tokens.py` — auto-generated, **DO NOT EDIT BY HAND**. The file's first line says so; `tests/test_tokens_drift.py::test_tokens_not_drifted` runs `python scripts/port_tokens.py --check` and fails CI on drift.
- `toolkit/fills.py` — sibling module that converts an `HL_*` 6-char hex into the encoding a specific renderer needs:
  - `argb(hex_rgb) -> str` for `openpyxl.styles.PatternFill(fgColor=...)` (prepends `"FF"` alpha)
  - `bgr_int(hex_rgb) -> int` for Win32 COM `.Interior.Color`
  - Module docstring maps each `HL_*` ↔ `--hl-*` CSS property and flags `HL_EDITED` as a **legend-only ghost constant** (defined and documented in instruction text, but no fill site applies it today).
- `tests/test_tokens_drift.py` enforces three guards:
  1. `test_tokens_not_drifted` — Python ↔ CSS sync.
  2. `test_no_rogue_hex_in_tool_strings` — no `#RRGGBB` in any user-facing string under `tools/` may differ from a canonical `HL_*` value (AST scan, excludes `tests/` subfolders).
  3. `test_pattern_fill_colours_are_canonical` — every `PatternFill(fgColor=...)` in `tools/` must derive from `argb(<HL_*>)` or be a canonical ARGB literal. Has a sentinel that fails if no `PatternFill` calls are found at all (so accidental wholesale removal of fills can't silently bypass the check).
- The Win32 COM regression test `tools/master_budget/tests/test_logic.py::test_com_interior_colour_matches_hl_mismatch` is now a math + wiring check (originally added 2026-04-24 after the M3 code review; migrated 2026-04-25 to survive the fills-module refactor without losing its semantic guarantee). When refactoring `_apply_mismatch_highlights_excel`, preserve that test's intent.

### In-flight work surfaced this session (queue)

Four buckets, by priority. Detail in `PROJECT-INVENTORY.md` §6.

1. **3 bug reports against Master Budget Compass Autofill** (screenshot-driven, 2026-04-25):
   - OneDrive `Open output folder` doesn't open the right folder (root cause: `subprocess.Popen(["explorer", f"/select,{path}"])` with spaces in path; fix is to pass as a single string so explorer's parser handles `/select,"<path>"` correctly).
   - `IMPORT SUMMARY` log uses `tag="warning"` (orange) for mismatch codes; should be `tag="danger"` (red) to match the Excel pink fill + Instructions text "Pink / red".
   - `IMPORT SUMMARY` only reports row mismatches; column mismatches (`missing_subprogram_codes`, `source_extra_subprogram_codes`) are painted but not surfaced. Fix: extend `ImportSummary` dataclass with two new fields, update return + `_build_result` + tests.
2. **4 unfinished test improvements from last round** (per `handoff/phase1_drift_map.md` §"Suggested new tests"; Agent D proposed 6, Agent H implemented 2):
   - Refactor `tools/sub_program/tests/test_frame.py:268` and `tools/sub_program/tests/test_logic.py:267-268` to import `HL_MISMATCH` instead of bare `"F4CCCC"`.
   - Add `test_canonical_token_values` pinning absolute hex of all three `HL_*` in `tests/test_tokens_drift.py`.
   - Add `test_over_budget_fill_all_columns` (verify every cell in over-budget rows is filled, not just column 1).
   - Replace `pytest.skip("No over-budget lines in sample PDF")` with a hard assertion.
3. **2 cosmetic follow-ups**:
   - `_OVER_BG = "#" + HL_MISMATCH  # "#F4CCCC"` in `tools/sub_program/frame.py:91` — trailing comment is stale.
   - Extend `scripts/port_tokens.py` to emit `# matches --hl-*` linking comments above each `HL_*` in auto-generated `tokens.py`.
4. **6 M2 backend completion items** (block M3 ship): `routes/invoices.ts`, `routes/pos.ts`, `routes/licences.ts`, Ed25519 keypair generation + `LICENCE_PUBLIC_KEY` populate, Resend email templates, OCR consumer skeleton.

### Test entry points

```
pytest tests/                           # toolkit-level tests + drift guards
pytest tools/sub_program/tests/         # sub_program unit + integration
pytest tools/master_budget/tests/       # master_budget unit + integration + Win32 regression
pytest tools/hyia/tests/                # hyia unit + golden DoE worked example
cd backend && pnpm run test             # backend vitest (auth / me / schools / db)
```

On Linux CI, expect ~15 environmental skips on the desktop side (`tkinter` absent, `pywin32` Windows-only). They are not failures.

### Open blockers / decisions awaiting Ivan

| Blocker | Affects | Status |
| --- | --- | --- |
| ZXW Investment ABN | Invoice template (M4 build can proceed; live invoicing cannot) | TBD |
| Seller bank details (BSB + account number) + registered address | First live invoice | TBD |
| Camps Reconciliation sample exports | M8 entirely | TBD |
| Custom domain `schooltool.com.au` | M6 launch polish (optional at M2) | Pre-wired in code; awaiting registration |
| Microsoft Store Partner Center identity | Signed MSIX (M6) | Confirmed available per ROADMAP, not yet plumbed |

---

## Gotchas / tribal knowledge

Things you can't infer from reading the code:

- **`toolkit/tokens.py` regeneration is silent on success.** Editing it by hand "works" until the next CI run, where `test_tokens_not_drifted` fails with a `port_tokens.py --check` diff. To change a colour: edit `colors_and_type.css`, run `python scripts/port_tokens.py`, commit both files together.
- **`master_budget/logic.py` has two parallel paint paths.** openpyxl (cross-platform) and Win32 COM (`Interior.Color`, Windows-only, `pywin32`). They must produce visually identical output — the COM path preserves macros, the openpyxl path runs in CI. They were routed through `toolkit.fills` on 2026-04-25 so they can't drift apart again.
- **Python uses `.pyc` bytecode caches aggressively.** A stale `.pyc` can mask a corrupted `.py` source: `import` works, but `ast.parse(file.read_text())` fails with `SyntaxError`. If you see that pattern, the source is corrupted on disk; don't assume the import success means the file is OK.
- **Cowork sandbox cross-filesystem divergence.** The Windows-side file tools (Read/Edit/Write) and the Linux bash mount can disagree about the contents of a recently-edited file — bash may see a truncated version while Read shows the full one. Symptom: AST-parsing tests fail with `SyntaxError` at line numbers the Read tool says don't exist. Workaround: re-write the file from bash with `pathlib.Path(p).write_text(p.read_text())` to force the views to converge. Encountered 2026-04-25 during Phase 3 verification.
- **Cowork sandbox can't delete files by default.** Even files just `touch`-ed return `rm: Operation not permitted`. To delete from the agent side, call `mcp__cowork__allow_cowork_file_delete` per file with a clear rationale; the user approves each request. For bulk deletes, ask Ivan to run `Remove-Item` from PowerShell instead. Encountered 2026-04-25 during the Orchestrator+Sub-agent reorg setup.
- **Git is unusable from the agent side as a result.** Every `git config` / `git add` / `git commit` performs an `unlink()` of internal lock or temp files (`config.lock`, `index.lock`, packfiles, ref locks) — and unlink is exactly what the sandbox blocks. Even after the user re-runs `git init` on Windows, the agent's `git status` first call typically fails with `fatal: unknown error occurred while reading the configuration files` because the mount's stale view of `.git/config` ENOENTs on read. Sub-agents (Sonnet 4.6) run in the same sandbox, so this constraint applies to them too — switching models does not help.
- **In Cowork mode, do NOT auto-suggest commit commands.** Ivan controls commit timing and wording explicitly. After making file changes via Read/Edit/Write, end the response with a summary of what changed and stop — do not append "now run `git add … && git commit -m "…"` on Windows" suggestions. When Ivan wants code he'll ask ("give me the commit command" / "what should I commit?"). Plan documents like `ORCHESTRATION-PLAN.md` may describe a per-phase commit cadence as a contract — that's documentation, not a live suggestion. Rule established 2026-04-25.
- **`mypy --strict` needs `--cache-dir=/tmp/mypy_cache` in the Cowork sandbox.** mypy uses a SQLite metastore cache; the default location (`.mypy_cache/` in the project) is in the mount that disallows the file-locking ops SQLite needs. Symptom: `INTERNAL ERROR ... OperationalError: disk I/O error` even on a clean repo. Workaround: redirect the cache to `/tmp`. The `/tmp` filesystem in the sandbox is unrestricted. Encountered 2026-04-25 during Phase 1 closing checks.
- **Existing instruction text in `tools/*/frame.py` is `f"""..."""`, not `"""..."""`** — every hex colour mentioned in the user-visible help string interpolates from `HL_*`. If you add a new one, use the same pattern.
- **`HL_EDITED` is a ghost constant** — defined, documented in instruction text, but no fill site applies it today. The legend says yellow = "user-edited cell convention preserved from a prior version". If you ever need to actually paint a cell yellow, add the fill site, but don't remove the constant.
- **Tkinter colour vs openpyxl ARGB vs Win32 BGR are three different encodings.** Tkinter wants `"#RRGGBB"`; openpyxl wants `"FFRRGGBB"` (8 chars, ARGB); Win32 COM wants an integer encoded `BB<<16 | GG<<8 | RR`. `toolkit/fills.argb()` and `bgr_int()` handle the latter two. Tkinter still uses inline `"#" + HL_*` (one call site at `tools/sub_program/frame.py:91`); if a second appears, factor out a `tk_hex()` helper.
- **`# noqa: F401` smells.** When you see one on a `from toolkit.tokens import HL_*` line, it usually means a refactor was started and not finished — those imports were placed for future use that never landed. Treat as a TODO.
- **Two egg-info directories live in the repo** (`school_finance_toolkit.egg-info/`, `school_tool.egg-info/`). The first is from a prior project name; both regenerate on `pip install -e`. They're in `.gitignore`. Not worth deleting unless they're confusing tooling.

---

## When in doubt

- Product / tool spec / acceptance criteria → `docs/01_REQUIREMENTS.md`.
- Architecture decision (Tkinter, threading, MSIX, etc.) → `docs/02_ARCHITECTURE.md`.
- "What's the next milestone? What's the parallel/serial structure?" → `docs/03_ROADMAP.md`.
- Backend / API / D1 schema / admin actions → `docs/04_BACKEND_DESIGN.md`.
- Style, copy, layout, colour question → `design_system/design_handoff_school_finance_toolkit/`.
- "How do I add a tool?" → `design_system/.../EXTENDING.md` §"Adding a tool — 10-minute checklist".
- "Can I change X?" → if it's locked-by-design (ADR-0014 / EXTENDING.md "What stays locked"), raise it as a deliberate design change first.
- "What's the current orchestrator state? Active sub-agents? Cumulative metrics?" → `ORCHESTRATION-STATUS.md` (created during the 2026-04-25 reorg).
- "What did the last colour-alignment work do?" → `handoff/phase1_drift_map.md` + `handoff/phase3_final_report.md`.
- "What's the inventory snapshot?" → `PROJECT-INVENTORY.md`.
