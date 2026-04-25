# CONTEXT-SUMMARY.md

**Purpose:** front-loaded context every sub-agent (Sonnet 4.6) receives via its prompt template. Designed so a sub-agent can act correctly on a scoped task **without reading the full repo or `docs/`**. If you (sub-agent) need detail beyond what's here, the orchestrator (Opus 4.7) will quote it into your task brief. Do not autonomously read files outside your task scope — your concurrency budget is small and your context window is tighter than the orchestrator's.

**Last updated:** 2026-04-25.

---

## 1. What this project is

**School Tool v2.0.0** — a multi-tool Windows desktop application for Victorian Government school business managers, shipped as an MSIX through the Microsoft Store. Three tools at v2.0.0 launch:

| Tool | Tier |
| --- | --- |
| HYIA Transfer Code Generator | Free |
| Master Budget Compass Autofill | Free |
| Sub-Program Budget Report | Paid ($550 + GST/year/school) |

Plus a Cloudflare Workers backend for registration, invoicing, and licensing.

Publisher: **Vurctne**. Legal seller on invoices: **ZXW Investment Pty Ltd** (ABN TBD). Support: `Vurctne@gmail.com`.

---

## 2. Stack

**Desktop (Python):** Python 3.12 x64, Tkinter (vista theme), openpyxl, pdfplumber, pywin32 (Win32 COM for macro-preserving Excel writes), WeasyPrint (PDF). PyInstaller-frozen, MSIX-packaged.

**Backend (TypeScript):** Hono on Cloudflare Workers. D1 (SQLite) for app data. R2 for object storage (invoice PDFs, PO uploads). Cloudflare Queues for OCR jobs. Workers AI for OCR inference. Resend for transactional email. Argon2id passwords (via `hash-wasm`). HS256 JWT user sessions; admin password + TOTP. Ed25519 for licence token signing.

**Build:** `.github/workflows/build.yml` (Python lint + type + test) and `backend.yml` (vitest). MSIX built via `msix/build_msix_package.ps1` + vendored `.tools/msixsdk/`.

---

## 3. Quality gates — all four must pass

1. `ruff format --check .`
2. `ruff check .`
3. `mypy --strict .`
4. `pytest`

Plus on backend: `cd backend && pnpm run check && pnpm run test`.

CI enforces these. Don't merge red.

---

## 4. Code conventions (non-negotiable)

- **Every Python file** starts with `from __future__ import annotations`.
- **Sentence case** for all UI button labels (`Generate budget workbook`, NOT `Generate Budget Workbook`).
- **Australian English** spelling and punctuation. No emoji in code or UI copy.
- **Unicode minus** `−` (U+2212) for negatives in user-facing text and PDF output. Never the ASCII hyphen `-`.
- **`$` prefix, no space**: `$1,234.56`. Two decimal places in reconciliation views; whole dollars in Council summaries / metric cards. Banker's rounding.
- **Tabular figures everywhere** for numeric columns (Cascadia Mono primary, Consolas fallback; `font-variant-numeric: tabular-nums` on web).
- **Colour is never the only signal** — negatives are red AND have a minus; over-budget rows are pink-filled AND show >100% used.

---

## 5. Frozen surfaces — touch only with explicit orchestrator authorisation

These are locked by ADR-0014 (`docs/02_ARCHITECTURE.md`). A sub-agent that would change any of them must **escalate to orchestrator first** rather than just doing it:

- Window chrome, title bar, status bar layout
- Left rail (220 px width, `#3399FF` selected colour, focus ring `rgba(43,124,184,.35)`)
- 4 px spacing grid; 8-token type scale
- Colour tokens in `colors_and_type.css` (and `toolkit/tokens.py` which is auto-generated from it)
- The `BaseTool` contract (ADR-0004)

**Highlight colour semantics are also frozen** (no new highlight colours without changing the CSS first):
- pink (`HL_MISMATCH = F4CCCC`) = over-budget / mismatch
- green (`HL_SOURCE_ONLY = E2F0D9`) = source-only inserted row
- yellow (`HL_EDITED = FFF2CC`) = legend-only ghost constant; **no fill site applies it today** (defined for instruction-text legend completeness; do not invent fills against it without orchestrator OK)

