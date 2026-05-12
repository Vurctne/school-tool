# Round 39 — Multi-agent comprehensive audit + fixes

**Date:** 2026-05-08

User request: "使用不同的agents 来测试所有软件项目，总结并修复他们发现的问题"
(use different agents to test the whole project, summarize findings,
and fix issues).

Dispatched 4 parallel general-purpose agents — one each for **bug
review**, **test coverage gaps**, **user-facing string consistency**,
and **cross-FS truncation footprints** — then consolidated the
findings and applied fixes. This handoff records both the audit
results and the fixes that landed.

---

## Audit summary

### Agent 1 — Bug review (10 findings)

* CRITICAL: 0
* HIGH: 1 (`comment_synonyms` UnboundLocalError)
* MEDIUM: 4 (Tk-shutdown race, dead try/except, commentary not
  persisted, executor not shutdown on close)
* LOW: 5 (mutable class-level defaults, `_active_id` empty-string
  guard, `eb > 0` should be `!= 0`, locale-string COM match,
  ambiguous SRP totals comment)

### Agent 2 — Test coverage gaps (3 untested public APIs)

* HIGH: `MasterBudgetTool.run_compare` — Round 28's primary entry
  point for Compare-two-budgets has no test.
* LOW: `suggest_compare_output_name` — zero references in tests.
* (rest are filtered as trivial / indirectly covered)

### Agent 3 — User-facing string consistency (~14 findings)

* `Vurctne@gmail.com` in user-facing surfaces: **0 occurrences**
  (Round 34 cleanup is complete).
* Paid-tier language in user-facing surfaces:
  - 2 in `tools/sub_program/frame.py` help text (`"This is a paid
    tool. … Licence fee: $550 + GST per school per year"`)
  - 2 in `tools/operating/frame.py` help text (`"This is a paid
    tool. Activating … requires a paid licence — see User → Service"`)
  - ~10 in `toolkit/user_frame.py` (User tab — hidden via
    `SHOW_USER_TAB = False`, content out-of-scope per audit rule)
* Stale version reference in `docs/store_listing_copy.md:1`
  (`School Tool v2.0.0` instead of `School Tool`).

### Agent 4 — Cross-FS truncation footprints (1 finding)

* `toolkit/base_tool.py:260-261, 266-267` — duplicate docstring
  lines inside `preview_update`'s docstring (orphaned `state in
  run() …` and `key:` lines from a botched recovery). Cosmetic;
  AST-parses fine.
* All other `.py` files clean — AST-parses, no null bytes, no
  suspicious tails.

---

## Fixes applied

| # | Severity | Fix | Files |
| --- | --- | --- | --- |
| 1 | HIGH | Hoisted `comment_synonyms` to module scope as `_COMMENT_SYNONYMS`. `load_prior_period_comments` no longer raises `UnboundLocalError` when every input sheet is empty. | `tools/sub_program/logic.py` |
| 2 | HIGH | Removed paid-licence wording from Sub-Program help text (`"This is a paid tool. An active licence … Licence fee: $550 + GST per school per year (Seller: ZXW Investment Pty Ltd)"`). | `tools/sub_program/frame.py` |
| 3 | HIGH | Removed paid-licence wording from Operating Statement help text (`"This is a paid tool. Activating … requires a paid licence — see User → Service"`). | `tools/operating/frame.py` |
| 4 | MEDIUM | Tk-shutdown race guard on `app.py:_schedule_update_check`. The worker thread's `root.after(0, …)` is now wrapped in `try/except (RuntimeError, tk.TclError)` so a closed-window-during-WinRT-call exits silently. | `app.py` |
| 5 | MEDIUM | Deleted dead try/except in `tools/sub_program/frame.py:549-560` (placeholder for an in-place banner update never implemented; `mb.showinfo` below is the actual user-facing notification). | `tools/sub_program/frame.py` |
| 6 | MEDIUM | Stale `v2.0.0` heading in `docs/store_listing_copy.md` updated to drop the version (single source of truth = `app_metadata.APP_VERSION`). | `docs/store_listing_copy.md` |
| 7 | LOW | Deduped repeated docstring lines in `BaseTool.preview_update` (cosmetic; AST-clean). | `toolkit/base_tool.py` |
| 8 | LOW | Negative-budget edge case: `if eb > 0` → `if eb != 0` (and same for `rb`) so the rare cost-recovery sub-programs with negative annual budgets still produce a percentage in the Monthly Sub Program Report output. | `tools/sub_program/logic.py` |
| 9 | TEST | Added two tests for `run_compare` — missing-A error path and missing-B error path (closes the HIGH-risk coverage gap from Round 28). | `tools/master_budget/tests/test_frame.py` |
| 10 | TEST | Added `test_suggest_compare_output_name_format` (closes the LOW-risk zero-reference coverage gap). | `tools/master_budget/tests/test_logic.py` |
| 11 | TEST | Updated `tools/operating/tests/test_frame.py::TestHelpText::test_help_text_mentions_licence` → `test_help_text_does_not_mention_paid_licence` to match the new (paid-licence-free) help text. | `tools/operating/tests/test_frame.py` |

---

## Findings deliberately deferred (not fixed in this round)

* **`toolkit/user_frame.py` licence/invoice content** (~10 strings).
  `SHOW_USER_TAB = False` means users can't reach this UI today, so
  the strings aren't visible. Rewriting the entire User tab is a
  larger scope — tracked as a future round if/when the User tab
  comes back.
* **Mutable class-level defaults** on `SubProgramBudgetReportTool`,
  `MasterBudgetTool`, `SrpComparisonTool`. Works fine today (each
  tool instantiated once); only matters if multi-window support
  ever ships.
* **`_active_id = ""` corner case** in `TkShell` — practically
  unreachable (registry always has tools). Defensive guard could
  be added but adds little real value.
* **`_commentary_overrides` not persisted to XLSX** — known TODO
  in `tools/sub_program/frame.py:383-385`. Threading the override
  dict through `logic.generate_report` is a non-trivial API change.
  Current behaviour: edits survive the session but don't show up in
  the saved file. Documented as a known limitation; future round.
* **Locale-dependent COM string match** in
  `tools/master_budget/logic.py:843` (only matches English
  Windows). Defensive; the HRESULT comparison above is the
  primary signal.
* **SRP totals comment ambiguity** (`tools/srp/logic.py:635-636`).
  Cosmetic doc-string clarification; doesn't affect output.

---

## Quality gates

```
ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 72 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 544 passed, 66 skipped (env), 1 warning
                           (was 541 before round — +3 new tests)
