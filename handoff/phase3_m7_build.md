# Phase 3 (renumbered) Handoff — M7 Build: SRP Comparison + Operating Statement

**Started:** 2026-04-26 06:00 UTC
**Finished:** 2026-04-26 08:00 UTC
**Orchestrator:** Opus 4.7
**Sub-agents dispatched:** 4 (1 Discovery, 2 Implementer parallel, 1 Code-reviewer)

This is the **renumbered** Phase 3. The original Phase 3 (M4 build — invoice PDF + admin dashboard) was paused due to Ivan's strategic pivot to credit-based pricing; see `handoff/phase3_paused_m4_research.md` for the disco-2 architecture research that informs the eventual M4 resume. After M7 (this handoff) and M8 (next phase, blocked on Camps samples), M4 resumes as new Phase 5.

---

## Headline

Two new tools shipped: SRP Comparison (free, Budget group, M7-a) and Operating Statement (paid, Reconciliation group, M7-b). Both are PDF-input → XLSX-output tools that mirror the structure of Sub-Program Budget Report. The desktop registry now exposes **5 tools**:

```
Banking         · HYIA Transfer Code           (free, M1)
Budget          · Master Budget Compass Autofill (free, M3-a)
Budget          · SRP Comparison                (free, M7-a)  ← new
Budget          · Sub-Program Budget Report     (paid, M3-b)
Reconciliation  · Operating Statement           (paid, M7-b)  ← new
```

**Quality gates final state:** ruff format clean (65 files), ruff check clean, mypy --strict clean (65 source files), pytest **383 passed** / 15 environmental skips / 0 failed. Test count growth this phase: 211 (Phase 2 close) → 383 (Phase 3 close) = +172 tests across the 2 new tools.

---

## Goal → Resolution

| Goal | Resolution | Test guard |
| --- | --- | --- |
| Parse Indicative + Confirmed SRP PDFs (`extract_tables()` path) | `tools/srp/logic.py:parse_srp_pdf` | 9 logic tests + integration tests against real samples |
| SRP diff with `(Ref, Description)` join key | `tools/srp/logic.py:compare_srp` — 5 categories: unchanged / increased / decreased / new_in_confirmed / removed | `test_ref_desc_join_key` (synthetic) + `test_ref15_multiplicity` (real PDF) + `test_all_five_categories_present` (strengthened during reviewer-3 round) |
| SRP free tool (no licence gate) | `SrpComparisonTool` has no `requires_feature` attr | `test_no_requires_feature` |
| SRP XLSX output with category-coloured rows | `argb(HL_MISMATCH)` for decreased/removed; `argb(HL_SOURCE_ONLY)` for increased/new_in_confirmed; `unchanged` no fill | `test_decreased_rows_have_pink_fill`, `test_increased_rows_have_green_fill`, etc. |
| Parse two GL21150 PDFs (text-line heuristic, no tables) | `tools/operating/logic.py:parse_opstat_pdf` — 5-digit GL codes + 9-token rows | `test_parse_yields_50plus_rows`, `test_section_assignment`, `test_subsection_tracking` |
| Operating Statement bare `-` = zero | `_parse_opstat_decimal()` extends sub_program's parse_decimal | `test_bare_hyphen_is_zero` |
| Period-over-period diff with dual `$/%` threshold | `compare_opstat()` applies `abs(movement) >= dollars OR abs(pct) >= pct_threshold` | `test_threshold_at_boundary`, `test_threshold_below_both`, `test_threshold_above_one_only` |
| Favourable/adverse highlighting per section direction map | REVENUE up = green; EXPENDITURE up = red; etc. | `test_revenue_up_is_favourable`, `test_expenditure_up_is_adverse` |
| Operating Statement paid (`requires_feature = "operating"`) | `OperatingStatementTool.requires_feature = "operating"` | `test_requires_feature` |
| All 4 quality gates green | ruff format / ruff check / mypy strict / pytest | runner verified manually by orchestrator |
| 1 reviewer-3 blocker fixed | `test_all_five_categories_present` strengthened — split OR-gate into 5 separate asserts | `pytest -k all_five` passes after fix |

---

## Files changed

12 new files + 2 orchestrator-touched existing files.

