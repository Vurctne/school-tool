from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from toolkit.base_tool import (
    CurrencyInput,
    DateInput,
    LogLine,
    ProgressFn,
    SecretInput,
    ToolResult,
)
from tools.hyia.logic import compute_security_code, parse_currency

_HELP_TEXT = """HYIA Transfer Code Generator

Each school is issued with a School Identification Number (SIN) by Westpac. \
The SIN is a unique, confidential identifier for the school and must be \
entered every time funds are transferred to or from the High Yield Investment \
Account via the HYIA Portal. It is extremely important that the SIN is \
appropriately safeguarded within each school.


HOW THE SECURITY CODE IS CALCULATED

The security code is the sum of three parts:

    Security Code  =  SIN  +  (Amount × 100)  +  DD  +  MM  +  YY

  1. SIN — your School Identification Number.
  2. Amount × 100 — the transfer amount with the decimal point removed \
(cents included). For example, $20,000.00 becomes 2000000.
  3. Date — the day, month, and two-digit year of the request, each added \
separately.


WORKED EXAMPLE (from the Department of Education)

    SIN Number           12345
    Amount of Transfer   $20,000.00
    Date of Request      16/02/07

    Calculate            12345 + 2000000 + 16 + 2 + 7
    SECURITY CODE      = 2012370


USING THIS TOOL

  • Enter your SIN. Click the eye icon to reveal/hide it. Tick "Remember \
on this device" to have the SIN securely stored using Windows DPAPI so you \
don't have to retype it next time.
  • Enter the transfer amount (with or without the dollar sign and commas).
  • Pick the date of the request — today by default.
  • Click "Generate code". The security code appears in large green type. \
By default the calculation breakdown is hidden so anyone glancing at your \
screen can't see how the code was assembled.
  • To verify the calculation, press and HOLD the "Show formula" button \
under the result. While you hold the left mouse button down, the formula \
appears next to the button. Release (or move the cursor off the button) \
and the formula disappears immediately. Your SIN is masked (shown as \
asterisks) in the formula.


IMPORTANT SECURITY NOTES

  • There is an additional security step in the HYIA Portal: you will be \
asked to enter a verification code from information displayed on the portal.
  • Never share your SIN by email or messaging apps.
  • If your school cannot locate its SIN, the Principal must email \
Westpac at wibce@westpac.com.au to request the current SIN or a new one.


SUPPORT

  Westpac HYIA queries:       wibce@westpac.com.au
  DoE schools finance help:   schools.finance.support@education.vic.gov.au
  This tool — feedback:         Vurctne@gmail.com

Source: Department of Education — High Yield Investment Account (HYIA) \
Funds Transfer, updated May 2022.
"""


class HyiaTool:
    id = "hyia"
    group = "Banking"
    label = "HYIA Transfer Code"
    short = "HY"
    order = 10
    primary_button = "Generate code"
    pdf_template = None
    pdf_body = None
    help_text = _HELP_TEXT
    requires_feature = None

    inputs = [
        SecretInput(
            key="sin",
            label="School Identification Number (SIN)",
            pattern=r"\d{4,6}",
            remember_key="hyia_sin",
        ),
        CurrencyInput(key="amount", label="Transfer amount"),
        DateInput(key="date", label="Date of request", default="today"),
    ]
    output = None  # no file output; result is the code itself

    # Cached formula text — populated on each successful run().  Read by the
    # press-and-hold "Show formula" button via press_hold_actions().  Empty
    # string means there is no current result to reveal.  (Round 21)
    _last_formula: str = ""

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        progress(100, "Calculating…")
        sin = int(str(paths["sin"]).strip())
        amount_cents = parse_currency(str(paths["amount"]))
        d: date = paths["date"]  # already a date per shell's DateField resolver
        bd = compute_security_code(sin, amount_cents, d)
        sin_masked = "*" * len(str(bd.sin))  # preserve digit count, hide the value
        # Cache the formula for the press-and-hold reveal button.  The log
        # below shows a placeholder line instead of the formula itself —
        # the user can verify on demand by holding "Show formula".
        self._last_formula = (
            f"{sin_masked} + {bd.amount_raw} + {bd.day} + {bd.month}"
            f" + {bd.year_two_digit} = {bd.code}"
        )
        return ToolResult(
            status="success",
            banner_level="neutral",
            banner_text="",
            metrics=[("Security code", str(bd.code), "ok")],
            log_lines=[
                LogLine(
                    "Calculation hidden. Press and HOLD 'Show formula' below "
                    "to reveal it for verification.",
                    tag="muted",
                ),
            ],
            output_path=None,
        )

    def press_hold_actions(self) -> list[tuple[str, Callable[[], str]]]:
        """Press-and-hold "Show formula" button (Round 21).

        While the user holds the left mouse button, the cached formula is
        revealed next to the button.  On release (or pointer leave) the
        text disappears.  This keeps the calculation off-screen by
        default — anyone glancing at the screen sees only the final
        security code, not the SIN-derived breakdown.
        """
        return [("Show formula", lambda: self._last_formula)]

    def clear(self) -> None:
        """Reset cached formula so a stale value can't leak after Clear."""
        self._last_formula = ""
        return None

    def preview_update(self, key: str, value: float | str) -> None:
        """No live-preview inputs on this tool; always returns None."""
        return None

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        return []  # Copy is handled shell-side because ToolResult is what it has