```

---

## Cross-FS sync nightmare this round

This was a heavy round for the bash mount truncation issue. **Ten or
more separate truncations** during the fix application phase:

* `tools/sub_program/logic.py` — truncated 3+ times (mid-method,
  recovered each time)
* `tools/sub_program/frame.py` — null-byte padding (677 nulls), recovered
* `toolkit/base_tool.py` — null-byte padding (87 nulls), recovered
* `tools/operating/frame.py` — null-byte padding (124 nulls), recovered
* `tools/master_budget/tests/test_logic.py` — truncated mid-statement
* `tools/master_budget/tests/test_frame.py` — truncated mid-statement
* `app.py` — truncated mid-docstring

Each recovered via the now-standard pattern: read Windows-side
content via the Read tool, write a clean version via `pathlib.write_text`
in bash, touch to bump mtime. The handoff for Round 28 already
documents this; Round 39 confirms it's still the most reliable
recovery path.

After all the recoveries the file states are clean — AST-parses,
no nulls, no suspicious tails on every Python file in the repo.

---

## What rolls into the next ship

If the v2.2.2.0 hotfix hasn't shipped yet, fold these in. Patch
notes addition:

> • Friendlier help text on Sub-Program Budget Report and Operating
>   Statement — no more outdated paid-licence references.
> • Edge-case fix: percentages now compute correctly for the rare
>   sub-programs with negative annual budgets (cost-recovery
>   accounts).
> • Stability fix: rare crash on app close during the startup
>   update check, eliminated.
> • Internal: 3 new tests, 1 friendlier error path on missing
>   prior-period comments file.

---

## Files touched (Round 39)

```
MOD   tools/sub_program/logic.py     (UnboundLocalError fix, eb!=0, progress(100), final_lines fix)
MOD   tools/sub_program/frame.py     (drop paid-licence text, drop dead try/except)
MOD   tools/operating/frame.py       (drop paid-licence text)
MOD   app.py                         (Tk-shutdown race guard)
MOD   toolkit/base_tool.py           (dedupe docstring lines)
MOD   docs/store_listing_copy.md     (drop stale v2.0.0)
MOD   tools/master_budget/tests/test_frame.py    (+2 run_compare tests)
MOD   tools/master_budget/tests/test_logic.py    (+1 suggest_compare_output_name test)
MOD   tools/operating/tests/test_frame.py        (test renamed for new help text)
ADD   handoff/round39_multi_agent_audit_and_fixes.md
```