---

## 6. The `BaseTool` contract (ADR-0004)

Every desktop tool is a class with the following surface, and the shell renders the UI from these declarations. **Never put shell-aware code inside a tool**; if a tool needs something the shell doesn't provide, extend `BaseTool` / `toolkit/shell.py`, not the tool.

```python
class BaseTool(Protocol):
    id: str             # kebab-case
    group: str          # "Banking" | "Budget" | "Reconciliation"
    label: str
    short: str          # 2-letter mark
    order: int
    inputs: list[InputSpec]   # FileInput | TextInput | NumberInput | CurrencyInput | DateInput | SecretInput
    output: OutputSpec | None
    primary_button: str
    pdf_template: str | None
    pdf_body: str | None

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult: ...
    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]: ...
```

`run()` is **pure**: takes resolved input values, returns a `ToolResult`. Must not touch Tk, the shell, or the registry. Exceptions inside `run()` get caught at the boundary and rendered as a `ToolResult(status="error", banner_level="danger", ...)`.

**Registration** — one line in `toolkit/registry.py`. Adding a tool should not touch the shell, the installer, or the build script.

---

## 7. Where things live

```
app.py                       — entrypoint
app_metadata.py              — APP_NAME, APP_VERSION ("2.0.0"), SUPPORT_EMAIL, API_BASE_URL, LICENCE_PUBLIC_KEY
toolkit/                     — shell, primitives, base_tool, registry, tokens (AUTO-GEN), fills, fonts, logging,
                               account, api_client, licence, user_frame, crypto_win
tools/<id>/                  — frame.py + logic.py + tests/{test_frame,test_logic,test_integration}.py
                               + __init__.py that calls `register(<ToolClass>)`
tests/                       — toolkit-level + drift guards
backend/                     — TypeScript Cloudflare Worker (Hono routes, D1 migrations, lib helpers, vitest)
scripts/port_tokens.py       — regenerates toolkit/tokens.py from colors_and_type.css
docs/01_REQUIREMENTS.md      — canonical product/tool spec
docs/02_ARCHITECTURE.md      — 14 ADRs
docs/03_ROADMAP.md           — 8 milestones M1-M8
docs/04_BACKEND_DESIGN.md    — REST API + D1 schema + admin actions
design_system/               — read-only design reference (DO NOT EDIT)
handoff/                     — previous-round handoff docs (active reference)
_archive/                    — quarantined cruft (DO NOT READ for context)
```

**`toolkit/tokens.py` is auto-generated.** Header line says `# AUTO-GENERATED — DO NOT EDIT BY HAND. Run scripts/port_tokens.py.` `tests/test_tokens_drift.py::test_tokens_not_drifted` runs `python scripts/port_tokens.py --check` and fails CI on drift. To change a colour: edit `colors_and_type.css`, run the script, commit both files together.

**`toolkit/fills.py`** is the helper module that converts a 6-char `HL_*` hex into the encoding a specific renderer needs:
- `argb(hex_rgb) -> str` for openpyxl `PatternFill(fgColor=...)` — prepends `"FF"` alpha
- `bgr_int(hex_rgb) -> int` for Win32 COM `.Interior.Color` — `BB << 16 | GG << 8 | RR`

Three drift guards in `tests/test_tokens_drift.py`:
1. `test_tokens_not_drifted` — Python ↔ CSS sync.
2. `test_no_rogue_hex_in_tool_strings` — every `#RRGGBB` in any string literal under `tools/**/*.py` (excluding test files) must equal one of the canonical `HL_*` values.
3. `test_pattern_fill_colours_are_canonical` — every `PatternFill(fgColor=...)` in `tools/` must derive from `argb(<HL_*>)` or be a canonical ARGB literal.

---

## 8. Privacy & licensing posture

