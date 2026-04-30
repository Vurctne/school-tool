# Round 20 — Plain-English error messages with solutions

**Date:** 2026-04-29
**Scope:** When something goes wrong, school business managers should see a
message they can act on — not a Python type name and stack-trace fragment.
This round adds a translator (`toolkit/user_errors.py`) and wires every
tool through it.

---

## Before / after

**Before** (cryptic — exposes Python internals):

```
An error occurred (ValueError): File not found:
C:\Users\ivan\Downloads\GL21150_Operating Statement Detailed.pdf
```

**After** (plain English + concrete next step):

```
Banner:  We couldn't find the file you selected.

Log:
WHAT WENT WRONG
  One of the files you picked is no longer at that location, or the
  path was changed since you selected it.

HOW TO FIX IT
  Open File Explorer and check the file is still where you expect.
  Then click the file picker in this tool again and re-select it.

TECHNICAL DETAIL (for support)
  ValueError: File not found: C:\Users\ivan\Downloads\GL21150…pdf
```

The original Python error is preserved at the bottom under "TECHNICAL
DETAIL (for support)" so we can still triage if the user emails us, but
it's no longer the primary surface area.

---

## What changed

### New module — `toolkit/user_errors.py`

A `friendly_error(exc) -> FriendlyError` function that translates an
exception into four parts:

| Field | Audience | Example |
| --- | --- | --- |
| `banner` | User (one-line danger banner) | "We couldn't find the file you selected." |
| `message` | User (1-2 sentence body) | "One of the files you picked is no longer at that location…" |
| `advice` | User (concrete next step) | "Open File Explorer and check…" |
| `technical` | Support staff | "ValueError: File not found: …" |

The translator covers the failure modes we've actually seen during
testing:

| Rule | Match | Banner |
| --- | --- | --- |
| File not found | `FileNotFoundError` or `"File not found"` text | "We couldn't find the file you selected." |
| File locked / in use | `PermissionError` or `"being used by another process"` | "Windows wouldn't let us read or save that file." |
| PDF empty | `"PDF appears empty"` or `"no data rows found"` | "The PDF didn't contain any rows we could read." |
| PDF unreadable | `"Cannot read"` + `"PDF"` | "We couldn't read this PDF." |
| Number parse error | `"Cannot parse"` + (`"decimal"` or `"currency amount"`) | "We hit a number we couldn't read in your file." |
| Negative value | `"must be non-negative"` | "A value can't be negative." |
| Browser launch | `"Could not open the browser"` | "We couldn't open your default browser." |
| Excel COM retry | `"Excel retry loop"` | "Excel kept refusing our updates." |
| Anything else | (fallback) | "Something unexpected went wrong." |

Each rule includes a tailored `advice` line — usually pointing the user
at File Explorer, Adobe Reader, CASES21, or Windows Settings depending
on the failure mode.

### Tool frames now use the helper

`tools/operating/frame.py`, `tools/sub_program/frame.py`,
`tools/master_budget/frame.py`, `tools/srp/frame.py`, and
`tools/refined_pal_search/frame.py` all replaced this:

```python
except Exception as exc:
    return ToolResult(
        status="error",
        banner_level="danger",
        banner_text=(f"An error occurred ({type(exc).__name__}): {exc}"),
        log_lines=[
            LogLine("ERROR", tag="heading"),
            LogLine(f"{type(exc).__name__}: {exc}", tag="danger"),
            LogLine(tb, tag="danger"),
        ],
        ...
    )
```

with this:

```python
except Exception as exc:
    fe = friendly_error(exc)
    return ToolResult(
        status="error",
        banner_level="danger",
        banner_text=fe.banner,
        log_lines=[
            LogLine("WHAT WENT WRONG", tag="heading"),
            LogLine(fe.message, tag="danger"),
            LogLine("HOW TO FIX IT", tag="heading"),
            LogLine(fe.advice, tag="muted"),
            LogLine("TECHNICAL DETAIL (for support)", tag="heading"),
            LogLine(fe.technical, tag="muted"),
            LogLine(tb, tag="muted"),
        ],
        ...
    )
```

### Shell global exception handler (`toolkit/shell.py::_on_tool_complete`)