**New tool: SRP Comparison (`tools/srp/`)**
- `__init__.py` — registers `SrpComparisonTool`
- `frame.py` — `SrpComparisonTool(BaseTool)`, free tool, group=Budget, order=20, 2 FileInput inputs, `_HELP_TEXT` is f-string interpolating `HL_MISMATCH` + `HL_SOURCE_ONLY`
- `logic.py` — `parse_srp_pdf()` using pdfplumber `extract_tables()` (6 tables on p1 + 3 on p2 of sample); `compare_srp()` with `(Ref, Description)` join key; `generate_srp_comparison()` orchestrator; `_write_xlsx()` with `argb(HL_*)` row fills
- `tests/__init__.py` — empty package marker
- `tests/test_logic.py` — 39 logic tests
- `tests/test_frame.py` — frame conformance + integration

**New tool: Operating Statement (`tools/operating/`)**
- `__init__.py` — registers `OperatingStatementTool`
- `frame.py` — `OperatingStatementTool(BaseTool)`, paid tool, group=Reconciliation, order=20, 4 inputs (2 FileInput + CurrencyInput threshold + NumberInput threshold), `requires_feature = "operating"`, `_HELP_TEXT` is f-string with HL_* interpolation
- `logic.py` — text-line heuristic parser (no table extraction); `_parse_opstat_decimal()` handles bare `-` as zero; section/sub-section context tracking; `compare_opstat()` with dual `$/%` threshold; favourable/adverse direction map (REVENUE vs EXPENDITURE)
- `tests/__init__.py` — empty
- `tests/test_logic.py` — logic tests (~50)
- `tests/test_frame.py` — frame conformance + integration

**Modified by orchestrator after both implementers finished:**
- `toolkit/registry.py` — added `import tools.operating` + `import tools.srp` lines (alphabetical with existing imports). Now 5 tool packages registered.
- `app_metadata.py` — wrapped over-long `LICENCE_PUBLIC_KEY` line into a separate comment + assignment (cosmetic; `ruff format` had flagged the original >100-char line as needing reformat).
- `tools/srp/tests/test_logic.py:test_all_five_categories_present` — split OR-gate into 5 separate asserts (per reviewer-3 blocker; strengthened test still passes).

**Untouched:**
- All other tool subtrees (`hyia`, `master_budget`, `sub_program`).
- `toolkit/tokens.py` (auto-generated).
- `backend/` — no backend changes this phase.
- `docs/01-05` — `docs/06_PRICING.md` already documents the credit pivot; specs in 01/04 still reference old pricing prose but won't be edited until Phase 5 (M4 resume).

---

## Sub-agent run log