- **Free tools** (HYIA, Master Budget) are 100% offline. Zero server calls. Tool file contents never leave disk. Preserve this.
- **Paid tools** (Sub-Program) do **one** server hit per year at activation, then fully offline. The licence file is at `%LOCALAPPDATA%\Packages\<MSIX-family>\LocalCache\licence.json`, signed Ed25519, public key embedded in the desktop binary.
- **Server collects the minimum**: email, school + ABN, PO content + original PDF, device id, app version, IP. Tool input/output file contents NEVER touch the server.
- **DPAPI** (`win32crypt.CryptProtectData`) is used for any locally-encrypted secret (HYIA "Remember SIN", account.dat). Only the same Windows user on the same machine can decrypt.

---

## 9. Cowork sandbox — operational realities

If a sub-agent runs commands via `mcp__workspace__bash`, these constraints apply:

- **Cannot delete files** (`rm: Operation not permitted` on the project mount, even on freshly-touched files). Use Read/Edit/Write for content changes; for actual deletes the orchestrator hands a PowerShell command to Ivan or invokes `mcp__cowork__allow_cowork_file_delete` per file.
- **Cannot run git** for the same reason — `git config` / `add` / `commit` all require unlinking lock or temp files. Sub-agents must NOT run any git command. The orchestrator handles version control by handing PowerShell command lists to Ivan.
- **`/tmp` works normally** — bash sandbox mount is unrestricted there. Use it for scratch artifacts; copy results back via Write.
- **Cross-FS sync lag** — the Linux mount can briefly disagree with the Windows-side Read-tool view of a recently-edited file. If `ast.parse(path.read_text())` fails with `SyntaxError` at line numbers Read says don't exist, force convergence with `pathlib.Path(p).write_text(p.read_text())`.
- **No network fetches** unless your task brief explicitly authorises it. Default is local-only work.

---

## 10. Dispatch rules — what you (sub-agent) may and may not do

**You MAY:**
- Read files within your task scope.
- Write/Edit files explicitly listed in your task brief.
- Run `pytest`, `pnpm run test`, `ruff`, `mypy` against your changes (read the output, don't fix flakiness).
- Return structured markdown reports / unified diffs / verification command outputs.

**You MUST NOT:**
- Touch any file outside your task brief's "files to create/modify" list.
- Edit `toolkit/tokens.py` by hand (it's auto-generated from CSS).
- Edit `design_system/` (read-only design reference).
- Touch any frozen surface (§5 above) without escalating.
- Run `git` commands (sandbox blocks them).
- Auto-fix test failures in run mode — return the failure log only; the orchestrator decides next steps.
- Make product, legal, financial, or branding decisions — escalate.
- Search for files / fetch URLs not in your brief unless the brief explicitly authorises it.

**If you discover scope creep is unavoidable** (e.g. the file you need to modify imports from a file outside your scope and that import needs updating), return a **scope expansion request** instead of acting. Format: a one-paragraph description of (a) what you discovered, (b) what minimal scope expansion would unblock you, (c) the risk if expansion is declined.

**Failure rule:** orchestrator gives you one re-dispatch on the same scope if your first return is unsatisfactory. After two failures, the orchestrator escalates to Ivan rather than auto-retrying you.

---

## 11. Where to find more (orchestrator's responsibility, not yours)

If the orchestrator's task brief is unclear, escalate before guessing. The orchestrator has:
- `PROJECT-INVENTORY.md` — current-state snapshot
- `ORCHESTRATION-PLAN.md` — phase plan + your role's full prompt template
- `ORCHESTRATION-STATUS.md` — live status, your dispatch ID
- `CLAUDE.md` — gotchas and tribal knowledge
- The `docs/01_REQUIREMENTS.md` / `docs/02_ARCHITECTURE.md` / `docs/03_ROADMAP.md` / `docs/04_BACKEND_DESIGN.md` documents for canonical detail
- The `design_system/design_handoff_school_finance_toolkit/` folder for visual specs
- `handoff/phase1_drift_map.md` + `handoff/phase3_final_report.md` for the previous round's highlight-colour alignment work

You receive only what you need from these.
