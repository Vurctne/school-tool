# Round 37 — Friendly errors for missing inputs

**Date:** 2026-05-07

---

## User report

Sub-Program Budget Report, click Generate without picking the source
file:

```
WHAT WENT WRONG
The tool hit an error we don't have a specific message for yet.
The technical detail is in the log below.

HOW TO FIX IT
Try running the tool again.  If the same error comes back, send a
screenshot of this screen plus the log to feedback@schooltool.com.au …

TECHNICAL DETAIL (for support)
KeyError: 'report_file'
```

User feedback: "这是一个很明显的没有选择source file的错误…直接告诉用户怎么解决，
而不是让用户联系 support" — this is an obviously-missing-file error;
just tell users how to fix it, don't make them email support.

---

## Fix

`toolkit/user_errors.py::friendly_error` gained a rule for `KeyError`
exceptions whose argument is one of the tools' input keys. The rule
matches before the generic fallback, so missing-input errors now
produce a "fill in X first" message instead of "send a screenshot to
support".

The rule maps each known input key to a human-readable label:

```python
_INPUT_KEY_LABELS: dict[str, str] = {
    # Sub-Program
    "report_file": "Sub-Program report (the CASES21 GL21157 PDF or XLSX)",
    "comments_file": "prior-period comments file (optional)",
    # HYIA
    "sin": "SIN", "amount": "transfer amount", "date": "transfer date",
    # Master Budget
    "expense_file": "Compass Expense file",
    "master_file": "Master Budget template (or Master Budget A in Compare mode)",
    "master_file_b": "Master Budget B",
    # Operating Statement
    "current_file": "current-period operating statement PDF",
    "prior_file": "prior-period operating statement PDF",
    # SRP
    "indicative_pdf": "Indicative SRP PDF",
    "confirmed_pdf": "Confirmed SRP PDF",
    "revised1_pdf": "1st Revised SRP PDF",
    "revised2_pdf": "2nd Revised SRP PDF",
}
```

Add a new entry whenever a tool gets a new required input. If no
match is found the rule falls back to using the raw key name in the
message — still better than the generic "email support" advice.

### Example output (Sub-Program, no source file picked)

```
WHAT WENT WRONG
This tool needs the Sub-Program report (the CASES21 GL21157 PDF or
XLSX) before it can run.  The field is empty right now, so there's
nothing to process.

HOW TO FIX IT
Fill in the 'Sub-Program report (the CASES21 GL21157 PDF or XLSX)'
field above (Browse for a file, or type a value, depending on the
field), then click the primary button again.

TECHNICAL DETAIL (for support)
KeyError: 'report_file'
```

The technical line is preserved so support still has the original
error if a user does email it.

---

## How the existing tools wire to this

| Tool | run() error path | Now produces friendly message? |
| --- | --- | --- |
| Sub-Program Budget Report | inline `try: … except: friendly_error(exc)` | ✓ via the new rule |
| HYIA Transfer Code | no try/except — exception bubbles to `_on_tool_complete` which calls `friendly_error` | ✓ via the same rule |
| Master Budget Compass Autofill | `_run_autofill / _run_compare` → `_error_result(exc)` → `friendly_error` | ✓ |
| Operating Statement | inline `try: … except: friendly_error(exc)` | ✓ |
| SRP Comparison | uses `paths.get(key) or ""` so no KeyError; explicit "Please pick at least 2" check | already friendly (unchanged) |
| Refined PAL Search | no required inputs | n/a |

So the fix lands universally — every tool that previously surfaced a
"send a screenshot" message for a missing-input error now surfaces a
specific "fill in X first" message instead.

---

## Files touched

```
MOD   toolkit/user_errors.py
       - new _INPUT_KEY_LABELS map
       - new KeyError rule (placed first in friendly_error so it wins
         over the generic fallback)
       - rule wording works for both file pickers and text/secret
         inputs ("Fill in" rather than "Pick the…")

MOD   tests/test_user_errors.py
       - new TestMissingInput class — 4 tests:
         test_known_key_uses_friendly_label
         test_unknown_key_falls_back_to_key_name
         test_master_budget_compass_key
         test_master_budget_b_key
```

No tool-side code changes — the friendly_error layer covers every
tool already calling `friendly_error(exc)` in their except blocks
(or implicitly via the shell's `_on_tool_complete`).

---

## Quality gates

```
ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 72 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 554 passed, 66 skipped (env), 1 warning
                           (was 550 — +4 from new TestMissingInput class)
```

---

## What to manually verify on Windows

1. Open Sub-Program Budget Report.
2. Click **Generate report** without picking a file.
3. The error panel should now say:
   * Banner: "Please fill in the Sub-Program report (the CASES21
     GL21157 PDF or XLSX) before running this tool."
   * Advice: "Fill in the 'Sub-Program report …' field above (Browse
     for a file, …), then click the primary button again."
   * The "send a screenshot to feedback@schooltool.com.au" line is
     **gone**.
4. Same flow on HYIA with the SIN field empty — "Please fill in the
   SIN before running this tool."
5. Same flow on Master Budget Compass Autofill with no Compass file —
   "Please fill in the Compass Expense file before running this tool."

---

## Roll into the v2.2.2.0 hotfix

This change rolls cleanly into the same hotfix submission you're
about to ship. No new version bump needed beyond what `-StoreUpload`
already does:

```powershell
cd D:\Software\Productivity\Vic_School_Finance_Tools
pwsh msix\build_msix_package.ps1 -StoreUpload
```

Add this line to the v2.2.2.0 patch notes:

> • Friendlier errors when you click Generate without picking a file
>   — the tool now tells you which field to fill in instead of asking
>   you to email support.

---

## Files committed-side

```
MOD   toolkit/user_errors.py
MOD   tests/test_user_errors.py
ADD   handoff/round37_friendly_missing_input.md
```