| ID | Role | Files in scope | Result |
| --- | --- | --- | --- |
| disco-3 | Discovery | 4 sample PDFs (read via pdfplumber) + spec docs + sub_program reference impl | Structured 3-section report covering SRP parser strategy (`extract_tables` viable, 7 cols/row), OpStat parser strategy (no tables, text-line heuristic), shared concerns (`Samples/` is .gitignored, run implementers in parallel, don't extract toolkit/pdf_helpers yet). Critical finding surfaced: SRP `Ref` is NOT globally unique — Ref 15 appears for multiple Integration Student levels — join key must be `(Ref, Description)`. |
| imp-9 | Implementer | `tools/srp/{__init__,frame,logic,tests/}.py` | PASS — 80 tests; cross-FS sync hit, recovered. |
| imp-10 | Implementer | `tools/operating/{__init__,frame,logic,tests/}.py` | PASS — 82 tests; cross-FS sync hit on 3 files, recovered via bash heredoc. |
| reviewer-3 | Code-reviewer | All 12 new files + registry.py + app_metadata.py | 1 blocker (test_all_five_categories OR-gate) + 5 concerns + 5 suggestions. Acceptance: 9 MET + 1 PARTIAL (the blocker test). MEDIUM confidence. Orchestrator fixed the blocker inline (1 line edit, 1-minute work) rather than dispatching a Fixer. |

**runner-3 dispatch was skipped** — orchestrator ran all 4 quality gates manually after the test fix. This was a deliberate optimisation; the dispatch contract still works for future phases, just not always strictly necessary.

**Cross-FS sync events** hit imp-9, imp-10, AND the orchestrator's own Edit operations on `app_metadata.py` and `toolkit/registry.py`. Each was recovered. `app_metadata.py` had to be force-rewritten from bash with the full known-good content because the read-then-write workaround would persist the truncation. CLAUDE.md's gotcha about cross-FS divergence remains accurate; severity in this phase was higher than prior phases (orchestrator-side Edits were also affected, not just sub-agent Edits).

---

## Quality gates (final state)

| Gate | Command | Result |
| --- | --- | --- |
| 1 | `ruff format --check .` | PASS — 65 files already formatted |
| 2 | `ruff check .` | PASS — All checks passed! |
| 3 | `mypy --strict --cache-dir=/tmp/mypy_cache .` | PASS — Success: no issues found in 65 source files |
| 4 | `pytest tests/ tools/sub_program/tests/ tools/master_budget/tests/ tools/hyia/tests/ tools/srp/tests/ tools/operating/tests/` | PASS — 383 passed, 15 skipped (env), 1 pre-existing warning, 0 failed |

The 15 skips are environment-only (`tkinter` absent on Linux, `pywin32` Windows-only). The 1 warning is the pre-existing `ZipFile.__del__` resource warning in `test_integration.py`, present since Phase 1.

---

## Reviewer-3's concerns (non-blocking; deferred)

These are real but small. Document for future polish:

1. **`tools/srp/tests/test_logic.py:370-381` and `406-415`** — Fill verification reads from column 1 (Ref) which is technically fragile if any description string contains the same digit pattern. Low risk in SRP domain. Recommend: match on column 3 (Description) for uniqueness on next refactor.
2. **`tools/operating/tests/test_logic.py:424-425`** — `test_no_fill_for_unchanged_rows` uses `pytest.skip()` when all rows exceed threshold. Should be a hard assertion (matches the Phase 1 pattern of replacing pytest.skip with hard asserts in sub_program tests). **Add to a future polish phase queue.**
3. **`tools/srp/logic.py:267`** — Tolerance for `unchanged` is `abs(variance) < Decimal("0.01")` (strictly less than 1 cent). Design choice; document it explicitly in the function docstring.
4. **`tools/operating/frame.py:79`** — Help text mentions "see User → Service in the app" for licence activation, but that UI path is M4-paused. Forward-looking copy is technically wrong today. **Will become correct when Phase 5 (M4 with credits) ships.**
5. **`tools/srp/frame.py:85-89`** — Comment says "without leading #, as required by openpyxl fills" but the variables `_DECREASED_BG` / `_INCREASED_BG` carry `#` prefix and are used for Tkinter table `_bg`, not openpyxl. Misleading comment.

These are noted in `ORCHESTRATION-STATUS.md` as Phase-future polish items.

---

## What this phase deliberately did NOT do

- Did not touch `toolkit/registry.py` from the implementers (orchestrator handled the import additions after both finished, avoiding parallel-edit conflict).
- Did not extract a `toolkit/pdf_helpers.py` shared module (per disco-3 recommendation: rule of three — wait until a 3rd tool reuses the helpers).
- Did not commit sample PDFs to the repo (they're under `Samples/` which is `.gitignored` — real customer data).
- Did not implement the licence-activation UI path that the Operating Statement help text references — that's M4 work paused per `handoff/phase3_paused_m4_research.md`.
- Did not address the existing 5 reviewer-2 concerns from Phase 2 (those were Phase 3 polish queue; carry to next phase).
- Did not run runner-3 — orchestrator manually verified gates instead. Saved one dispatch (~30K tokens).

---

## What's next

Phase 3 (M7 build) is **done — awaiting Ivan sign-off**. Per `ORCHESTRATION-PLAN.md` §D.2, orchestrator does not dispatch the next phase until sign-off.

**New Phase 4 = M8 Camps Reconciliation** — currently **blocked on samples**. Per `docs/03_ROADMAP.md` "Known blockers" and `ORCHESTRATION-STATUS.md` "Pending decisions awaiting Ivan", the Camps register + supplier invoices + Sub-Program ledger sample exports are still TBD. When Ivan provides them:
- Three-way join logic
- Per-activity variance with Match / Minor / Open status
- 4-metric strip (Activities · Students · Reconciled · Unreconciled)
- Same paid-tool licence gate pattern as Sub-Program / Operating Statement

If Ivan elects to skip M8 and jump to **Phase 5 = M4 build with credit pricing**, that's also viable. Phase 5's brief will need a fresh design pass on top of disco-2's research because the credit model changes the invoice template, the DB schema (new `credit_purchases` + `credit_redemptions` tables, `schools.credits_balance` column), and the User → Service UI contracts. See `docs/06_PRICING.md` §9 (migration notes) for the canonical change list.

---

## Pending Ivan-side actions

None required for Phase 3 ship. Phase 5 (M4 resume) will trigger:
- Decision on Workers Paid Plan upgrade (vs `pdf-lib` fallback)
- Open questions in `docs/06_PRICING.md §8` (5 design questions about discount tiers, first-purchase incentive, refund policy, etc.)
- Seller bank details + ABN + registered address
- Resend domain DKIM / SPF setup if branded emails desired pre-Store-launch
