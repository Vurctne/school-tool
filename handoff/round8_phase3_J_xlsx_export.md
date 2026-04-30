# Round 8 Phase 3 J — Sub-Program XLSX export rewrite

**Date:** 2026-04-26 / 27
**Orchestrator:** Opus 4.7
**Builder:** Sonnet 4.6 (Agent J, ~162K tokens, 108 tool uses, ~17 min) + orchestrator follow-up fix
**Quality gates:** all green (ruff format, ruff check, mypy --strict, pytest 425/30/0)

---

## What changed

The Sub-Program tool's XLSX export was rewritten end-to-end to match the user's reference file
`Annual sub program budget Report Jan26.xlsx`. The in-app rendering (faculty rail, result table
with pink over-budget rows) is **unchanged** — only the exported workbook differs.

### New XLSX structure

**Two sheets** instead of one:

| Sheet | Cols | Frozen | Contents |
|---|---|---|---|
| `Revenue` | 8 | A3 | Sub Prog. / Title / Last year actual / Last year budget / Annual budget / YTD / % Budget received / Comments |
| `Expenditure` | **9** (Outstanding Orders dropped per Q3) | A3 | + Uncommitted Balance (= Annual − YTD − Outstanding) instead of Outstanding+Uncommitted pair |

- Row 1: merged across all columns, **bold size 14**, e.g. `"Annual Sub-Program Budget Report - March 2026 Revenue"`
- Row 2: column headers
- Row 3+: data rows
- **No fills** — pink over-budget row highlight removed entirely from the XLSX (replaced by data bars)
- Currency format `_-"$"* #,##0_-;\-"$"* #,##0_-;_-"$"* "-"??_-;_-@_-` on Annual budget + YTD (matches Jan26)
- Number format `0.00` on the % Budget column
- **Green data bar** conditional formatting on G3:G{N} — color `#FF63C384`, scale 0–110 (matches Jan26)
- Plus a `cellIs > 110` conditional formatting rule (also from Jan26)

### Q1–Q5 resolutions applied

| Q | User answer | Implementation |
|---|---|---|
| Q1 — last-year actual + budget | "GL21157 has these columns already" | Parser extracts from `pre[-4]` and `pre[-3]` (positions left of the % column in the PDF token sequence) |
| Q2 — outstanding orders | "in the GL21157 PDF" | Parser extracts from `post[0]` when `len(post) >= 2`; defaults to 0 on Revenue lines |
| Q3 — don't show Outstanding Orders | (display constraint) | Column dropped from `_EXP_HEADERS`; data still parsed and used internally for Uncommitted Balance computation |
| Q4 — date range will be in PDF | (extract from PDF) | Regex `r'\d{1,2}\s+([A-Z][a-z]+\s+\d{4})\s+\d{2}:\d{2}\s+\d+\s+\[GL'` against page text; the PDF footer pattern `3 March 2026 13:37 1 [GL21157]` yields `"March 2026"` |
| Q5 — show bars for each row for % budget | (data bars) | `DataBarRule` color `#FF63C384`, scale 0–110, with `cellIs > 110` second rule |

---

## Files changed

| File | Net Δ | What |
|---|---|---|
| `tools/sub_program/logic.py` | +488 / -~80 | 3 new `SubProgramLine` fields (`last_year_actual`, `last_year_budget`, `outstanding_orders`, all default `Decimal("0")`); 1 new `ReportSummary` field (`period_label: str = ""`); PDF parser extends `pre[]` indexing for last-year cols + handles `post[]` for outstanding orders; period regex; full `_write_xlsx` rewrite into `_write_sheet` + Revenue/Expenditure helpers |
| `tools/sub_program/tests/test_logic.py` | +341 | 31 new tests; 4 existing tests rewritten for new XLSX structure; sheet headers + currency/percent formats + frozen panes + Uncommitted Balance + period title + conditional formatting all covered |
| `tools/sub_program/tests/test_frame.py` | unchanged | `_make_summary` and `_make_line` use only required fields; new SubProgramLine fields have defaults so it compiles unchanged |

---

## Quality gates (final)

```
ruff format --check ........ 63 files already formatted
ruff check ................. All checks passed!
mypy --strict .............. Success: no issues found in 63 source files
pytest tests/ tools/ ....... 425 passed, 30 skipped, 0 failed
port_tokens.py --check ..... OK: tokens.py in sync with CSS
```

30 skips break down to expected env-absent skips (Tk on Linux CI, pywin32 Windows-only).

---

## Off-spec deviation caught + fixed

Agent J's first pass kept "Outstanding Orders" as a displayed column on the Expenditure sheet
(10 cols total), but Q3 explicitly said "don't show Outstanding Orders". Orchestrator inline-fixed:

1. Removed `"Outstanding Orders"` from `_EXP_HEADERS` (now 9 cols, not 10)
2. Removed the corresponding entry from `_EXP_WIDTHS`
3. Removed the `float(line.outstanding_orders)` from the row_values list in the Expenditure path
4. Updated `test_expenditure_sheet_columns` to assert `"Outstanding Orders" not in headers` (was: `in headers`)
5. Updated `test_uncommitted_balance_computed_correctly` to read col 8 (was col 9)
6. Outstanding Orders is still parsed from the PDF — it's only the *display* that's suppressed.
   The Uncommitted Balance computation (`Annual − YTD − Outstanding`) still uses it.

---

## Cross-FS sync issue (CLAUDE.md gotcha) — encountered again

While running quality gates, both `tools/sub_program/logic.py` and
`tools/sub_program/tests/test_logic.py` showed mid-statement truncation on the bash mount
(unclosed `(` errors at lines 832 and 849 respectively). Windows-side Read view was complete
and correct. Fix: appended the known-good tail to each file via Python heredoc, then `touch`-ed
to force Python's import machinery to re-parse. Same workaround as Round 8 Phase 3 G — already
documented in CLAUDE.md gotchas.

---

## What the user will see when they next run the tool

1. Restart School Tool to pick up the code change.
2. Open Sub-Program Budget Report from the left rail (paid feature, licence still active until
   2027-04-26).
3. Pick a CASES21 GL21157 PDF (Jan26 / March26 / etc.) and click Generate report.
4. **The output workbook now opens with two sheets**:
   - `Revenue`: 8 columns, $-formatted Annual budget + YTD, green data bar on % Budget received,
     no pink highlights, frozen at A3.
   - `Expenditure`: 9 columns (no Outstanding Orders shown), Uncommitted Balance computed
     automatically, same formatting, same data bar.
5. Title row at top of each sheet: `"Annual Sub-Program Budget Report - {PeriodFromPDF} Revenue"` or
   `"... Expenditure"`. Period parsed from the PDF footer date stamp.
6. The in-app result panel still shows the original 7-col table with pink over-budget rows + the
   220 px faculty rail — unchanged. The visual mismatch between in-app (pink rows) and exported
   workbook (data bars) is intentional: in-app gets density, the exported workbook is council-ready.

---

## Pending items

- **Phase 3 H** — shell-level Clear button convention (still in design-decision purgatory)
- **Phase 3 I** — click-to-filter wiring on the faculty rail (rail row click → filter table)
- **Mailer FROM** — still using gmail.com which Resend rejects; manual `/verify-email` curl
  needed for any new test accounts
- **Argon2 in Workers** — currently falling back to PBKDF2-100k (security degraded but acceptable
  for pilot)
- The CLAUDE.md gotcha about bash-mount tail truncation is now hitting us repeatedly during
  Phase 3 dispatches — worth investing in a defensive script (e.g. a post-write verifier that
  hashes the file and refuses to proceed on mismatch)
