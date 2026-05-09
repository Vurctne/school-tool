"""Plain-English error translator.

The tools below are used by school business managers, not developers. When
something goes wrong we want to surface a message they can act on, not a
Python type name and stack-trace fragment.

Usage from a tool's ``except`` block:

    from toolkit.user_errors import friendly_error

    try:
        ...
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
            ],
            output_path=None,
        )

The ``technical`` string keeps the original Python error so support can
diagnose if needed; the ``banner`` and ``message`` + ``advice`` strings are
what the user sees most prominently.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FriendlyError:
    """Plain-English translation of a Python exception.

    Attributes
    ----------
    banner:
        One-line message for the danger banner. Self-contained — should make
        sense without reading the log.
    message:
        Plain-English description of what went wrong (1-2 sentences).
    advice:
        Concrete, actionable next step for the user.
    technical:
        Original ``type(exc).__name__: str(exc)`` — kept so support can
        reproduce the issue if the friendly message isn't enough.
    """

    banner: str
    message: str
    advice: str
    technical: str


# ---------------------------------------------------------------------------
# Phrase-matching rules
# ---------------------------------------------------------------------------
#
# Each rule is a (predicate, message, advice) triple.  We walk the rules in
# order and the first match wins.  ``predicate`` receives the lower-cased
# str(exc) plus the exception itself so it can match either text or type.
#
# When you add a new rule, prefer matching on the text (str(exc)) — it's
# stable across Python versions and our own raise sites.  Match on type
# only for "system-level" categories where the text isn't reliable, e.g.
# PermissionError when Excel has the file locked.
# ---------------------------------------------------------------------------


# Round 37 — Friendly labels for the file-picker keys each tool uses.
# When a tool's run() is invoked with one of these keys missing from the
# `paths` dict (i.e. the user clicked Generate without picking a file),
# Python raises ``KeyError: '<key>'``.  The translator below maps each
# key to the human-readable label shown next to its file picker.
#
# Add a new entry whenever a tool gets a new required FileInput.
_INPUT_KEY_LABELS: dict[str, str] = {
    # Sub-Program Budget Report
    "report_file": "Sub-Program report (the CASES21 GL21157 PDF or XLSX)",
    "comments_file": "prior-period comments file (optional)",
    # HYIA Transfer Code
    "sin": "SIN",
    "amount": "transfer amount",
    "date": "transfer date",
    # Master Budget Compass Autofill / Compare
    "expense_file": "Compass Expense file",
    "master_file": "Master Budget template (or Master Budget A in Compare mode)",
    "master_file_b": "Master Budget B",
    # Operating Statement
    "current_file": "current-period operating statement PDF",
    "prior_file": "prior-period operating statement PDF",
    # SRP Comparison
    "prev_year_revised_pdf": "Previous Year — Revised Budget PDF",
    "indicative_pdf": "Indicative Budget PDF",
    "confirmed_pdf": "Confirmed Budget PDF",
    "revised_pdf": "Revised Budget PDF",
}


def friendly_error(exc: Exception) -> FriendlyError:
    """Translate ``exc`` into a FriendlyError users can act on."""
    text = str(exc)
    lower = text.lower()
    technical = f"{type(exc).__name__}: {text}"

    # ----- Missing input field (Round 37) -------------------------------
    # ``KeyError`` raised by ``paths["foo"]`` when the user clicked the
    # primary button without filling in the "foo" field.  Surface a clear
    # "fill in X first" message instead of the support fallback.
    if isinstance(exc, KeyError):
        # KeyError stringifies its key with quotes — strip them.
        key = text.strip("'\"")
        label = _INPUT_KEY_LABELS.get(key, key)
        return FriendlyError(
            banner=f"Please fill in the {label} before running this tool.",
            message=(
                f"This tool needs the {label} before it can run.  The "
                "field is empty right now, so there's nothing to process."
            ),
            advice=(
                f"Fill in the '{label}' field above (Browse for a file, or "
                "type a value, depending on the field), then click the "
                "primary button again."
            ),
            technical=technical,
        )

    # ----- File system: not found ----------------------------------------
    if isinstance(exc, FileNotFoundError) or "file not found" in lower:
        return FriendlyError(
            banner="We couldn't find the file you selected.",
            message=(
                "One of the files you picked is no longer at that location, "
                "or the path was changed since you selected it."
            ),
            advice=(
                "Open File Explorer and check the file is still where you "
                "expect.  Then click the file picker in this tool again and "
                "re-select it."
            ),
            technical=technical,
        )

    # ----- File system: locked / in use ----------------------------------
    if isinstance(exc, PermissionError) or "being used by another process" in lower:
        return FriendlyError(
            banner="Windows wouldn't let us read or save that file.",
            message=(
                "The file is open in another program (most often Excel), or "
                "you don't have permission to write to that folder."
            ),
            advice=(
                "Close the file in Excel (or any other program), then try "
                "again.  If that doesn't help, save the output somewhere you "
                "have write access — for example, your Documents folder."
            ),
            technical=technical,
        )

    # ----- PDF: empty / no rows -----------------------------------------
    if "pdf appears empty" in lower or "no data rows found" in lower:
        return FriendlyError(
            banner="The PDF didn't contain any rows we could read.",
            message=(
                "We opened the PDF but couldn't find a budget or operating "
                "table inside it.  This usually means the file was exported "
                "before the data finished loading, or it's the wrong report."
            ),
            advice=(
                "Open the PDF in a viewer to confirm the data is there.  If "
                "it looks blank or only shows a cover page, re-export the "
                "report from CASES21 — make sure to export the full detailed "
                "version, not just the summary."
            ),
            technical=technical,
        )

    # ----- PDF: cannot be read ------------------------------------------
    if "cannot read" in lower and "pdf" in lower:
        return FriendlyError(
            banner="We couldn't read this PDF.",
            message=(
                "The file may be password-protected, corrupted, or in a layout we don't recognise."
            ),
            advice=(
                "Open the PDF in Adobe Reader to check it isn't broken.  If "
                "it opens fine there but the tool still can't read it, "
                "re-export the report from CASES21 (make sure 'Detailed' "
                "is selected, not 'Summary')."
            ),
            technical=technical,
        )

    # ----- Number / decimal parsing -------------------------------------
    if "cannot parse" in lower and ("decimal" in lower or "currency amount" in lower):
        return FriendlyError(
            banner="We hit a number we couldn't read in your file.",
            message=(
                "One of the cells or fields in your file contains text where "
                "we expected a number.  This often happens when a draft "
                "budget still has placeholder text in dollar columns."
            ),
            advice=(
                "Open the file and check that every dollar / amount column "
                "contains numbers only — no 'TBC', 'TBA', or notes like "
                "'see attached'.  Re-run once those rows are fixed."
            ),
            technical=technical,
        )

    # ----- Negative number where one was required to be ≥ 0 -------------
    if "must be non-negative" in lower:
        return FriendlyError(
            banner="A value can't be negative.",
            message=(
                "The amount or SIN you entered is below zero.  These fields "
                "only accept zero or positive numbers."
            ),
            advice=(
                "Check the value you typed and re-enter it as a positive "
                "amount.  If you meant a refund or correction, use the tool "
                "designed for that workflow instead."
            ),
            technical=technical,
        )

    # ----- Browser launch failure (PAL search) --------------------------
    if "could not open the browser" in lower or ("webbrowser" in lower and "open" in lower):
        return FriendlyError(
            banner="We couldn't open your default browser.",
            message=("Windows didn't return a default browser, or it refused to open the link."),
            advice=(
                "Set Edge or Chrome as your default browser in Windows "
                "Settings → Apps → Default apps, then try again.  You can "
                "also copy the URL from the log below and paste it into a "
                "browser manually."
            ),
            technical=technical,
        )

    # ----- Excel COM / Win32 retry exhaustion ---------------------------
    if "excel retry loop" in lower:
        return FriendlyError(
            banner="Excel kept refusing our updates.",
            message=(
                "We tried several times to write back to the master budget "
                "file but Excel kept rejecting the change."
            ),
            advice=(
                "Close every Excel window (check the system tray for hidden "
                "ones), make sure no one else has the file open from a "
                "shared drive, then run the tool again."
            ),
            technical=technical,
        )

    # ----- Generic fallback ---------------------------------------------
    return FriendlyError(
        banner="Something unexpected went wrong.",
        message=(
            "The tool hit an error we don't have a specific message for "
            "yet.  The technical detail is in the log below."
        ),
        advice=(
            "Try running the tool again.  If the same error comes back, "
            "send a screenshot of this screen plus the log to "
            "feedback@schooltool.com.au and we'll take a look."
        ),
        technical=technical,
    )