Uncaught exceptions that escape a tool's `run()` (rare — most are caught
inside the tool now) used to surface as just `f"Error: {exc}"`. They now
go through `friendly_error()` too, so even the worst-case "tool didn't
catch its own exception" path gives the user something actionable.

### SRP "fewer than 2 PDFs" message

Reworded to drop "files" / "comparison" jargon and added a HOW TO FIX IT
log entry pointing the user at the four file pickers by name.

### Refined PAL Search

Two warning/error messages reworded:

- **No default browser detected** — used to say "Could not detect a
  default browser. Please open this URL manually: …".  Now says
  "No default browser is set up on this PC." with a multi-line log
  walking the user through Windows Settings → Apps → Default apps.
- **Browser launch raised** — used to expose the Python exception name
  in the banner.  Now goes through the browser-launch rule in
  `friendly_error` and surfaces "We couldn't open your default browser."
  with the same advice path.

---

## Files touched

```
NEW   toolkit/user_errors.py                                (211 lines)
NEW   tests/test_user_errors.py                             (152 lines, 17 tests)

MOD   toolkit/shell.py
       - _on_tool_complete uses friendly_error for uncaught exceptions

MOD   tools/operating/frame.py
       - import + use friendly_error in except block

MOD   tools/sub_program/frame.py
       - import + use friendly_error in except block

MOD   tools/master_budget/frame.py
       - import + use friendly_error (now binds `exc` instead of bare except)

MOD   tools/srp/frame.py
       - import + use friendly_error in except block
       - reworded "fewer than 2 PDFs" validation message

MOD   tools/refined_pal_search/frame.py
       - import + use friendly_error in except block
       - reworded "no default browser detected" warning

MOD   tools/refined_pal_search/tests/test_frame.py
       - updated assertions for new banner copy (URL now in log_lines)
```

---

## Quality gates

All green:

```
ruff format --check .   → 77 files already formatted
ruff check .             → All checks passed!
mypy --strict toolkit/ tools/ tests/  → no issues found in 70 source files
pytest                   → 456 passed, 66 skipped (excluding pre-existing
                            sub_program tkinter-stub pollution and
                            operating sample-PDF naming drift)
```

The test count increased by 17 (the new `test_user_errors.py` suite).

### Known pre-existing test-suite issues (not Round 20)

1. **`tools/sub_program/tests/test_frame.py`** stubs `sys.modules["tkinter"]`
   for its mock-based tests, which leaks into any subsequent test file
   that imports tkinter (test_shell_smoke, test_licence_gate). Running
   each file individually works fine; running both in the same pytest
   process produces ~20 collection errors. This was true before Round 20
   and is a separate cleanup task.
2. **`tools/operating/tests/test_logic.py`** looks for sample PDFs at
   `Samples/Operating Statement/GL21150_Operating Statement Detailed.pdf`
   but the folder only has `…Feb.pdf` and `…Mar.pdf`.  Pre-existing data
   drift; the Operating tool is parked under "In development" so the
   tests aren't on the critical path.

---

## Adding a new error rule

When you hit a new failure mode in the wild, add a rule to
`toolkit/user_errors.py::friendly_error`:

1. Find the exception text it raises (run the failure once to see).
2. Add a new `if "<phrase>" in lower:` block — order matters, more
   specific rules go first, the fallback stays at the end.
3. Write three things from the user's perspective:
   - **banner** — one line, no Python jargon, describes the problem.
   - **message** — 1-2 sentences explaining *what* and *why*.
   - **advice** — concrete steps the user can take (mention File
     Explorer / Excel / Adobe / CASES21 / Windows Settings by name).
4. Add a unit test in `tests/test_user_errors.py` matching the pattern
   of the existing classes (TestFileNotFound, TestPdfEmpty, etc.).

The "technical" field is auto-populated from `type(exc).__name__: str(exc)`,
so support staff always have the original error to triage from.

---

## What did not change

- `logic.py` raise messages stay technical (e.g. `"File not found: …"`).
  The unit tests in `tools/*/tests/test_logic.py` rely on those exact
  strings, and the translator matches on those strings to pick a rule.
- The traceback is still appended to the log under the friendly text,
  for cases where support needs the full Python stack.
- Status string (`"error"` / `"warning"` / `"success"`) and banner level
  (`"danger"` / `"warning"` / `"ok"`) are unchanged — only the human-
  readable text moved.
